"""大批校验信息的可缩放窗口与入口回归。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from src.app import Application
from src.core.idf.models import ValidationIssue
from src.ui.dialogs.validation_dialog import ValidationDialog
from src.ui.main_window import MainWindow


def test_large_report_resize_scroll_and_copy(qtbot) -> None:
    issues = [
        ValidationIssue(
            "error", f"完整问题 {i}: " + "字段说明" * 60, "Material", f"材料 {i}", 2, "Thickness"
        )
        for i in range(100)
    ]
    dialog = ValidationDialog(issues, "发现 100 个问题")
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    assert dialog.isSizeGripEnabled()
    assert dialog.windowFlags() & Qt.WindowMaximizeButtonHint
    initial = dialog._text.size()
    dialog.resize(1200, 800)
    qtbot.waitUntil(lambda: dialog._text.width() > initial.width())
    assert dialog._text.height() > initial.height()
    assert dialog._text.isReadOnly()
    assert dialog._text.verticalScrollBar().maximum() > 0
    assert "完整问题 99" in dialog._text.toPlainText()
    button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "复制完整报告")
    qtbot.mouseClick(button, Qt.LeftButton)
    assert QApplication.clipboard().text() == dialog._text.toPlainText()


def test_validation_entry_uses_resizable_dialog(qtbot, tmp_path, monkeypatch) -> None:
    shown = []
    monkeypatch.setattr(
        ValidationDialog, "exec", lambda self: shown.append(self._text.toPlainText()) or 0
    )
    app = Application(tmp_path / "config.json", tmp_path / "runs")
    window = MainWindow(app.run_manager, app.idf_service, app.config_service, app.idd_service)
    qtbot.addWidget(window, before_close_func=lambda widget: setattr(widget, "_modified", False))
    window._editor.setPlainText("Zone, A;")
    window._validate_idf()
    assert "语法正确" in shown[-1] and "IDD" in shown[-1]
    window._editor.setPlainText("Zone, incomplete")
    window._validate_idf()
    assert "校验失败" in shown[-1]
