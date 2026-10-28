"""原生主题、真实属性输入和焦点保持回归。"""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QLineEdit

from src.app import Application
from src.ui.main_window import MainWindow
from src.ui.theme import apply_theme


@pytest.fixture
def window(qtbot, tmp_path: Path):
    container = Application(tmp_path / "config.json", tmp_path / "runs")
    window = MainWindow(
        container.run_manager,
        container.idf_service,
        container.config_service,
        container.idd_service,
    )
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "_modified", False))
    window.show()
    path = tmp_path / "input.idf"
    path.write_text("! comment\nZone, Z1, 0;\nZone, Z2, 90;\n")
    window._open_file(str(path))
    yield window
    window._modified = False


def test_open_highlight_keeps_properties_editable(window, qtbot) -> None:
    qtbot.wait(700)
    assert window._field_panel.isEnabled()
    assert not window._modified
    assert not window._sync_timer.isActive()
    assert window._field_panel._table.rowCount() == 2


def test_type_multiple_fields_then_save_reopen(window, qtbot) -> None:
    panel = window._field_panel
    first = panel._table.cellWidget(0, 2)
    second = panel._table.cellWidget(1, 2)
    assert isinstance(first, QLineEdit)
    qtbot.mouseClick(first, Qt.LeftButton)
    first.selectAll()
    qtbot.keyClicks(first, "New Zone")
    qtbot.keyClick(first, Qt.Key_Return)
    assert panel._table.cellWidget(0, 2) is first
    assert panel.isEnabled()
    assert window._doc.objects[0].name() == "New Zone"
    assert first.hasFocus()
    qtbot.mouseClick(second, Qt.LeftButton)
    second.selectAll()
    qtbot.keyClicks(second, "45")
    # QAction 触发保存，输入框尚未失焦也必须提交。
    window._act_save.trigger()
    assert not window._modified
    document = window._idf_service.open(window._current_path)
    assert document.objects[0].fields == ["New Zone", "45"]
    assert "! comment" in document.raw_text
    assert window._doc.objects[0].fields == document.objects[0].fields


def test_object_selection_survives_field_edit(window, qtbot) -> None:
    window._on_object_selected(window._doc.objects[1])
    field = window._field_panel._table.cellWidget(0, 2)
    qtbot.mouseClick(field, Qt.LeftButton)
    field.selectAll()
    qtbot.keyClicks(field, "Second")
    qtbot.keyClick(field, Qt.Key_Return)
    qtbot.wait(700)
    assert window._selected_object_index == 1
    assert window._field_panel._name_label.text() == "Second"
    assert window._doc.objects[0].name() == "Z1"
    assert window._field_panel.isEnabled()


def test_theme_roundtrip_restores_native(qtbot) -> None:
    app = QApplication.instance()
    apply_theme("system")
    original_style = app.style().objectName()
    original_palette = QPalette(app.palette())
    apply_theme("dark")
    assert app.palette().color(QPalette.Window).lightness() < 100
    apply_theme("system")
    assert app.style().objectName() == original_style
    assert app.palette() == original_palette
    assert app.styleSheet() == ""


def test_tree_click_commits_pending_without_losing_target(window, qtbot) -> None:
    field = window._field_panel._table.cellWidget(0, 2)
    qtbot.mouseClick(field, Qt.LeftButton)
    field.selectAll()
    qtbot.keyClicks(field, "First changed")
    child = window._tree._model.item(0).child(1)
    index = child.index()
    rect = window._tree._tree.visualRect(index)
    qtbot.mouseClick(window._tree._tree.viewport(), Qt.LeftButton, pos=rect.center())
    assert window._doc.objects[0].name() == "First changed"
    assert window._selected_object_index == 1
    assert window._field_panel._name_label.text() == "Z2"


def test_source_error_then_undo_restores_property_editing(window, qtbot) -> None:
    original = window._editor.toPlainText()
    window._editor_tabs.setCurrentWidget(window._editor)
    window._editor.setFocus()
    window._editor.setPlainText("Zone, incomplete")
    qtbot.wait(700)
    assert not window._field_panel.isEnabled()
    window._editor.setPlainText(original)
    qtbot.waitUntil(lambda: window._field_panel.isEnabled(), timeout=2000)


def test_choice_editor_keeps_focus_until_commit(window, qtbot, tmp_path) -> None:
    from PySide6.QtWidgets import QComboBox

    metadata = tmp_path / "test.idd"
    metadata.write_text(
        "Zone,\n A1, \\field Name\n A2; \\field Mode\n \\type choice\n \\key One\n \\key Two\n"
    )
    window._idd_service.load(metadata)
    window._auto_sync()
    editor = window._field_panel._table.cellWidget(1, 2)
    assert isinstance(editor, QComboBox)
    editor.setFocus()
    editor.lineEdit().selectAll()
    qtbot.keyClicks(editor.lineEdit(), "Two")
    assert window._doc.objects[0].get_field(1) == "0"
    qtbot.keyClick(editor.lineEdit(), Qt.Key_Return)
    assert window._doc.objects[0].get_field(1) == "Two"
    assert window._field_panel._table.cellWidget(1, 2) is editor


def test_field_structure_and_delimiter_value(window, qtbot) -> None:
    service = window._idf_service
    service.update_field(window._doc, 0, 0, "Name, with comma")
    window._on_object_changed(window._doc.objects[0])
    assert window._doc.objects[0].name() == '"Name, with comma"'
    assert window._field_panel._table.cellWidget(0, 2).text() == '"Name, with comma"'
    before = len(window._doc.objects[0].fields)
    window._resize_fields(True)
    assert len(window._doc.objects[0].fields) == before + 1
    window._resize_fields(False)
    assert len(window._doc.objects[0].fields) == before
    with pytest.raises(ValueError):
        service.update_field(window._doc, 0, -1, "x")
    with pytest.raises(ValueError):
        service.update_field(window._doc, 0, 0, 'bad, "quote')
