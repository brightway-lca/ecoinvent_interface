import pytest

from ecoinvent_interface import EcoinventRelease, Settings
from ecoinvent_interface import get_excel_lcia_file_for_version as gelffv


@pytest.fixture
def release(tmp_path):
    settings = Settings(output_path=str(tmp_path))
    custom_headers = {"ecoinvent-api-client-library-is-test": "true"}
    return EcoinventRelease(settings=settings, custom_headers=custom_headers)


def test_gelffv_basic(release):
    assert gelffv(release, "3.7.1").name == "LCIA_implementation_3.7.1.xlsx"
    assert gelffv(release, "3.8").name == "LCIA Implementation v3.8.xlsx"
    assert gelffv(release, "3.9.1").name == "LCIA Implementation 3.9.1.xlsx"


def test_gelffv_input_errors(release):
    with pytest.raises(ValueError):
        gelffv(release, "3.17.1")
    with pytest.raises(ValueError):
        gelffv(None, "3.7.1")
