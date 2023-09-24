import logging
from enum import Enum
from pathlib import Path
from typing import Union
from urllib.parse import parse_qsl, urlparse

import requests

from . import __version__
from .core import SYSTEM_MODELS, InterfaceBase, fresh_login

logger = logging.getLogger("ecoinvent_interface")


class MissingProcess(BaseException):
    """Operation not possible because no process selected"""

    pass


def selected_process(f):
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, "dataset_id"):
            raise MissingProcess("Must call `.select_process()` first")
        return f(self, *args, **kwargs)

    return wrapper


def split_url(url: str) -> tuple[str, dict]:
    """Split a URL with params into a base path and a params dict"""
    nt = urlparse(url)
    return nt.path, dict(parse_qsl(nt.query))


class ProcessFileType(Enum):
    upr = "Unit Process"
    lci = "Life Cycle Inventory"
    lcia = "Life Cycle Impact Assessment"
    pdf = "Dataset Report"
    undefined = "Undefined (unlinked and multi-output) Dataset Report"


ZIPPED_FILE_TYPES = (ProcessFileType.lci, ProcessFileType.lcia, ProcessFileType.upr)


class EcoinventProcess(InterfaceBase):
    def set_release(self, version: str, system_model: str) -> None:
        if version not in self.list_versions():
            raise ValueError(f"Given version {version} not found")
        self.version = version

        system_model = SYSTEM_MODELS.get(system_model, system_model)
        if system_model not in self.list_system_models(self.version):
            raise ValueError(
                f"Given system model '{system_model}' not available in {version}"
            )
        self.system_model = system_model

    def select_process(self) -> None:
        if not hasattr(self, "system_model"):
            raise ValueError("Must call `.set_release()` first")
        self.dataset_id = "1"

    @selected_process
    @fresh_login
    def _json_request(self, url: str) -> Union[dict, list]:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "ecoinvent-api-client-library": "ecoinvent_interface",
            "ecoinvent-api-client-library-version": __version__,
        } | self.custom_headers
        return requests.get(
            url,
            params={
                "dataset_id": self.dataset_id,
                "version": self.version,
                "system_model": self.system_model,
            },
            headers=headers,
            timeout=20,
        ).json()
        message = """Requesting URL.
    URL: {url}
    Class: {self.__class__.__name__}
    Instance ID: {id(self)}
    Version: {__version__}
    User: {self.username}
        """
        logger.debug(message)

    def get_basic_info(self) -> dict:
        return self._json_request(self.urls["api"] + "spold")

    def get_documentation(self) -> dict:
        return self._json_request(self.urls["api"] + "spold/documentation")

    def get_file(self, file_type: ProcessFileType, directory: Path) -> Path:
        files = {
            obj.pop("name"): obj
            for obj in self._json_request(self.urls["api"] + "spold/export_file_list")
        }
        try:
            meta = files[file_type.value]
        except KeyError:
            available = list(files)
            raise KeyError(f"Can't find {file_type} in available options: {available}")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "ecoinvent-api-client-library": "ecoinvent_interface",
            "ecoinvent-api-client-library-version": __version__,
        } | self.custom_headers
        if meta.get("type").lower() == "xml":
            headers["Accept"] = "text/plain"

        url, params = split_url(meta["url"])
        suffix = meta["type"].lower()
        filename = (
            f"ecoinvent-{self.version}-{self.system_model}-{file_type.name}-"
            + f"{self.dataset_id}.{suffix}"
        )

        if file_type == ProcessFileType.undefined:
            s3_link = requests.get(
                self.urls["api"][:-1] + url, params=params, headers=headers, timeout=20
            ).json()["download_url"]
            self._streaming_download(
                url=s3_link, params={}, directory=directory, filename=filename
            )
            return directory / filename

        self._streaming_download(
            url=self.urls["api"][:-1] + url,
            params=params,
            directory=directory,
            filename=filename,
            headers=headers,
            zipped=file_type in ZIPPED_FILE_TYPES,
        )
        return directory / filename
