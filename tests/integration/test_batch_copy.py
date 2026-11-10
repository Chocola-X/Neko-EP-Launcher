"""批量复制、原子粘贴和错误高亮交互回归。"""

from pathlib import Path

import pytest
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from src.app import Application
from src.core.idd.models import FieldDef, IDDDocument, ObjectDef
from src.services.idf_service import IDFService


@pytest.fixture
def windows(qtbot, tmp_path):
    container = Application(tmp_path / "config.json", tmp_path / "runs")
    result = []
    for name, text in [
        ("a", "Zone,A,45,1,2;\nZone,B,90,3,4;\nZone,C,0,5,6;"),
        ("b", "Zone,Target,0,0,0;"),
    ]:
        path = tmp_path / f"{name}.idf"
        path.write_text(text)
        win = container.create_window(path)
        qtbot.addWidget(win, before_close_func=lambda w: setattr(w, "_modified", False))
        result.append(win)
    yield result
    QApplication.clipboard().clear()


def test_ctrl_shift_copy_paste_and_undo(windows, qtbot):
    source, target = windows
    tree = source._tree._tree
    parent = source._tree._model.item(0)
    tree.setFocus()
    for row, modifier in [(0, Qt.NoModifier), (2, Qt.ControlModifier)]:
        rect = tree.visualRect(parent.child(row).index())
        qtbot.mouseClick(tree.viewport(), Qt.LeftButton, modifier, rect.center())
    assert source._tree.selected_indices() == (0, 2)
    qtbot.keyClick(tree, Qt.Key_C, Qt.ControlModifier)
    assert len(source._idf_service.parse(QApplication.clipboard().text()).objects) == 2
    target._paste_object_from_clipboard()
    assert [o.name() for o in target._doc.objects] == ["Target", "A", "C"]
    assert target._tree._model.item(0).rowCount() == 3
    target._editor.undo()
    target._auto_sync()
    assert [o.name() for o in target._doc.objects] == ["Target"]
    qtbot.mouseClick(
        tree.viewport(),
        Qt.LeftButton,
        Qt.NoModifier,
        tree.visualRect(parent.child(0).index()).center(),
    )
    qtbot.mouseClick(
        tree.viewport(),
        Qt.LeftButton,
        Qt.ShiftModifier,
        tree.visualRect(parent.child(2).index()).center(),
    )
    assert source._tree.selected_indices() == (0, 1, 2)


def test_group_selection_and_repeat_paste(windows):
    source, target = windows
    source._tree._tree.setCurrentIndex(source._tree._model.item(0).index())
    source._tree.request_copy()
    target._paste_object_from_clipboard()
    target._paste_object_from_clipboard()
    assert len(target._doc.objects) == 4
    assert target._tree._model.item(0).rowCount() == 4


def test_selected_attributes_keep_positions_and_save(windows):
    source, target = windows
    table = source._field_panel._table
    flags = QItemSelectionModel.Select | QItemSelectionModel.Rows
    table.selectionModel().select(table.model().index(1, 1), flags)
    table.selectionModel().select(table.model().index(3, 1), flags)
    source._field_panel._btn_copy_selected.click()
    target._field_panel._btn_paste_params.click()
    assert target._doc.objects[0].fields == ["Target", "45", "0", "2"]
    target._save_file()
    assert target._idf_service.open(target._current_path).objects[0].fields == [
        "Target",
        "45",
        "0",
        "2",
    ]


def test_conflict_and_invalid_source_preserve_model(windows, monkeypatch):
    _source, target = windows
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[2]))
    baseline = target._editor.toPlainText()
    QApplication.clipboard().setText("Zone,New,0;Zone,Target,90;")
    target._paste_object_from_clipboard()
    assert messages and target._editor.toPlainText() == baseline
    assert len(target._doc.objects) == 1
    target._editor.setPlainText("Zone,Incomplete")
    QApplication.clipboard().setText("Zone,New,0;")
    target._paste_object_from_clipboard()
    assert target._editor.toPlainText() == "Zone,Incomplete"


def test_validation_highlights_and_clears(windows, tmp_path: Path):
    source, _ = windows
    path = tmp_path / "test.idd"
    path.write_text(
        "Zone,\n A1, \\field Name\n N1; \\field Angle\n \\type real\n \\minimum 0\n \\maximum 360\n"
    )
    source._idd_service.load(path)
    source._auto_sync()
    source._edit_field(1, "bad")
    item = source._tree._model.item(0).child(0)
    assert "期望数值" in item.toolTip()
    editor = source._field_panel._table.cellWidget(1, 2)
    assert "期望数值" in editor.toolTip()
    assert (
        editor.palette().color(QPalette.Text).red() > editor.palette().color(QPalette.Text).green()
    )
    source._edit_field(1, "30")
    assert source._tree._model.item(0).child(0).toolTip() == ""
    assert "期望数值" not in editor.toolTip()
    assert source._doc.objects[0].get_field(1) == "30"


def test_dependency_closure_cycles_extensible_and_missing():
    svc = IDFService()
    idd = IDDDocument()
    idd.add(
        ObjectDef(
            "Layer",
            fields=[
                FieldDef("Name", references=["Layers"]),
                FieldDef("Other", object_lists=["Layers"]),
            ],
        )
    )
    idd.add(
        ObjectDef(
            "Construction",
            fields=[
                FieldDef("Name"),
                FieldDef("Layer", object_lists=["Layers"], begin_extensible=True),
            ],
            extensible_size=1,
        )
    )
    doc = svc.parse("Layer,A,B;Layer,B,A;Construction,C,A,B;")
    assert len(svc.collect_objects(doc, (2,), idd)) == 3
    doc.objects[0].set_field(1, "Missing")
    with pytest.raises(ValueError, match="缺失"):
        svc.collect_objects(doc, (2,), idd)
    with pytest.raises(ValueError):
        svc.collect_objects(doc, (-1,), idd)


def test_atomic_field_updates_and_quoted_values():
    svc = IDFService()
    doc = svc.parse("Zone,A,0,0;")
    with pytest.raises(ValueError):
        svc.update_fields(doc, 0, ((1, "30"), (-1, "bad")))
    assert doc.objects[0].fields == ["A", "0", "0"]
    encoded = svc.encode_fields(doc.objects[0], (1, 2))
    assert svc.decode_fields(encoded, "zone") == ((1, "0"), (2, "0"))
    with pytest.raises(ValueError, match="同类型"):
        svc.decode_fields(encoded, "Material")
    with pytest.raises(ValueError):
        svc.decode_fields('{"type":"Zone","fields":[[-1,"bad"]]}', "Zone")


def test_choice_and_reference_errors_clear(windows, tmp_path):
    source, _ = windows
    metadata = tmp_path / "references.idd"
    metadata.write_text(
        "Zone,\n A1, \\field Name\n \\reference Zones\n"
        " A2, \\field Mode\n \\type choice\n \\key One\n \\key Two\n"
        " A3; \\field Other Zone\n \\type object-list\n \\object-list Zones\n"
    )
    source._idd_service.load(metadata)
    source._auto_sync()
    source._edit_field(1, "one")
    source._edit_field(2, "Unknown")
    assert "未找到" in source._field_panel._table.cellWidget(2, 2).toolTip()
    assert "不在选项" not in source._field_panel._table.cellWidget(1, 2).toolTip()
    source._edit_field(2, "b")
    assert "未找到" not in source._field_panel._table.cellWidget(2, 2).toolTip()


def test_json_object_and_paste_atomic_conflict():
    svc = IDFService()
    assert svc.parse_objects('{"type":"Zone","fields":["A","0"]}')[0].name() == "A"
    with pytest.raises(ValueError):
        svc.parse_objects('{"type":"Zone","fields":[2]}')
    doc = svc.parse("Zone,A,0;")
    with pytest.raises(ValueError):
        svc.paste_objects(doc, svc.parse_objects("Zone,B,0;Zone,a,45;"))
    assert len(doc.objects) == 1
    assert svc.paste_objects(doc, svc.parse_objects("Zone,A,0;")) == 0


def test_idd_named_namespace_conflicts_and_unnamed_objects():
    svc = IDFService()
    idd = IDDDocument()
    for type_name in ("Material", "WindowMaterial:Glazing"):
        idd.add(ObjectDef(type_name, fields=[FieldDef("Name", references=["Materials"])]))
    idd.add(ObjectDef("Output:Variable", fields=[FieldDef("Key Value")]))
    target = svc.parse("Material,Glass;Output:Variable,*,Temperature,Hourly;")
    with pytest.raises(ValueError, match="冲突"):
        svc.paste_objects(target, svc.parse_objects("WindowMaterial:Glazing,glass;"), idd)
    assert (
        svc.paste_objects(target, svc.parse_objects("Output:Variable,*,Humidity,Hourly;"), idd) == 1
    )
