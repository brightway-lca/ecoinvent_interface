import hashlib
import json
import shutil
from collections.abc import MutableMapping
from pathlib import Path
from typing import Iterable, Union

import platformdirs

base_dir = Path(
    platformdirs.user_data_dir(appname="EcoinventInterface", appauthor="pylca")
)
cache_dir_platformdirs = base_dir / "cache"
cache_dir_platformdirs.mkdir(exist_ok=True, parents=True)
secrets_dir = base_dir / "secrets"
secrets_dir.mkdir(exist_ok=True)


class Catalogue(MutableMapping):
    """Synchronous JSON dictionary"""

    def __init__(self, filepath: Path):
        self._filepath = filepath
        if not self._filepath.exists():
            self._write({})

    def _load(self):
        return json.load(open(self._filepath, encoding="utf-8"))

    def _write(self, data: dict) -> None:
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def __getitem__(self, key: str) -> dict:
        return self._load()[key]

    def __setitem__(self, key: str, value: dict) -> None:
        data = self._load()
        data[key] = value
        self._write(data)

    def __delitem__(self, key: str) -> None:
        data = self._load()
        del data[key]
        self._write(data)

    def __iter__(self) -> Iterable[str]:
        return iter(self._load())

    def __len__(self) -> int:
        return len(self._load())


class CachedStorage:
    def __init__(self, cache_dir: Union[None, Path, str] = None):
        if cache_dir:
            self.dir = Path(cache_dir)
        else:
            self.dir = cache_dir_platformdirs

        if not self.dir.is_dir():
            self.dir.mkdir(exist_ok=True, parents=True)

        self.catalogue = Catalogue(self.dir / "catalogue.json")

    def clear(self):
        shutil.rmtree(self.dir, ignore_errors=True)
        (self.dir / "catalogue.json").unlink()
        self.dir.mkdir(exist_ok=True)


def md5(filepath: Union[str, Path], blocksize: int = 65536) -> str:
    """Generate MD5 hash for file at `filepath`"""
    hasher = hashlib.md5()
    fo = open(filepath, "rb")
    buf = fo.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = fo.read(blocksize)
    return hasher.hexdigest()
