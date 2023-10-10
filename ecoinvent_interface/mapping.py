from pathlib import Path
from time import sleep
from typing import Optional

import pyecospold
from tqdm import tqdm

from . import CachedStorage, EcoinventProcess, Settings

DATA_DIR = Path(__file__).parent.resolve() / "data"


def get_rp_text(exchanges: list) -> str:
    rp_exchanges = [
        exc for exc in exchanges if exc.groupStr == "ReferenceProduct" and exc.amount
    ]
    if len(rp_exchanges) != 1:
        raise ValueError("Can't find single reference product")
    return rp_exchanges[0].names[0]


class ProcessMapping:
    def __init__(
        self, settings: Settings, storage: Optional[CachedStorage] = None
    ) -> None:
        self.settings = settings
        self.storage = storage or CachedStorage()

    def create_remote_mapping(
        self, version: str, system_model: str, max_id: int
    ) -> list:
        remote_data = []

        process = EcoinventProcess(self.settings)
        process.set_release(version, system_model)

        for index in tqdm(range(1, max_id + 1)):
            process.dataset_id = index
            remote_data.append(process.get_basic_info())
            sleep(0.1)

        return remote_data

    def create_local_mapping(self, key: str, verbose: bool) -> None:
        if key not in self.storage.catalogue:
            ERROR = f"{key} not in current catalogue. Download the release and retry."
            raise ValueError(ERROR)

        dir_path = Path(self.storage.catalogue[key]["path"]) / "datasets"
        local_data = []
        file_paths = [
            fp
            for fp in dir_path.iterdir()
            if fp.is_file() and fp.suffix.lower() == ".spold"
        ]

        for file_path in tqdm(file_paths):
            ecospold = pyecospold.parse_file_v2(file_path)
            local_data.append(
                {
                    "path": str(file_path),
                    "filename": file_path.name,
                    "activity_name": ecospold.activityDataset.activityDescription.activity[  # NOQA E501
                        0
                    ].activityNames[
                        0
                    ],
                    "reference_product": get_rp_text(
                        ecospold.activityDataset.flowData.intermediateExchanges
                    ),
                    "geography": ecospold.activityDataset.activityDescription.geography[
                        0
                    ].shortNames[0],
                }
            )

        return local_data
