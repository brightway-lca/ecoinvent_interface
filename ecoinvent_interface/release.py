import logging
import shutil
import warnings
import zipfile
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import py7zr

from .core import SYSTEM_MODELS, InterfaceBase, format_dict
from .spold_versions import fix_version_meta, fix_version_upr, major_minor_from_string
from .string_distance import damerau_levenshtein

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
            version=None,
            system_model=None,
            kind="report",
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
            version=version,
            system_model=None,
            kind="extra",
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
        fix_version: Optional[bool] = True,
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
                [
                    (damerau_levenshtein(filename, maybe), maybe)
                    for maybe in available_files
                ]
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

        cached = filename in self.storage.catalogue
        result_path = self._download_and_cache(
            filename=filename,
            uuid=available_files[filename]["uuid"],
            modified=available_files[filename]["modified"],
            expected_size=available_files[filename]["size"],
            url_namespace="r",
            extract=extract,
            force_redownload=force_redownload,
            version=version,
            system_model=system_model,
            kind="release",
        )

        SPOLD_FILES = (ReleaseType.ecospold, ReleaseType.lci, ReleaseType.lcia)
        if fix_version and release_type in SPOLD_FILES and not cached:
            major, minor = major_minor_from_string(version)
            if (result_path / "datasets").is_dir():
                logger.info("Fixing versions in unit process datasets")
                for filepath in (result_path / "datasets").iterdir():
                    if not filepath.suffix.lower() == ".spold":
                        continue
                    fix_version_upr(
                        filepath=filepath, major_version=major, minor_version=minor
                    )
            if (result_path / "MasterData").is_dir():
                logger.info("Fixing versions in master data")
                for filepath in (result_path / "MasterData").iterdir():
                    if not filepath.suffix.lower() == ".xml":
                        continue
                    fix_version_meta(
                        filepath=filepath, major_version=major, minor_version=minor
                    )

        return result_path

    def _download_and_cache(
        self,
        filename: str,
        uuid: str,
        kind: str,
        modified: datetime,
        expected_size: int,
        url_namespace: str,
        version: Optional[str] = None,
        system_model: Optional[str] = None,
        extract: Optional[bool] = True,
        force_redownload: Optional[bool] = False,
    ) -> Path:
        if filename in self.storage.catalogue:
            cache_meta = self.storage.catalogue[filename]
            if (
                cache_meta["kind"] != kind
                or cache_meta["system_model"] != system_model
                or cache_meta["version"] != version
            ):
                message = f"""{filename} in cache inconsistent with requested:
    Cache version: {cache_meta['version']}
    Requested version: {version}
    Cache system model: {cache_meta['system_model']}
    Requested system model: {system_model}
    Cache kind: {cache_meta['kind']}
    Requested kind: {kind}"""
                raise ValueError(message)
            cache_fresh = datetime.fromisoformat(cache_meta["created"]) > modified
            if cache_fresh and not force_redownload:
                return Path(cache_meta["path"])

        filepath = self._download_s3(
            uuid=uuid,
            filename=filename,
            url_namespace=url_namespace,
            directory=self.storage.dir,
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
                self.storage.catalogue[filename] = {
                    "path": str(directory),
                    "archive": filepath.name,
                    "extracted": True,
                    "created": datetime.now().isoformat(),
                    "system_model": system_model,
                    "version": version,
                    "kind": kind,
                }
                try:
                    filepath.unlink()
                except PermissionError:
                    # Error on Windows during testing
                    message = f"""Can't automatically delete {filepath}
        Please delete manually"""
                    warnings.warn(message)
                message = f"""Adding to cache:
    Filename: {filename}
    Version: {version}
    Kind: {kind}
    Directory: {directory}
    Extracted: True
    Archive format: 7z
                """
                logger.debug(message)
                return directory
        elif filepath.suffix.lower() == ".zip" and extract:
            with zipfile.ZipFile(filepath, "r") as archive:
                directory = filepath.parent / Path(filename).stem
                if directory.exists():
                    shutil.rmtree(directory)
                archive.extractall(path=directory)
                try:
                    filepath.unlink()
                except PermissionError:
                    # Error on Windows during testing
                    message = f"""Can't automatically delete {filepath}
        Please delete manually"""
                    warnings.warn(message)

                self.storage.catalogue[filename] = {
                    "path": str(directory),
                    "archive": filepath.name,
                    "extracted": True,
                    "created": datetime.now().isoformat(),
                    "system_model": system_model,
                    "version": version,
                    "kind": kind,
                }
                message = f"""Adding to cache:
    Filename: {filename}
    Version: {version}
    Kind: {kind}
    Directory: {directory}
    Extracted: True
    Archive format: zip
                """
                logger.debug(message)
                return directory
        else:
            self.storage.catalogue[filename] = {
                "path": str(filepath),
                "extracted": False,
                "created": datetime.now().isoformat(),
                "system_model": system_model,
                "version": version,
                "kind": kind,
            }
            message = f"""Adding to cache:
    Filename: {filename}
    Version: {version}
    Kind: {kind}
    Extracted: False
            """
            logger.debug(message)
            return filepath


def get_excel_lcia_file_for_version(release: EcoinventRelease, version: str) -> Path:
    """
    The Excel LCIA file has varying names depending on the version. This
    function download the LCIA file, if necessary, and returns the filepath
    of the Excel file for further use.

    Parameters
    ----------
    release
        An instance of `EcoinventRelease` with valid settings
    version
        The ecoinvent version for which the LCIA file should be found

    Returns
    -------
    A `pathlib.Path` filepath

    """
    if not isinstance(release, EcoinventRelease):
        raise ValueError("`release` must be an instance of `EcoinventRelease`")
    if version not in release.list_versions():
        raise ValueError("Invalid version")

    filelist = release.list_extra_files(version)
    guess = f"ecoinvent {version}_LCIA_implementation.7z"

    possibles = sorted(
        [
            (damerau_levenshtein(given, guess), given)
            for given in release.list_extra_files(version)
            if "lcia" in given.lower() and version in given
        ]
    )
    if not possibles:
        raise ValueError(f"Can't find LCIA file close to {guess} among {filelist}")
    elif possibles[0][0] > 10:
        raise ValueError(
            f"Closest LCIA filename match to {guess} is {filelist[0][1]},"
            + "but this is too different"
        )
    dirpath = release.get_extra(
        version=version,
        filename=possibles[0][1],
    )

    guess = f"LCIA_implementation_{version}.xlsx"
    filelist = list(dirpath.iterdir())
    possibles = sorted(
        [
            (damerau_levenshtein(filepath.name, guess), filepath)
            for filepath in filelist
            if filepath.suffix.lower() == ".xlsx" and version in filepath.name
        ]
    )
    if possibles and possibles[0][0] < 10:
        return possibles[0][1]
    else:
        raise ValueError(f"Can't find LCIA Excel file like {guess} in {filelist}")
