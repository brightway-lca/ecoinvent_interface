import pytest

from ecoinvent_interface import EcoinventRelease, Settings
from ecoinvent_interface.storage import md5

try:
    authenticated_settings = Settings()
    assert authenticated_settings.username
    HAS_USERNAME = True
except AssertionError:
    HAS_USERNAME = False


@pytest.fixture
def release(tmp_path):
    settings = Settings(output_path=str(tmp_path))
    custom_headers = {"ecoinvent-api-client-library-is-test": "true"}
    return EcoinventRelease(settings=settings, custom_headers=custom_headers)


@pytest.mark.skipif(not HAS_USERNAME, reason="Requires ecoinvent account")
def test_list_report_files(release):
    file_list = release.list_report_files()
    filename = "Allocation, cut-off, EN15804_documentation.pdf"
    assert filename in file_list
    for attr in ("size", "modified", "description"):
        assert file_list[filename][attr]


@pytest.mark.skipif(not HAS_USERNAME, reason="Requires ecoinvent account")
def test_get_report(release):
    filename = "Allocation, cut-off, EN15804_documentation.pdf"
    filepath = release.get_report(filename)
    assert md5(filepath) == "915852190a48fdc07ca6ea32e0ab70fc"

    metadata = release.storage.catalogue[filename]
    assert filename in metadata["path"]
    assert not metadata["extracted"]
    assert metadata["created"]


@pytest.mark.skipif(not HAS_USERNAME, reason="Requires ecoinvent account")
def test_list_extra_files(release):
    file_list = release.list_extra_files("3.5")
    filename = "ecoinvent 3.5_APOS_known issues.xlsx"
    assert filename in file_list
    for attr in ("size", "modified"):
        assert file_list[filename][attr]


@pytest.mark.skipif(not HAS_USERNAME, reason="Requires ecoinvent account")
def test_get_extra(release):
    filename = "ecoinvent 3.5_APOS_known issues.xlsx"
    filepath = release.get_extra("3.5", filename)
    assert md5(filepath) == "92d6a9daf584c54b09e8456019222014"

    metadata = release.storage.catalogue[filename]
    assert filename in metadata["path"]
    assert not metadata["extracted"]
    assert metadata["created"]


# TBD
# def test_get_release()
