import os.path
from typing import Optional
from pydantic import BaseSettings, SecretStr

class Settings(BaseSettings):
    username: Optional[str]
    password: Optional[SecretStr]
    output_path: Optional[str]
    database_spdx: Optional[str]

    class Config:
        env_prefix = 'ECOINVENT_'

    @property
    def version(self):
        return self.database_spdx.split('-')[1]

    @property
    def system_model(self):
        return self.database_spdx.split('-')[2]

if os.path.exists('eidl/settings/ecoinvent_settings') and os.path.exists('eidl/settings/secrets/ecoinvent_password'):
    settings = Settings(_env_file='eidl/settings/ecoinvent_settings', _secrets_dir='eidl/settings/secrets')
elif os.path.exists('eidl/settings/ecoinvent_settings'):
    settings = Settings(_env_file='eidl/settings/ecoinvent_settings')
else:
    settings = {}

print(settings)
