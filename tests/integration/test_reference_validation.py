"""官方示例误报回归：对象类型引用、自动数值关键字、缓存与属性下拉。"""

import hashlib
import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QComboBox

from src.core.idd.parser import IDDParser
from src.services.idd_service import IDDService
from src.services.idf_service import IDFService
from src.ui.tree.field_panel import FieldEditPanel

METADATA = """Fan:ConstantVolume,
 A1; \\field Name
 \\reference FanNames
 \\reference-class-name FanTypes
Branch,
 A1, \\field Name
 A2, \\field Component Type
 \\type object-list
 \\object-list FanTypes
 A3; \\field Component Name
 \\type object-list
 \\object-list FanNames
"""


def test_type_references_do_not_require_instances() -> None:
    service = IDFService()
    idd = IDDParser().parse_text(METADATA)
    doc = service.parse("Branch,B,fan:constantvolume,Missing;")
    issues = service.validate(doc, idd)
    assert len(issues) == 1
    assert issues[0].field_name == "Component Name"
    doc.objects[0].set_field(1, "Fan:Misspelled")
    assert {issue.field_index for issue in service.validate(doc, idd)} == {1, 2}


def test_dependency_copy_ignores_type_reference_and_collects_named_instance() -> None:
    service = IDFService()
    idd = IDDParser().parse_text(METADATA)
    doc = service.parse(
        "Fan:ConstantVolume,F1;Fan:ConstantVolume,F2;Branch,B,Fan:ConstantVolume,F1;"
    )
    assert not service.validate(doc, idd)
    assert [obj.name() for obj in service.collect_objects(doc, (2,), idd)] == ["F1", "B"]
    doc.objects[2].set_field(2, "Missing")
    with pytest.raises(ValueError, match="缺失"):
        service.collect_objects(doc, (2,), idd)


@pytest.mark.parametrize("capability", ["autosizable", "autocalculatable"])
@pytest.mark.parametrize("value", ["Autosize", "AUTOCALCULATE"])
def test_numeric_auto_aliases_and_real_invalid_values(capability: str, value: str) -> None:
    idd = IDDParser().parse_text(
        f"PlantLoop,\n A1, \\field Name\n N1; \\field Volume\n \\type real\n \\{capability}\n"
    )
    service = IDFService()
    assert not service.validate(service.parse(f"PlantLoop,P,{value};"), idd)
    assert service.validate(service.parse("PlantLoop,P,Automatic;"), idd)
    plain = IDDParser().parse_text("Plain,\n N1; \\field Numeric\n \\type real\n")
    assert service.validate(service.parse(f"Plain,{value};"), plain)


def test_cache_invalidates_old_metadata_and_preserves_class_references(tmp_path: Path) -> None:
    path = tmp_path / "test.idd"
    path.write_text(METADATA)
    cache = tmp_path / "cache.json"
    old_key = "v2:" + hashlib.sha256(path.read_bytes()).hexdigest()
    cache.write_text(json.dumps({old_key: {"version": "obsolete", "objects": []}}))
    service = IDDService(cache)
    document = service.load(path)
    assert document.get("Fan:ConstantVolume").fields[0].class_references == ["FanTypes"]
    reloaded = IDDService(cache)
    assert reloaded.load(path) == document
    assert reloaded.get_reference_names("FanTypes") == ["Fan:ConstantVolume"]
    assert reloaded.get_reference_names("FanNames") == []


def test_type_dropdown_uses_idd_classes_without_document_instances(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "test.idd"
    path.write_text(METADATA)
    metadata = IDDService()
    metadata.load(path)
    document = IDFService().parse("Branch,B,Fan:ConstantVolume,Missing;")
    panel = FieldEditPanel(metadata)
    qtbot.addWidget(panel)
    panel.set_document(document)
    panel.set_object(document.objects[0])
    editor = panel._table.cellWidget(1, 2)
    assert isinstance(editor, QComboBox)
    assert editor.findText("Fan:ConstantVolume") >= 0
    # 实例引用下拉不能把类名混作实例名称。
    assert panel._table.cellWidget(2, 2).findText("Fan:ConstantVolume") == -1
