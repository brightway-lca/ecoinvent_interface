import json
import logging
import shutil
import urllib
from time import time
from typing import Optional
from enum import Enum
from pathlib import Path
from datetime import datetime

import py7zr
import requests
from Levenshtein import distance

from .storage import CachedStorage
from .settings import Settings


class NotLoggedIn(BaseException):
    """Operation not possible because not logged in"""

    pass


def logged_in(f):
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, "access_token"):
            raise NotLoggedIn("Must call `.login()` first")
        return f(self, *args, **kwargs)

    return wrapper


def fresh_login(f):
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, "last_refresh"):
            raise NotLoggedIn("Must call `.login()` first")
        if time() - self.last_refresh > 120:
            self.refresh_tokens()
        return f(self, *args, **kwargs)

    return wrapper


URLS = {
    "sso": "https://sso.ecoinvent.org/realms/ecoinvent/protocol/openid-connect/token",
    "api": "https://api.ecoquery.ecoinvent.org/",
}

SYSTEM_MODELS = {
    "Allocation cut-off by classification": "cutoff",
    "Substitution, consequential, long-term": "consequential",
    "Allocation at the Point of Substitution": "apos",
    "Allocation, cut-off, EN15804": "EN15804",
}
SYSTEM_MODELS_REVERSE = {v: k for k, v in SYSTEM_MODELS.items()}


def format_dict(obj: dict) -> dict:
    return {
        "uuid": obj["uuid"],  # str
        "size": obj["size"],  # int
        "modified": datetime.fromisoformat(obj["last_modified"]),  # dt
    }


class ReleaseType(Enum):
    ecospold = "ecoinvent {version}_{system_model_abbr}_ecoSpold02.7z"
    matrix = "universal_matrix_export_{version}_{system_model_abbr}.7z"
    lci = "ecoinvent {version}_{system_model_abbr}_lci_ecoSpold02.7z"
    lcia = "ecoinvent {version}_{system_model_abbr}_lcia_ecoSpold02.7z"
    cumulative_lci = "ecoinvent {version}_{system_model_abbr}_cumulative_lci_xlsx.7z"
    cumulative_lcia = "ecoinvent {version}_{system_model_abbr}_cumulative_lcia_xlsx.7z"

    def filename(self, version: str, system_model_abbr: str) -> str:
        return self.value.format(
            **{"version": version, "system_model_abbr": system_model_abbr}
        )


class EcoinventInterface:
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        output_dir: Optional[Path] = None,
        urls: Optional[dict] = None,
        custom_headers: Optional[dict] = None,
    ):
        settings = Settings()
        self.username = username or settings.username
        self.password = password or settings.password
        self.urls = URLS if urls is None else urls
        self.custom_headers = custom_headers or {}
        self.storage = CachedStorage(output_dir or settings.output_path)
        if not self.username:
            raise ValueError("Missing username; see configurations docs")
        if not self.password:
            raise ValueError("Missing password; see configurations docs")

        message = f"""Instantiated `EcoinventInterface`.
    User: {self.username}
    Output directory: {self.storage.dir}
    """
        logging.info(message)

    def login(self) -> None:
        post_data = {
            "username": self.username,
            "password": self.password,
            "client_id": "apollo-ui",
            "grant_type": "password",
        }
        self._get_credentials(post_data)

    @logged_in
    def refresh_tokens(self) -> None:
        post_data = {
            "client_id": "apollo-ui",
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        self._get_credentials(post_data)

    def _get_credentials(self, post_data: dict) -> None:
        sso_url = self.urls["sso"]
        headers = {
            "ecoinvent-api-client-library": "ecoinvent_interface 2.0"
        } | self.custom_headers
        response = requests.post(sso_url, post_data, headers=headers, timeout=20)

        if response.ok:
            tokens = json.loads(response.text)
            self.last_refresh = time()
            self.access_token = tokens["access_token"]
            self.refresh_token = tokens["refresh_token"]
        else:
            print(
                "Given credentials can't log in: error {}".format(response.status_code)
            )
            response.raise_for_status()

    @fresh_login
    def _get_all_files(self) -> dict:
        files_url = self.urls["api"] + "files"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "ecoinvent-api-client-library": "ecoinvent_interface 2.0",
        } | self.custom_headers
        files_res = requests.get(files_url, headers=headers, timeout=20)
        return files_res.json()

    def _get_files_for_version(self, version: str) -> dict:
        data = self._get_all_files()
        mapping = {obj["version_name"]: index for index, obj in enumerate(data)}
        try:
            return data[mapping[version]]
        except KeyError:
            raise KeyError(
                "{} not in found versions: {}".format(version, list(mapping))
            )

    def _filename_dict(self, version: str) -> dict:
        return {
            dct["name"]: format_dict(dct)
            for obj in self._get_files_for_version(version=version)["releases"]
            for dct in obj["release_files"]
        }

    def _download_and_cache(
        self,
        filename: str,
        uuid: str,
        modified: datetime,
        expected_size: int,
        url_namespace: str,
        extract: Optional[bool] = True,
        force_redownload: Optional[bool] = False,
    ) -> Path:
        if filename in self.storage.catalogue:
            cache_meta = self.storage.catalogue[filename]
            cache_fresh = datetime.fromisoformat(cache_meta["created"]) > modified
            if cache_fresh and not force_redownload:
                return Path(cache_meta["path"])

        filepath = self._download_s3(
            uuid=uuid, filename=filename, url_namespace=url_namespace, directory=self.storage.dir
        )

        try:
            actual = filepath.stat().st_size
            if actual != expected_size:
                ERROR = f""""Downloaded file doesn't match expected size:
    Actual: {actual}
    Expected: {expected_size}
Proceeding anyways as no download error occurred."""
                logging.error(ERROR)
        except KeyError:
            pass

        if filepath.suffix.lower() == ".7z" and extract:
            with py7zr.SevenZipFile(filepath, "r") as archive:
                directory = filepath.parent / Path(filename).stem
                if directory.exists():
                    shutil.rmtree(directory)
                archive.extractall(path=directory)
                filepath.unlink()
                self.storage.catalogue[filename] = {
                    "path": str(directory),
                    "extracted": True,
                    "created": datetime.now().isoformat(),
                }
                return directory
        else:
            self.storage.catalogue[filename] = {
                "path": str(filepath),
                "extracted": False,
                "created": datetime.now().isoformat(),
            }
            return filepath

    @fresh_login
    def _download_s3(self, uuid: str, filename: str, url_namespace: str, directory: Path) -> Path:
        url = f"https://api.ecoquery.ecoinvent.org/files/{url_namespace}/{uuid}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "ecoinvent-api-client-library": "ecoinvent_interface 2.0",
        } | self.custom_headers
        s3_link = requests.get(url, headers=headers, timeout=20).json()["download_url"]

        with urllib.request.urlopen(s3_link, timeout=60) as response, open(
            directory / filename, "wb"
        ) as out_file:
            if response.status != 200:
                raise urllib.error.HTTPError(
                    "URL {} returns status code {}.".format(url, response.status)
                )
            # Streaming download to reduce memory consumption
            chunk = 128 * 1024
            while True:
                segment = response.read(chunk)
                if not segment:
                    break
                out_file.write(segment)

        return directory / filename

    def get_versions(self) -> list:
        return [obj["version_name"] for obj in self._get_all_files()]

    def get_system_models(self, version: str, translate: Optional[bool] = True) -> list:
        releases = [obj["system_model_name"] for obj in self.get_release_files(version)]
        if translate:
            releases = [SYSTEM_MODELS.get(key, key) for key in releases]
        return releases

    def get_extra_files(self, version: str) -> dict:
        return {
            obj["name"]: format_dict(obj)
            for obj in self._get_files_for_version(version=version)["version_files"]
        }

    def get_extra(
        self,
        version: str,
        filename: str,
        extract: Optional[bool] = True,
        force_redownload: Optional[bool] = False,
    ) -> Path:
        available_files = self.get_extra_files(version=version)
        return self._download_and_cache(
            filename=filename,
            uuid=available_files[filename]["uuid"],
            modified=available_files[filename]["modified"],
            expected_size=available_files[filename]["size"],
            url_namespace='v',
            extract=extract,
            force_redownload=force_redownload,
        )

    def get_release_files(self, version: str) -> list:
        return self._get_files_for_version(version)["releases"]

    def get_release(
        self,
        version: str,
        system_model: str,
        release_type: ReleaseType,
        extract: Optional[bool] = True,
        force_redownload: Optional[bool] = False,
    ) -> Path:
        if not isinstance(release_type, ReleaseType):
            raise ValueError("`release_type` must be an instance of `ReleaseType`")

        abbr = SYSTEM_MODELS.get(system_model, system_model)
        filename = release_type.filename(version=version, system_model_abbr=abbr)
        available_files = self._filename_dict(version=version)

        if filename not in available_files:
            # Sometimes the filename prediction doesn't work, as not every filename
            # follows our patterns. But these exceptions are unpredictable, it's
            # just easier to find the closest match and log the correction
            # than build a catalogue of exceptions.
            possible = sorted(
                [(distance(filename, maybe), maybe) for maybe in available_files]
            )[0]
            if possible[0] <= 3:
                logging.info(
                    f"Using close match {possible[1]} for predicted filename {filename}"
                )
                filename = possible[1]
            else:
                ERROR = """"Can't find predicted filename {filename}.
    Closest match is {possible[1]}.
    Filenames for this version:""" + "\n\t".join(
                    available_files
                )
                raise ValueError(ERROR)

        return self._download_and_cache(
            filename=filename,
            uuid=available_files[filename]["uuid"],
            modified=available_files[filename]["modified"],
            expected_size=available_files[filename]["size"],
            url_namespace='r',
            extract=extract,
            force_redownload=force_redownload,
        )
