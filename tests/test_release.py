from pathlib import Path

import pytest
from lxml import objectify
from pypdf import PdfReader

from ecoinvent_interface import EcoinventRelease, ReleaseType, Settings
from ecoinvent_interface.storage import md5

try:
    authenticated_settings = Settings()
    assert authenticated_settings.username
except AssertionError:
    pytest.skip("Requires ecoinvent account", allow_module_level=True)


@pytest.fixture
def release(tmp_path):
    settings = Settings(output_path=str(tmp_path))
    custom_headers = {"ecoinvent-api-client-library-is-test": "true"}
    return EcoinventRelease(settings=settings, custom_headers=custom_headers)


def test_get_release_files(release):
    rf = release.get_release_files("3.7.1")
    assert isinstance(rf, list)
    assert len(rf) == 3
    assert rf[0]["system_model_name"] == "Allocation cut-off by classification"
    assert rf[0]["release_files"][0] == {
        "uuid": "a18a6292-b5af-477b-814f-593e55ce89a6",
        "name": "ecoinvent 3.7.1_cutoff_ecoSpold02.7z",
        "size": 59512955,
        "last_modified": "2023-04-25",
        "description": None,
    }


def test_list_report_files(release):
    file_list = release.list_report_files()
    filename = "Allocation, cut-off, EN15804_documentation.pdf"
    assert filename in file_list
    for attr in ("size", "modified", "description"):
        assert file_list[filename][attr]


def test_get_report(release):
    filename = "Allocation, cut-off, EN15804_documentation.pdf"
    filepath = release.get_report(filename)
    assert md5(filepath) == "915852190a48fdc07ca6ea32e0ab70fc"
    assert PdfReader(filepath)

    metadata = release.storage.catalogue[filename]
    assert filename in metadata["path"]
    assert not metadata["extracted"]
    assert metadata["created"]

    filename = "ecoinvent 3 report_Agriculture.zip"
    dirpath = release.get_report(filename)
    filepath = (
        dirpath / "ecoinvent 3 report_Crop Production - Seed production processing.pdf"
    )
    assert md5(filepath) == "4f9e6b2a9c2022ba815fb28813b8b26e"
    assert PdfReader(filepath)

    metadata = release.storage.catalogue[filename]
    assert metadata["extracted"]
    assert metadata["created"]


def test_list_extra_files(release):
    file_list = release.list_extra_files("3.5")
    filename = "ecoinvent 3.5_APOS_known issues.xlsx"
    assert filename in file_list
    for attr in ("size", "modified"):
        assert file_list[filename][attr]


def test_get_extra(release):
    filename = "ecoinvent 3.5_APOS_known issues.xlsx"
    filepath = release.get_extra("3.5", filename)
    assert md5(filepath) == "92d6a9daf584c54b09e8456019222014"

    metadata = release.storage.catalogue[filename]
    assert filename in metadata["path"]
    assert not metadata["extracted"]
    assert metadata["created"]


@pytest.mark.slow
def test_get_release(release):
    filepath = release.get_release("3.5", "cutoff", ReleaseType.ecospold)
    metadata = release.storage.catalogue["ecoinvent 3.5_cutoff_ecoSpold02.7z"]

    assert filepath.is_dir()
    assert len(list((Path(metadata["path"]) / "datasets").iterdir())) == 16022
    assert "ecoinvent 3.5_cutoff_ecoSpold02" in metadata["path"]
    assert metadata["extracted"]
    assert metadata["created"]
    assert metadata["version"] == "3.5"
    assert metadata["kind"] == "release"
    assert metadata["archive"] == "ecoinvent 3.5_cutoff_ecoSpold02.7z"
    assert metadata["system_model"] == "cutoff"

    upr = (
        filepath
        / "datasets"
        / "daec3a84-14ca-49cb-af09-8945ad764e80_a498d9fb-9402-4374-b2e2-3f85f5d98f43.spold"  # NOQA E503
    )
    upr_root = objectify.parse(open(upr, encoding="utf-8")).getroot()
    fa = upr_root.activityDataset.administrativeInformation.fileAttributes
    assert fa.get("majorRelease") == "3"
    assert fa.get("minorRelease") == "5"

    meta = filepath / "MasterData" / "Companies.xml"
    meta_root = objectify.parse(open(meta, encoding="utf-8")).getroot()
    assert meta_root.get("majorRelease") == "3"
    assert meta_root.get("minorRelease") == "5"


@pytest.mark.slow
def test_get_release_not_extracted(release):
    filepath = release.get_release("3.4", "cutoff", ReleaseType.ecospold, extract=False)
    metadata = release.storage.catalogue[filepath.name]

    assert filepath.is_file()
    assert "ecoinvent 3.4_cutoff_ecoSpold02.7z" in metadata["path"]
    assert md5(filepath) == "74f05ecd798070ef4db7b351a6b91a4e"
    assert not metadata["extracted"]
    assert metadata["created"]
    assert metadata["version"] == "3.4"
    assert metadata["kind"] == "release"
    assert metadata["system_model"] == "cutoff"
