"""字段编辑面板。

显示选中对象的字段表格，支持增删字段。Phase 1 将基于 IDD 元数据升级为下拉、
单位、校验等。当前为 Phase 0 骨架，保留基础编辑能力。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.idf.models import IDFObject


class FieldEditPanel(QWidget):
    """字段编辑面板。

    Signals:
        fieldChanged(object, int, str): 字段变更。
        objectChanged(object): 对象变更。
    """

    fieldChanged = Signal(object, int, str)
    objectChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._obj: IDFObject | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        info_group = QGroupBox("对象信息")
        info_layout = QFormLayout(info_group)
        self._type_label = QLabel("-")
        self._type_label.setStyleSheet("font-weight: bold; color: #56B6C2;")
        self._name_label = QLabel("-")
        self._line_label = QLabel("-")
        info_layout.addRow("类型:", self._type_label)
        info_layout.addRow("名称:", self._name_label)
        info_layout.addRow("行号:", self._line_label)
        layout.addWidget(info_group)

        table_group = QGroupBox("字段")
        table_layout = QVBoxLayout(table_group)
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["#", "字段名", "值"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.itemChanged.connect(self._on_item_changed)
        table_layout.addWidget(self._table)
        layout.addWidget(table_group, 1)

        btn_layout = QHBoxLayout()
        self._btn_add = QPushButton("添加字段")
        self._btn_del = QPushButton("删除字段")
        self._btn_add.clicked.connect(self._add_field)
        self._btn_del.clicked.connect(self._del_field)
        btn_layout.addWidget(self._btn_add)
        btn_layout.addWidget(self._btn_del)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def set_object(self, obj: IDFObject | None) -> None:
        self._obj = obj
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        if obj is None:
            self._type_label.setText("-")
            self._name_label.setText("-")
            self._line_label.setText("-")
            self._table.blockSignals(False)
            return

        self._type_label.setText(obj.type_name)
        self._name_label.setText(obj.name() if obj.fields else "-")
        self._line_label.setText(f"{obj.line_start} - {obj.line_end}")

        self._table.setRowCount(len(obj.fields))
        for i, val in enumerate(obj.fields):
            fname = obj.field_names[i] if i < len(obj.field_names) else ""

            idx_item = QTableWidgetItem(str(i + 1))
            idx_item.setFlags(Qt.ItemIsEnabled)
            idx_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(i, 0, idx_item)

            name_item = QTableWidgetItem(fname)
            name_item.setFlags(Qt.ItemIsEnabled)
            self._table.setItem(i, 1, name_item)

            val_item = QTableWidgetItem(val)
            self._table.setItem(i, 2, val_item)
        self._table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._obj is None or item.column() != 2:
            return
        row = item.row()
        new_val = item.text()
        if row < len(self._obj.fields):
            self._obj.fields[row] = new_val
            self.fieldChanged.emit(self._obj, row, new_val)
            self.objectChanged.emit(self._obj)
            if row == 0:
                self._name_label.setText(new_val)

    def _add_field(self) -> None:
        if self._obj is None:
            return
        self._obj.fields.append("")
        self._obj.field_names.append("")
        self._obj.comments.append("")
        self.set_object(self._obj)
        self.objectChanged.emit(self._obj)

    def _del_field(self) -> None:
        if self._obj is None:
            return
        row = self._table.currentRow()
        if row < 0 or row >= len(self._obj.fields):
            return
        del self._obj.fields[row]
        if row < len(self._obj.field_names):
            del self._obj.field_names[row]
        if row < len(self._obj.comments):
            del self._obj.comments[row]
        self.set_object(self._obj)
        self.objectChanged.emit(self._obj)
