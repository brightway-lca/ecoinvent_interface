import pytest

from ecoinvent_interface import EcoinventProcess, EcoinventRelease, Settings
from ecoinvent_interface.process_interface import get_cached_mapping


def check_access():
    authenticated_settings = Settings()
    if not authenticated_settings.username:
        return False
    release = EcoinventRelease(
        settings=authenticated_settings,
        custom_headers={"ecoinvent-api-client-library-is-test": "true"},
    )
    try:
        release.get_release_files("3.7.1")
        return True
    except PermissionError:
        return False


has_access = check_access()


@pytest.fixture()
def custom_headers():
    return {"ecoinvent-api-client-library-is-test": "true"}


@pytest.fixture()
def settings(custom_headers, tmp_path):
    if not has_access:
        pytest.skip(
            f"Current credentials don't allow sufficient access for test functionality"
        )

    get_cached_mapping.cache_clear()
    return Settings(output_path=str(tmp_path))


@pytest.fixture
def process(settings, custom_headers):
    ep = EcoinventProcess(settings=settings, custom_headers=custom_headers)
    ep.set_release(version="3.7.1", system_model="apos")
    return ep


@pytest.fixture
def undefined(settings, custom_headers):
    ep = EcoinventProcess(settings=settings, custom_headers=custom_headers)
    ep.set_release(version="3.10", system_model="undefined")
    return ep


@pytest.fixture
def nuclear(process):
    process.select_process(dataset_id="1")
    return process


@pytest.fixture
def release(settings, custom_headers):
    return EcoinventRelease(settings=settings, custom_headers=custom_headers)
