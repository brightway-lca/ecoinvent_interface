import os
from pathlib import Path
from unittest import mock

import pytest
from pydantic_settings import SettingsConfigDict

from ecoinvent_interface import Settings


@pytest.fixture
def set_envvar(monkeypatch):
    monkeypatch.setenv("EI_PASSWORD", "red")
    monkeypatch.setenv("EI_USERNAME", "blue")
    monkeypatch.setenv("EI_OUTPUT_PATH", "green")


@pytest.fixture
def secrets_tmp_path(tmp_path):
    dir_path = Path(tmp_path)

    with open(dir_path / "EI_username", "w", encoding="utf-8") as f:
        f.write("up")
    with open(dir_path / "EI_password", "w", encoding="utf-8") as f:
        f.write("down")
    with open(dir_path / "EI_output_path", "w", encoding="utf-8") as f:
        f.write("all around")

    return dir_path


def custom_settings(dirpath, **kwargs):
    class CustomSettings(Settings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            secrets_dir=dirpath,
            env_prefix="EI_",
        )

    return CustomSettings(**kwargs)


def test_set_manually():
    my_parameters = {"username": "foo", "password": "bar", "output_path": "baz"}
    settings = Settings(**my_parameters)
    assert settings.username == "foo"
    assert settings.password == "bar"
    assert settings.output_path == "baz"


def test_set_manually_with_envvar(set_envvar):
    my_parameters = {"username": "foo", "password": "bar", "output_path": "baz"}
    settings = Settings(**my_parameters)
    assert settings.username == "foo"
    assert settings.password == "bar"
    assert settings.output_path == "baz"


def test_use_envvar(set_envvar):
    settings = Settings()
    assert settings.username == "blue"
    assert settings.password == "red"
    assert settings.output_path == "green"


# Environment values set in CI runners for integration tests
@mock.patch.dict(os.environ, {}, clear=True)
def test_use_secrets(secrets_tmp_path):
    settings = custom_settings(secrets_tmp_path)
    assert settings.username == "up"
    assert settings.password == "down"
    assert settings.output_path == "all around"


def test_envvar_over_secrets(set_envvar, secrets_tmp_path):
    settings = custom_settings(secrets_tmp_path)
    assert settings.username == "blue"
    assert settings.password == "red"
    assert settings.output_path == "green"


def test_manual_over_others(set_envvar, secrets_tmp_path):
    my_parameters = {"username": "foo", "password": "bar", "output_path": "baz"}
    settings = custom_settings(secrets_tmp_path, **my_parameters)
    assert settings.username == "foo"
    assert settings.password == "bar"
    assert settings.output_path == "baz"
