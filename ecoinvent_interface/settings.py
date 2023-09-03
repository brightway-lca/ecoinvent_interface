from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from .storage import secrets_dir


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        secrets_dir=secrets_dir,
        env_prefix="EI_",
    )

    username: Optional[str] = None
    password: Optional[str] = None
    output_path: Optional[str] = None
