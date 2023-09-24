import logging
from enum import Enum
from pathlib import Path
from typing import Optional

from Levenshtein import distance

from .core import SYSTEM_MODELS, InterfaceBase, format_dict

logger = logging.getLogger("ecoinvent_interface")


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


class EcoinventRelease(InterfaceBase):
    def list_report_files(self) -> dict:
        return {obj["name"]: format_dict(obj) for obj in self._get_all_reports()}

    def get_report(
        self,
        filename: str,
        extract: Optional[bool] = True,
        force_redownload: Optional[bool] = False,
    ) -> Path:
        reports = self.list_report_files()
        return self._download_and_cache(
            filename=filename,
            uuid=reports[filename]["uuid"],
            modified=reports[filename]["modified"],
            expected_size=reports[filename]["size"],
            url_namespace="report",
            extract=extract,
            force_redownload=force_redownload,
        )

    def list_extra_files(self, version: str) -> dict:
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
        available_files = self.list_extra_files(version=version)
        return self._download_and_cache(
            filename=filename,
            uuid=available_files[filename]["uuid"],
            modified=available_files[filename]["modified"],
            expected_size=available_files[filename]["size"],
            url_namespace="v",
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
                logger.info(
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
            url_namespace="r",
            extract=extract,
            force_redownload=force_redownload,
        )
