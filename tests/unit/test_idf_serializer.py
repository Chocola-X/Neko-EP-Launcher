"""IDF 序列化器单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.idf.models import IDFDocument, IDFObject
from src.core.idf.parser import IDFParser
from src.core.idf.serializer import IDFSerializer

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def parser() -> IDFParser:
    return IDFParser()


@pytest.fixture
def serializer() -> IDFSerializer:
    return IDFSerializer()


def test_serialize_empty(serializer: IDFSerializer) -> None:
    doc = IDFDocument()
    assert serializer.serialize(doc) == ""


def test_serialize_preserves_format(serializer: IDFSerializer, parser: IDFParser) -> None:
    text = "Material,\n    A,  !- Name\n    0.1;  !- Thickness\n"
    doc = parser.parse_text(text)
    out = serializer.serialize(doc)
    assert "Material," in out
    assert "!- Name" in out
    assert "!- Thickness" in out


def test_serialize_field_change_preserves_comments(
    serializer: IDFSerializer, parser: IDFParser
) -> None:
    text = "Material,\n    A,  !- Name\n    0.1;  !- Thickness\n"
    doc = parser.parse_text(text)
    doc.objects[0].fields[1] = "0.2"
    out = serializer.serialize(doc)
    assert "0.2" in out
    assert "!- Thickness" in out
    assert "!- Name" in out


def test_serialize_object_no_raw_lines(serializer: IDFSerializer) -> None:
    obj = IDFObject(type_name="Zone", fields=["Z1"], field_names=["Name"])
    out = serializer.serialize_object(obj)
    assert "Zone" in out
    assert "Z1" in out


def test_serialize_object_empty_fields(serializer: IDFSerializer) -> None:
    obj = IDFObject(type_name="Building", fields=[])
    out = serializer.serialize_object(obj)
    assert out == "Building;"


def test_serialize_fallback_on_field_count_mismatch(
    serializer: IDFSerializer, parser: IDFParser
) -> None:
    text = "Material,\n    A,  !- Name\n    0.1;  !- Thickness\n"
    doc = parser.parse_text(text)
    doc.objects[0].fields.append("extra")
    doc.objects[0].field_names.append("Extra")
    out = serializer.serialize(doc)
    assert "extra" in out


def test_serialize_header_comments(serializer: IDFSerializer) -> None:
    doc = IDFDocument(header_comments=["! header 1", "! header 2"])
    out = serializer.serialize(doc)
    assert "! header 1" in out
    assert "! header 2" in out


def test_roundtrip_multiple_objects(serializer: IDFSerializer, parser: IDFParser) -> None:
    text = "Material,\n    A,\n    0.1;\n\nMaterial,\n    B,\n    0.2;\n\nZone,\n    Z1;\n"
    doc = parser.parse_text(text)
    out = serializer.serialize(doc)
    reparsed = parser.parse_text(out)
    assert reparsed.object_count() == 3
    assert reparsed.objects[0].fields == ["A", "0.1"]
    assert reparsed.objects[1].fields == ["B", "0.2"]
    assert reparsed.objects[2].fields == ["Z1"]


def test_serialize_quoted_string_preserved(serializer: IDFSerializer, parser: IDFParser) -> None:
    text = 'Schedule:Compact,\n    "My Sched",  !- Name\n    "Fraction";  !- Type\n'
    doc = parser.parse_text(text)
    out = serializer.serialize(doc)
    assert '"My Sched"' in out
    assert '"Fraction"' in out
    assert "!- Name" in out


def test_serialize_parenthesized_value(serializer: IDFSerializer, parser: IDFParser) -> None:
    text = "Curve:Biquadratic,\n    C1,  !- Name\n    0.1,  !- Coeff1\n    (0.2);  !- Coeff2\n"
    doc = parser.parse_text(text)
    out = serializer.serialize(doc)
    assert "(0.2)" in out


def test_format_object_with_and_without_field_names(serializer: IDFSerializer) -> None:
    obj1 = IDFObject(type_name="Zone", fields=["Z1", "0.5"], field_names=["Name", "Multiplier"])
    out1 = serializer.serialize_object(obj1)
    assert "!- Name" in out1
    obj2 = IDFObject(type_name="Zone", fields=["Z2", "1"], field_names=["", ""])
    out2 = serializer.serialize_object(obj2)
    assert "Z2" in out2


@pytest.mark.parametrize(
    "name",
    ["1ZoneUncontrolled.idf", "1ZoneDataCenterCRAC_wPumpedDXCoolingCoil.idf"],
)
def test_preserve_real_idf(serializer: IDFSerializer, parser: IDFParser, name: str) -> None:
    path = FIXTURES / name
    if not path.exists():
        pytest.skip(f"fixture 缺失: {name}")
    doc = parser.parse_file(path)
    out = serializer.serialize(doc)
    reparsed = parser.parse_text(out)
    assert reparsed.object_count() == doc.object_count()
