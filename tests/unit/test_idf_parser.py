"""IDF 解析器单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.exceptions import IDFParseError
from src.core.idf.models import IDFObject
from src.core.idf.parser import IDFParser
from src.core.idf.serializer import IDFSerializer

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

IDF_FIXTURES = [
    "1ZoneUncontrolled.idf",
    "1ZoneDataCenterCRAC_wPumpedDXCoolingCoil.idf",
    "1ZoneEvapCooler.idf",
]


@pytest.fixture
def parser() -> IDFParser:
    return IDFParser()


@pytest.fixture
def serializer() -> IDFSerializer:
    return IDFSerializer()


def _available_idfs() -> list[Path]:
    return [FIXTURES / name for name in IDF_FIXTURES if (FIXTURES / name).exists()]


def test_parse_empty_text(parser: IDFParser) -> None:
    doc = parser.parse_text("")
    assert doc.object_count() == 0
    assert doc.objects == []


def test_parse_simple_object(parser: IDFParser) -> None:
    text = "Material,\n    A,  !- Name\n    0.1;  !- Thickness\n"
    doc = parser.parse_text(text)
    assert doc.object_count() == 1
    obj = doc.objects[0]
    assert obj.type_name == "Material"
    assert obj.fields == ["A", "0.1"]
    assert obj.field_names == ["Name", "Thickness"]
    assert obj.line_start == 1
    assert obj.line_end == 3


def test_parse_quoted_string(parser: IDFParser) -> None:
    text = 'Schedule:Compact,\n    "My Schedule",  !- Name\n    "Fraction",  !- Schedule Type Limits Name\n    4;  !- Number of Field Sets\n'
    doc = parser.parse_text(text)
    obj = doc.objects[0]
    assert obj.fields[0] == '"My Schedule"'
    assert obj.fields[1] == '"Fraction"'
    assert obj.fields[2] == "4"


def test_parse_comments_and_blanks(parser: IDFParser) -> None:
    text = "! header comment\n\nMaterial,\n    A;\n\n! trailing\n"
    doc = parser.parse_text(text)
    assert doc.header_comments == ["! header comment"]
    assert doc.object_count() == 1
    assert doc.objects[0].type_name == "Material"


def test_parse_line_numbers(parser: IDFParser) -> None:
    text = "\n\nMaterial,\n    A,\n    0.1;\n"
    doc = parser.parse_text(text)
    obj = doc.objects[0]
    assert obj.line_start == 3
    assert obj.line_end == 5


def test_parse_file_not_found(parser: IDFParser) -> None:
    with pytest.raises(IDFParseError):
        parser.parse_file("/nonexistent/path/file.idf")


def test_get_objects_by_type(parser: IDFParser) -> None:
    text = "Material,\n    A;\nMaterial,\n    B;\nZone,\n    Z1;\n"
    doc = parser.parse_text(text)
    assert len(doc.get_objects_by_type("Material")) == 2
    assert len(doc.get_objects_by_type("material")) == 2
    assert len(doc.get_objects_by_type("Zone")) == 1
    assert "Material" in doc.get_object_types()


@pytest.mark.parametrize("idf_path", _available_idfs(), ids=lambda p: p.name)
def test_roundtrip(parser: IDFParser, serializer: IDFSerializer, idf_path: Path) -> None:
    """往返测试：parse(serialize(parse(text))) 对象集合等价。"""
    original = parser.parse_file(idf_path)
    serialized = serializer.serialize(original)
    reparsed = parser.parse_text(serialized, str(idf_path))
    assert reparsed.object_count() == original.object_count()
    for orig, rep in zip(original.objects, reparsed.objects, strict=True):
        assert orig.type_name == rep.type_name
        assert orig.fields == rep.fields


@pytest.mark.parametrize("idf_path", _available_idfs(), ids=lambda p: p.name)
def test_parse_real_idf(parser: IDFParser, idf_path: Path) -> None:
    """真实 IDF 冒烟解析。"""
    doc = parser.parse_file(idf_path)
    assert doc.object_count() > 0
    assert all(isinstance(o, IDFObject) for o in doc.objects)


def test_object_get_set_field() -> None:
    obj = IDFObject(type_name="Material", fields=["A"])
    assert obj.get_field(0) == "A"
    assert obj.get_field(5) == ""
    obj.set_field(2, "X")
    assert obj.fields == ["A", "", "X"]
    assert obj.name() == "A"
