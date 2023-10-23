import shutil
from pathlib import Path

from ecoinvent_interface.spold_versions import fix_version_meta as meta
from ecoinvent_interface.spold_versions import fix_version_upr as upr
from ecoinvent_interface.spold_versions import major_minor_from_string as mm

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_major_minor_from_string():
    assert mm("3.9.1") == (3, 9)
    assert mm("3.9") == (3, 9)
    assert mm("3.8") == (3, 8)
    assert mm("3.10") == (3, 10)


def test_fix_version_upr(tmp_path):
    shutil.copy(FIXTURES_DIR / "dataset.spold", tmp_path / "dataset.spold")
    upr(tmp_path / "dataset.spold", 3, 12)
    text_given = open(tmp_path / "dataset.spold", encoding="utf-8").readlines()[1:]
    text_expected = open(
        FIXTURES_DIR / "dataset-fixed.spold", encoding="utf-8"
    ).readlines()[1:]
    assert text_given == text_expected


def test_fix_version_meta(tmp_path):
    shutil.copy(FIXTURES_DIR / "Compartments.xml", tmp_path / "Compartments.xml")
    meta(tmp_path / "Compartments.xml", 3, 12)
    text_given = open(tmp_path / "Compartments.xml", encoding="utf-8").readlines()[1:]
    text_expected = open(
        FIXTURES_DIR / "Compartments-fixed.xml", encoding="utf-8"
    ).readlines()[1:]
    assert text_given == text_expected
