"""IDD 解析器单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.idd.models import IDDDocument
from src.core.idd.parser import IDDParser

EP_DIR = Path(
    "/run/media/chocola/DATA/Building_energy-saving_shading/"
    "EnergyPlus-9.4.0-998c4b761e-Linux-Ubuntu18.04-x86_64"
)
IDD_PATH = EP_DIR / "Energy+.idd"


@pytest.fixture
def idd_doc() -> IDDDocument:
    if not IDD_PATH.exists():
        pytest.skip("Energy+.idd 不存在")
    return IDDParser().parse_file(IDD_PATH)


def test_parse_minimal_idd() -> None:
    text = """!IDD_Version 9.4.0
\\group Test Group
Material,
  A1 , \\field Name
       \\type alpha
       \\required-field
  N1 ; \\field Thickness
       \\type real
       \\units m
"""
    doc = IDDParser().parse_text(text)
    assert doc.version == "9.4.0"
    assert doc.object_count() == 1
    obj = doc.get("Material")
    assert obj is not None
    assert obj.group == "Test Group"
    assert obj.field_count() == 2
    assert obj.fields[0].name == "Name"
    assert obj.fields[0].type == "alpha"
    assert obj.fields[0].required is True
    assert obj.fields[1].name == "Thickness"
    assert obj.fields[1].type == "real"
    assert obj.fields[1].units == "m"


def test_parse_choice_field() -> None:
    text = """\\group G
Material,
  A1 , \\field Roughness
       \\type choice
       \\key Rough
       \\key Smooth
  N1 ; \\field Thickness
       \\type real
"""
    doc = IDDParser().parse_text(text)
    obj = doc.get("Material")
    assert obj.fields[0].type == "choice"
    assert obj.fields[0].key_choices == ["Rough", "Smooth"]


def test_parse_object_list_field() -> None:
    text = """\\group G
Construction,
  A1 , \\field Name
       \\type alpha
       \\reference ConstructionName
  A2 ; \\field Layer 1
       \\type object-list
       \\object-list MaterialName
"""
    doc = IDDParser().parse_text(text)
    obj = doc.get("Construction")
    assert obj.fields[1].type == "object-list"
    assert obj.fields[1].object_lists == ["MaterialName"]
    assert obj.fields[0].references == ["ConstructionName"]


def test_parse_default_and_bounds() -> None:
    text = """\\group G
Material,
  A1 , \\field Name
       \\type alpha
  N1 ; \\field Value
       \\type real
       \\default 0.7
       \\minimum 0
       \\maximum 1
"""
    doc = IDDParser().parse_text(text)
    f = doc.get("Material").fields[1]
    assert f.default == "0.7"
    assert f.minimum == 0.0
    assert f.maximum == 1.0


def test_parse_multiple_objects() -> None:
    text = """\\group G
Material,
  A1 ; \\field Name
Material:NoMass,
  A1 ; \\field Name
"""
    doc = IDDParser().parse_text(text)
    assert doc.object_count() == 2
    assert doc.get("Material") is not None
    assert doc.get("Material:NoMass") is not None


def test_parse_extensible() -> None:
    text = """\\group G
Building,
  A1 , \\field Name
       \\begin-extensible
       \\type alpha
  A2 ; \\field Field2
       \\type alpha
"""
    doc = IDDParser().parse_text(text)
    obj = doc.get("Building")
    assert obj.fields[0].begin_extensible is True
    assert obj.extensible_size == 2


@pytest.mark.skipif(not IDD_PATH.exists(), reason="Energy+.idd 不存在")
def test_real_idd_smoke(idd_doc: IDDDocument) -> None:
    """真实 IDD 冒烟解析。"""
    assert idd_doc.object_count() > 500
    assert idd_doc.version.startswith("9.")


@pytest.mark.skipif(not IDD_PATH.exists(), reason="Energy+.idd 不存在")
def test_real_idd_key_objects(idd_doc: IDDDocument) -> None:
    """断言关键对象存在且字段数合理。"""
    for name in ["Material", "Material:NoMass", "Zone", "Building", "Construction"]:
        obj = idd_doc.get(name)
        assert obj is not None, f"缺少对象: {name}"
        assert obj.field_count() > 0, f"{name} 字段数为 0"


@pytest.mark.skipif(not IDD_PATH.exists(), reason="Energy+.idd 不存在")
def test_real_idd_material_fields(idd_doc: IDDDocument) -> None:
    """对照 Material 对象字段（依据 R-2）。"""
    obj = idd_doc.get("Material")
    assert obj.fields[0].name == "Name"
    assert obj.fields[0].required is True
    assert obj.fields[1].name == "Roughness"
    assert obj.fields[1].type == "choice"
    assert "VeryRough" in obj.fields[1].key_choices
    assert obj.fields[2].name == "Thickness"
    assert obj.fields[2].units == "m"
    assert obj.fields[2].type == "real"


@pytest.mark.skipif(not IDD_PATH.exists(), reason="Energy+.idd 不存在")
def test_real_idd_zone_fields(idd_doc: IDDDocument) -> None:
    """对照 Zone 对象字段。"""
    obj = idd_doc.get("Zone")
    assert obj.fields[0].name == "Name"
    assert obj.fields[0].required is True
