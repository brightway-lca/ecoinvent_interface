import gzip
import json
import logging
import warnings
from datetime import datetime
from pathlib import Path
from time import time
from typing import Optional

import requests

from . import __version__
from .settings import Settings
from .storage import CachedStorage

logger = logging.getLogger("ecoinvent_interface")


def logged_in(f):
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, "access_token"):
            self.login()
        return f(self, *args, **kwargs)

    return wrapper


def fresh_login(f):
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, "last_refresh"):
            self.login()
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
    dct = {
        "uuid": obj["uuid"],  # str
        "size": obj["size"],  # int
        "modified": datetime.fromisoformat(obj["last_modified"]),  # dt
    }
    if obj.get("description"):
        dct["description"] = obj["description"]
    return dct


class InterfaceBase:
    def __init__(
        self,
        settings: Settings,
        urls: Optional[dict] = None,
        custom_headers: Optional[dict] = None,
    ):
        self.username = settings.username
        if not self.username:
            raise ValueError("Missing username; see configurations docs")
        self.password = settings.password
        if not self.password:
            raise ValueError("Missing password; see configurations docs")

        self.urls = URLS if urls is None else urls
        self.custom_headers = custom_headers or {}
        self.storage = CachedStorage(settings.output_path)

        message = f"""Instantiated ecoinvent_interface class:
    Class: {self.__class__.__name__}
    Instance ID: {id(self)}
    Version: {__version__}
    User: {self.username}
    Output directory: {self.storage.dir}
    Custom headers: {bool(custom_headers)}
    Custom URLs: {bool(urls)}
    """
        logger.info(message)

    def login(self) -> None:
        post_data = {
            "username": self.username,
            "password": self.password,
            "client_id": "apollo-ui",
            "grant_type": "password",
        }
        self._get_credentials(post_data)
        message = """Got initial credentials.
    Class: {self.__class__.__name__}
    Instance ID: {id(self)}
    Version: {__version__}
    User: {self.username}
        """
        logger.debug(message)

    @logged_in
    def refresh_tokens(self) -> None:
        post_data = {
            "client_id": "apollo-ui",
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        self._get_credentials(post_data)
        message = """Renewed credentials.
    Class: {self.__class__.__name__}
    Instance ID: {id(self)}
    Version: {__version__}
    User: {self.username}
        """
        logger.debug(message)

    def _get_credentials(self, post_data: dict) -> None:
        sso_url = self.urls["sso"]
        headers = {
            "ecoinvent-api-client-library": "ecoinvent_interface",
            "ecoinvent-api-client-library-version": __version__,
        }
        headers.update(self.custom_headers)
        response = requests.post(sso_url, post_data, headers=headers, timeout=20)

        if response.ok:
            tokens = json.loads(response.text)
            self.last_refresh = time()
            self.access_token = tokens["access_token"]
            self.refresh_token = tokens["refresh_token"]
        else:
            warnings.warn(
                "Given credentials can't log in: error {}".format(response.status_code)
            )
            response.raise_for_status()

    @fresh_login
    def _get_all_reports(self) -> dict:
        reports_url = self.urls["api"] + "files/reports"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "ecoinvent-api-client-library": "ecoinvent_interface",
            "ecoinvent-api-client-library-version": __version__,
        }
        headers.update(self.custom_headers)
        message = """Requesting URL.
    URL: {reports_url}
    Class: {self.__class__.__name__}
    Instance ID: {id(self)}
    Version: {__version__}
    User: {self.username}
        """
        logger.debug(message)
        return requests.get(reports_url, headers=headers, timeout=20).json()

    @fresh_login
    def _get_all_files(self) -> dict:
        files_url = self.urls["api"] + "files"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "ecoinvent-api-client-library": "ecoinvent_interface",
            "ecoinvent-api-client-library-version": __version__,
        }
        headers.update(self.custom_headers)
        message = """Requesting URL.
    URL: {files_url}
    Class: {self.__class__.__name__}
    Instance ID: {id(self)}
    Version: {__version__}
    User: {self.username}
        """
        logger.debug(message)
        return requests.get(files_url, headers=headers, timeout=20).json()

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

    def _streaming_download(
        self,
        url: str,
        params: dict,
        directory: Path,
        filename: str,
        headers: Optional[dict] = {},
        zipped: Optional[bool] = False,
    ) -> None:
        out_filepath = directory / (filename + ".gz" if zipped else filename)
        with requests.get(
            url, stream=True, headers=headers, params=params, timeout=60
        ) as response, open(out_filepath, "wb") as out_file:
            if response.status_code != 200:
                raise requests.exceptions.HTTPError(
                    f"URL '{url}'' returns status code {response.status_code}."
                )
            download = response.raw
            chunk = 128 * 1024

            while True:
                segment = download.read(chunk)
                if not segment:
                    break
                out_file.write(segment)

        message = """Downloaded file with `_streaming_download`.
    Filename: {filename}
    Directory: {self.storage.dir}
    File size (bytes): {actual}
    Class: {self.__class__.__name__}
    Instance ID: {id(self)}
    Version: {__version__}
    User: {self.username}
        """
        logger.debug(message)

        if zipped:
            with open(out_filepath, "rb") as source, open(
                directory / filename, "w", encoding="utf-8"
            ) as target:
                gzip_fd = gzip.GzipFile(fileobj=source)
                target.write(gzip_fd.read().decode("utf-8-sig"))
            try:
                out_filepath.unlink()
            except PermissionError:
                # Error on Windows during testing
                message = """"Can't automatically delete {out_filepath}
    Please delete manually"""
                warnings.warn(message)

    @fresh_login
    def _download_api_file(
        self, url: str, filename: str, directory: Path, params: Optional[dict] = {}
    ) -> Path:
        url = self.urls["api"] + url
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "ecoinvent-api-client-library": "ecoinvent_interface",
            "ecoinvent-api-client-library-version": __version__,
        }
        headers.update(self.custom_headers)
        self._streaming_download(
            url=url,
            params=params,
            directory=directory,
            headers=headers,
            filename=filename,
        )
        return directory / filename

    @fresh_login
    def _download_s3(
        self, uuid: str, filename: str, url_namespace: str, directory: Path
    ) -> Path:
        url = self.urls["api"] + f"files/{url_namespace}/{uuid}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "ecoinvent-api-client-library": "ecoinvent_interface",
            "ecoinvent-api-client-library-version": __version__,
        }
        headers.update(self.custom_headers)
        s3_link = requests.get(url, headers=headers, timeout=20).json()["download_url"]
        self._streaming_download(
            url=s3_link, params={}, directory=directory, filename=filename
        )
        return directory / filename

    def list_versions(self) -> list:
        return [obj["version_name"] for obj in self._get_all_files()]

    def list_system_models(
        self, version: str, translate: Optional[bool] = True
    ) -> list:
        releases = [
            obj["system_model_name"]
            for obj in self._get_files_for_version(version)["releases"]
        ]
        if translate:
            releases = [SYSTEM_MODELS.get(key, key) for key in releases]
        return releases
