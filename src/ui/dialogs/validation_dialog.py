"""可调整大小的 IDF 校验结果窗口。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.idf.models import ValidationIssue


class ValidationDialog(QDialog):
    """直接展示完整校验信息，支持拖动缩放、最大化和复制报告。"""

    def __init__(
        self,
        issues: list[ValidationIssue],
        summary: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("IDF 校验结果")
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setSizeGripEnabled(True)
        self.setMinimumSize(520, 320)
        self.resize(960, 600)

        layout = QVBoxLayout(self)
        label = QLabel(summary)
        label.setWordWrap(True)
        label.setTextFormat(Qt.PlainText)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(label)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setAccessibleName("完整 IDF 校验报告")
        paragraphs = [summary]
        for number, issue in enumerate(issues, 1):
            severity = {"error": "错误", "warning": "警告"}.get(issue.severity, issue.severity)
            location = " / ".join(v for v in (issue.object_type, issue.object_name) if v)
            field = issue.field_name or (
                f"字段 {issue.field_index + 1}" if issue.field_index >= 0 else "对象级"
            )
            paragraphs.append(f"{number}. [{severity}] {location}\n{field}\n{issue.message}")
        self._text.setPlainText("\n\n".join(paragraphs))
        layout.addWidget(self._text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        copy_button = QPushButton("复制完整报告")
        copy_button.clicked.connect(self._copy_report)
        buttons.addButton(copy_button, QDialogButtonBox.ActionRole)
        layout.addWidget(buttons)

    def _copy_report(self) -> None:
        QApplication.clipboard().setText(self._text.toPlainText())
