import pytest

from ecoinvent_interface import EcoinventProcess, Settings
from ecoinvent_interface.process_interface import get_cached_mapping

try:
    authenticated_settings = Settings()
    assert authenticated_settings.username
    HAS_USERNAME = True
except AssertionError:
    HAS_USERNAME = False


@pytest.fixture
def process(tmp_path):
    get_cached_mapping.cache_clear()

    settings = Settings(output_path=str(tmp_path))
    custom_headers = {"ecoinvent-api-client-library-is-test": "true"}
    ep = EcoinventProcess(settings=settings, custom_headers=custom_headers)
    ep.set_release(version="3.7.1", system_model="apos")
    return ep


@pytest.mark.skipif(not HAS_USERNAME, reason="Requires ecoinvent account")
def test_select_process_nothing_passed(process):
    with pytest.raises(ValueError):
        process.select_process()


@pytest.mark.skipif(not HAS_USERNAME, reason="Requires ecoinvent account")
def test_setup(process):
    assert process.version == "3.7.1"
    assert process.system_model == "apos"


@pytest.mark.skipif(not HAS_USERNAME, reason="Requires ecoinvent account")
def test_select_process_dataset_id(process):
    process.select_process(dataset_id="1")
    assert process.dataset_id == "1"


@pytest.mark.skipif(not HAS_USERNAME, reason="Requires ecoinvent account")
def test_select_process_filename(process):
    F = "b0eb27dd-b87f-4ae9-9f69-57d811443a30_66c93e71-f32b-4591-901c-55395db5c132.spold"  # NOQA E501
    process.select_process(filename=F)
    assert process.dataset_id == "1"


@pytest.mark.skipif(not HAS_USERNAME, reason="Requires ecoinvent account")
def test_select_process_filename_error(process):
    with pytest.raises(KeyError):
        process.select_process(filename="foo.spold")


@pytest.mark.skipif(not HAS_USERNAME, reason="Requires ecoinvent account")
def test_select_process_attributes_multiple(process):
    with pytest.raises(KeyError):
        process.select_process(attributes={"name": "electricity production, oil"})


@pytest.mark.skipif(not HAS_USERNAME, reason="Requires ecoinvent account")
def test_select_process_attributes_simple(process):
    process.select_process(
        attributes={
            "activity_name": "rye seed production, Swiss integrated production, for sowing"  # NOQA E501
        }
    )
    assert process.dataset_id == "40"


@pytest.mark.skipif(not HAS_USERNAME, reason="Requires ecoinvent account")
def test_select_process_attributes_none(process):
    with pytest.raises(KeyError):
        process.select_process(
            attributes={
                "activity_name": "rye sd production, Swiss integrated production, for sowing"  # NOQA E501
            }
        )


@pytest.mark.skipif(not HAS_USERNAME, reason="Requires ecoinvent account")
def test_select_process_attributes_translation(process):
    process.select_process(
        attributes={
            "name": "rye seed production, Swiss integrated production, for sowing",
            "location": "CH",
            "reference product": "rye seed, Swiss integrated production, for sowing",
        }
    )
    assert process.dataset_id == "40"
