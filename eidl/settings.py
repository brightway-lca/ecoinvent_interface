from os.path import dirname, join
from typing import Optional
from pydantic import BaseSettings, SecretStr

PROJECT_ROOT = dirname(dirname(__file__))


class Settings(BaseSettings):
    username: Optional[str]
    password: Optional[SecretStr]
    output_path: Optional[str]
    version_model: Optional[str]

    class Config:
        env_file = '.env.template', '.env'
        env_prefix = 'ECOINVENT_'
        secrets_dir = join(PROJECT_ROOT, 'secrets')

    @property
    def version(self):
        return self.version_model.split('-')[1]

    @property
    def system_model(self):
        return self.version_model.split('-')[2]
