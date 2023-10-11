import sys

import pytest
from pypdf import PdfReader

from ecoinvent_interface import EcoinventProcess, ProcessFileType, Settings
from ecoinvent_interface.process_interface import MissingProcess, get_cached_mapping
from ecoinvent_interface.storage import md5

try:
    authenticated_settings = Settings()
    assert authenticated_settings.username
except AssertionError:
    pytest.skip("Requires ecoinvent account", allow_module_level=True)

WINDOWS = sys.platform.startswith("cygwin") or sys.platform.startswith("win32")


@pytest.fixture
def process(tmp_path):
    get_cached_mapping.cache_clear()

    settings = Settings(output_path=str(tmp_path))
    custom_headers = {"ecoinvent-api-client-library-is-test": "true"}
    ep = EcoinventProcess(settings=settings, custom_headers=custom_headers)
    ep.set_release(version="3.7.1", system_model="apos")
    return ep


@pytest.fixture
def nuclear(process):
    process.select_process(dataset_id="1")
    return process


def test_get_cached_mapping_error():
    with pytest.raises(KeyError):
        get_cached_mapping("foo", "bar")


def test_select_process_without_release_error(tmp_path):
    settings = Settings(output_path=str(tmp_path))
    custom_headers = {"ecoinvent-api-client-library-is-test": "true"}
    ep = EcoinventProcess(settings=settings, custom_headers=custom_headers)
    with pytest.raises(ValueError):
        ep.select_process(dataset_id="1")


def test_invalid_system_model_error(tmp_path):
    settings = Settings(output_path=str(tmp_path))
    custom_headers = {"ecoinvent-api-client-library-is-test": "true"}
    ep = EcoinventProcess(settings=settings, custom_headers=custom_headers)
    with pytest.raises(ValueError):
        ep.set_release(version="3.4", system_model="EN15804")


def test_invalid_release_error(tmp_path):
    settings = Settings(output_path=str(tmp_path))
    custom_headers = {"ecoinvent-api-client-library-is-test": "true"}
    ep = EcoinventProcess(settings=settings, custom_headers=custom_headers)
    with pytest.raises(ValueError):
        ep.set_release(version="2.4", system_model="cutoff")


def test_select_process_nothing_passed(process):
    with pytest.raises(ValueError):
        process.select_process()


def test_no_selected_process(process):
    with pytest.raises(MissingProcess):
        process.get_basic_info()


def test_setup(process):
    assert process.version == "3.7.1"
    assert process.system_model == "apos"


def test_select_process_dataset_id(nuclear):
    assert nuclear.dataset_id == "1"


def test_select_process_filename(process):
    F = "b0eb27dd-b87f-4ae9-9f69-57d811443a30_66c93e71-f32b-4591-901c-55395db5c132.spold"  # NOQA E501
    process.select_process(filename=F)
    assert process.dataset_id == "1"


def test_select_process_filename_error(process):
    with pytest.raises(KeyError):
        process.select_process(filename="foo.spold")


def test_select_process_attributes_multiple(process):
    with pytest.raises(KeyError):
        process.select_process(attributes={"name": "electricity production, oil"})


def test_select_process_attributes_simple(process):
    process.select_process(
        attributes={
            "activity_name": "rye seed production, Swiss integrated production, for sowing"  # NOQA E501
        }
    )
    assert process.dataset_id == "40"


def test_select_process_attributes_none(process):
    with pytest.raises(KeyError):
        process.select_process(
            attributes={
                "activity_name": "rye sd production, Swiss integrated production, for sowing"  # NOQA E501
            }
        )


def test_select_process_attributes_translation(process):
    process.select_process(
        attributes={
            "name": "rye seed production, Swiss integrated production, for sowing",
            "location": "CH",
            "reference product": "rye seed, Swiss integrated production, for sowing",
        }
    )
    assert process.dataset_id == "40"


def test_get_basic_info(nuclear):
    expected = {
        "index": 1,
        "version": "3.7.1",
        "system_model": "apos",
        "activity_name": "electricity production, nuclear, boiling water reactor",
        "geography": "FI",
        "reference_product": "electricity, high voltage",
        "has_access": True,
    }
    assert nuclear.get_basic_info() == expected


def test_get_documentation(nuclear):
    result = nuclear.get_documentation()
    assert result["id"] == "b0eb27dd-b87f-4ae9-9f69-57d811443a30"


def test_get_file_upr(nuclear, tmp_path):
    fp = nuclear.get_file(file_type=ProcessFileType.upr, directory=tmp_path)
    # Manually verified to be readable and correct type
    if not WINDOWS:
        assert md5(fp) == "e2ff34407d0b74e2c8c80012516205f3"


def test_get_file_lci(nuclear, tmp_path):
    fp = nuclear.get_file(file_type=ProcessFileType.lci, directory=tmp_path)
    # Manually verified to be readable and correct type
    if not WINDOWS:
        assert md5(fp) == "ae0777ec7cfc086fb579a600d6e8b1dd"


def test_get_file_lcia(nuclear, tmp_path):
    fp = nuclear.get_file(file_type=ProcessFileType.lcia, directory=tmp_path)
    # Manually verified to be readable and correct type
    if not WINDOWS:
        assert md5(fp) == "3457143456bffad2b6c048bee6d87ad3"


def test_get_file_pdf(nuclear, tmp_path):
    fp = nuclear.get_file(file_type=ProcessFileType.pdf, directory=tmp_path)
    # This file generated dynamically, and the hash changes.
    # Just make sure it is readable as a PDF.
    assert PdfReader(fp)


def test_get_file_undefined(nuclear, tmp_path):
    fp = nuclear.get_file(file_type=ProcessFileType.undefined, directory=tmp_path)
    # Manually verified to be readable and correct type
    assert md5(fp) == "052f51f3fbb79a13a78753e9ff40428a"
    assert PdfReader(fp)
