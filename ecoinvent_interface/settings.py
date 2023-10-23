from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from .storage import secrets_dir


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        secrets_dir=secrets_dir,
        env_prefix="EI_",
    )

    username: Optional[str] = None
    password: Optional[str] = None
    output_path: Optional[str] = None


def permanent_setting(key: str, value: str) -> None:
    """Write a setting value permanently.

    Only accepts keys of `username`, `password`, and `output_path`.

    We are using [pydantic settings](https://docs.pydantic.dev/latest/usage/pydantic_settings/).
    As the main things being stored are secrets, we use their file-based
    secrets system.

    Manually-specified or environment variable values will always take
    precedence over the file-based values.

    One tricky bit is the the filenames need to use the `env_prefix`. See
    [this issue](https://github.com/pydantic/pydantic/issues/1279).

    """  # NOQA E501
    if key not in ("username", "password", "output_path"):
        raise ValueError(f"Invalid setting value {key}")

    with open(secrets_dir / f"EI_{key}", "w", encoding="utf-8") as f:
        f.write(value)
