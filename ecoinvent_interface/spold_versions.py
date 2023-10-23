import os
from pathlib import Path
from typing import Tuple

from lxml import etree, objectify


def major_minor_from_string(version: str) -> Tuple[int, int]:
    sections = version.split(".")
    return int(sections[0]), int(sections[1])


def check_inputs(
    filepath: Path,
    major_version: int,
    minor_version: int,
) -> None:
    assert Path(filepath).is_file(), "Given path is not a file"
    assert os.access(filepath, os.R_OK), "Can't read given file"
    assert os.access(filepath, os.W_OK), "Can't write corrected file"
    assert major_version >= 3, "Invalid major version"
    assert minor_version >= 0, "Invalid minor version"


def fix_version_upr(
    filepath: Path,
    major_version: int,
    minor_version: int,
) -> None:
    check_inputs(
        filepath=filepath, major_version=major_version, minor_version=minor_version
    )
    data = objectify.parse(open(filepath, encoding="utf-8-sig")).getroot()
    if hasattr(data, "childActivityDataset"):
        ad = getattr(data, "childActivityDataset")
    else:
        ad = getattr(data, "activityDataset")

    fa = ad.administrativeInformation.fileAttributes
    fa.set("majorRelease", str(major_version))
    fa.set("minorRelease", str(minor_version))

    with open(filepath, "wb") as f:
        f.write(
            etree.tostring(
                data, encoding="utf-8", pretty_print=True, xml_declaration=True
            )
        )


def fix_version_meta(
    filepath: Path,
    major_version: int,
    minor_version: int,
) -> None:
    check_inputs(
        filepath=filepath, major_version=major_version, minor_version=minor_version
    )

    data = objectify.parse(open(filepath, encoding="utf-8-sig")).getroot()
    data.set("majorRelease", str(major_version))
    data.set("minorRelease", str(minor_version))

    with open(filepath, "wb") as f:
        f.write(
            etree.tostring(
                data, encoding="utf-8", pretty_print=True, xml_declaration=True
            )
        )
