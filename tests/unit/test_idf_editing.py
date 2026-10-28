"""真实示例与保真编辑回归测试。"""

from pathlib import Path

import pytest

from src.core.exceptions import IDFParseError
from src.core.idf.parser import IDFParser
from src.core.idf.serializer import IDFSerializer


@pytest.mark.parametrize(
    "path", sorted((Path(__file__).parents[1] / "fixtures").glob("*.idf")), ids=lambda p: p.name
)
def test_official_examples_preserve_every_character(path: Path) -> None:
    parser = IDFParser()
    serializer = IDFSerializer()
    doc = parser.parse_file(path)
    assert serializer.serialize(doc) == doc.raw_text
    target = next(o for o in doc.objects if o.fields)
    target.set_field(0, "RegressionName")
    output = serializer.serialize(doc)
    reparsed = parser.parse_text(output)
    assert [(o.type_name, o.fields) for o in reparsed.objects] == [
        (o.type_name, o.fields) for o in doc.objects
    ]
    assert output.count("!") == doc.raw_text.count("!")


@pytest.mark.parametrize(
    "text", ["Zone, A", 'Zone, "unfinished;', "Zone, (1, 2;", "Zone, A);", ", A;"]
)
def test_incomplete_input_is_rejected(text: str) -> None:
    with pytest.raises(IDFParseError):
        IDFParser().parse_text(text)


def test_inline_objects_empty_and_quoted_fields() -> None:
    text = '! header\nZone, "a,b;!",, 1; Zone, B; ! trailing\n\n! end\n'
    doc = IDFParser().parse_text(text)
    assert len(doc.objects) == 2
    doc.objects[0].set_field(0, '"long new name"')
    doc.objects[0].set_field(1, "2")
    doc.objects[1].set_field(0, "C")
    out = IDFSerializer().serialize(doc)
    assert out == text.replace('"a,b;!",,', '"long new name",2,').replace("Zone, B;", "Zone, C;")


def test_remove_and_append_preserves_unrelated_comments() -> None:
    doc = IDFParser().parse_text("! header\nZone, A;\n! between\nZone, B;\n! end\n")
    doc.objects.pop(0)
    out = IDFSerializer().serialize(doc)
    assert "! between" in out and "! end" in out
    assert IDFParser().parse_text(out).objects[0].name() == "B"
