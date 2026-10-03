"""IDD 服务与 IDF 校验集成测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.idd.parser import IDDParser
from src.services.idd_service import IDDService
from src.services.idf_service import IDFService

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
EP_DIR = Path(
    "/run/media/chocola/DATA/Building_energy-saving_shading/"
    "EnergyPlus-9.4.0-998c4b761e-Linux-Ubuntu18.04-x86_64"
)
IDD_PATH = EP_DIR / "Energy+.idd"


def test_idd_service_cache_roundtrip(tmp_path: Path) -> None:
    if not IDD_PATH.exists():
        pytest.skip("Energy+.idd 不存在")
    cache = tmp_path / "idd_cache.json"
    svc1 = IDDService(cache)
    doc1 = svc1.load(IDD_PATH)
    assert doc1.object_count() > 0
    assert cache.exists()

    svc2 = IDDService(cache)
    doc2 = svc2.load(IDD_PATH)
    assert doc2.object_count() == doc1.object_count()
    assert doc2.version == doc1.version
    assert doc2.get("Material") is not None


def test_idd_service_get_object_def(tmp_path: Path) -> None:
    if not IDD_PATH.exists():
        pytest.skip("Energy+.idd 不存在")
    svc = IDDService(tmp_path / "cache.json")
    svc.load(IDD_PATH)
    obj = svc.get_object_def("Material")
    assert obj is not None
    assert obj.fields[0].name == "Name"


def test_idf_validate_required_field() -> None:
    idf_svc = IDFService()
    doc = idf_svc.parse("Material,\n    ,  !- Name\n    0.1;  !- Thickness\n")
    issues = idf_svc.validate(doc, None)
    assert len(issues) == 0


def test_idf_validate_with_idd() -> None:
    if not IDD_PATH.exists():
        pytest.skip("Energy+.idd 不存在")
    idd = IDDParser().parse_file(IDD_PATH)
    idf_svc = IDFService()
    doc = idf_svc.parse(
        "Material,\n    MyMat,  !- Name\n    BadRoughness,  !- Roughness\n    0.1;  !- Thickness\n"
    )
    issues = idf_svc.validate(doc, idd)
    roughness_issues = [i for i in issues if i.field_name == "Roughness"]
    assert len(roughness_issues) == 1
    assert "不在选项中" in roughness_issues[0].message


def test_idf_validate_type_mismatch() -> None:
    if not IDD_PATH.exists():
        pytest.skip("Energy+.idd 不存在")
    idd = IDDParser().parse_file(IDD_PATH)
    idf_svc = IDFService()
    doc = idf_svc.parse(
        "Material,\n    M,  !- Name\n    Rough,  !- Roughness\n    abc;  !- Thickness\n"
    )
    issues = idf_svc.validate(doc, idd)
    thickness_issues = [i for i in issues if i.field_name == "Thickness"]
    assert len(thickness_issues) == 1
    assert thickness_issues[0].severity == "error"


def test_idf_validate_real_idf_no_errors() -> None:
    idf_path = FIXTURES / "1ZoneUncontrolled.idf"
    if not idf_path.exists():
        pytest.skip("fixture 缺失")
    if not IDD_PATH.exists():
        pytest.skip("Energy+.idd 不存在")
    idd = IDDParser().parse_file(IDD_PATH)
    idf_svc = IDFService()
    doc = idf_svc.open(idf_path)
    issues = idf_svc.validate(doc, idd)
    errors = [i for i in issues if i.severity == "error"]
    assert len(errors) == 0
