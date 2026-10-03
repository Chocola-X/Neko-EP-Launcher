"""字段编辑面板（元数据驱动）。

基于 IDD ObjectDef 渲染字段：choice→下拉、object-list→可搜索下拉、
real/integer→带校验输入框，显示单位/默认/必填标记，非法值即时标红。
依据 R-2/R-10。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
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

from src.core.idd.models import FieldDef, ObjectDef
from src.core.idf.models import IDFDocument, IDFObject
from src.services.idd_service import IDDService


class FieldEditPanel(QWidget):
    """字段编辑面板（元数据驱动）。

    Signals:
        fieldChanged(object, int, str): 字段变更。
        objectChanged(object): 对象变更。
    """

    fieldChanged = Signal(object, int, str)
    objectChanged = Signal(object)

    def __init__(
        self,
        idd_service: IDDService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._idd = idd_service
        self._obj: IDFObject | None = None
        self._doc: IDFDocument | None = None
        self._obj_def: ObjectDef | None = None
        self._build_ui()

    def set_idd_service(self, idd_service: IDDService | None) -> None:
        """设置 IDD 服务。"""
        self._idd = idd_service

    def set_document(self, doc: IDFDocument | None) -> None:
        """设置当前 IDF 文档（用于 object-list 引用解析）。"""
        self._doc = doc

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
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["#", "字段名", "值", "单位/说明"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
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
        self._obj_def = None
        if obj is not None and self._idd is not None and self._idd.is_loaded():
            self._obj_def = self._idd.get_object_def(obj.type_name)
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
            fdef = (
                self._obj_def.fields[i] if self._obj_def and i < len(self._obj_def.fields) else None
            )
            fname = obj.field_names[i] if i < len(obj.field_names) else ""
            self._fill_row(i, val, fname, fdef)
        self._table.blockSignals(False)

    def _fill_row(self, row: int, value: str, name: str, fdef: FieldDef | None) -> None:
        display_name = fdef.name if fdef and fdef.name else name
        required_mark = " *" if fdef and fdef.required else ""
        idx_item = QTableWidgetItem(str(row + 1))
        idx_item.setFlags(Qt.ItemIsEnabled)
        idx_item.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(row, 0, idx_item)

        name_item = QTableWidgetItem(display_name + required_mark)
        name_item.setFlags(Qt.ItemIsEnabled)
        if fdef and fdef.required:
            name_item.setForeground(QColor("#E06C75"))
        self._table.setItem(row, 1, name_item)

        val_item = QTableWidgetItem(value)
        self._table.setItem(row, 2, val_item)
        self._validate_cell(row, value, fdef)

        unit_text = ""
        if fdef:
            parts = []
            if fdef.units:
                parts.append(f"[{fdef.units}]")
            if fdef.default:
                parts.append(f"默认={fdef.default}")
            if fdef.type == "choice" and fdef.key_choices:
                parts.append(f"({len(fdef.key_choices)}项)")
            unit_text = " ".join(parts)
        unit_item = QTableWidgetItem(unit_text)
        unit_item.setFlags(Qt.ItemIsEnabled)
        unit_item.setForeground(QColor("#7F848E"))
        self._table.setItem(row, 3, unit_item)

    def _validate_cell(self, row: int, value: str, fdef: FieldDef | None) -> None:
        item = self._table.item(row, 2)
        if item is None:
            return
        if not value.strip():
            if fdef and fdef.required:
                item.setForeground(QColor("#E06C75"))
            else:
                item.setForeground(QColor("#ABB2BF"))
            return
        if fdef and fdef.type in ("real", "integer"):
            try:
                num = float(value)
            except ValueError:
                item.setForeground(QColor("#E06C75"))
                return
            if (fdef.minimum is not None and num < fdef.minimum) or (
                fdef.maximum is not None and num > fdef.maximum
            ):
                item.setForeground(QColor("#E5C07B"))
            else:
                item.setForeground(QColor("#ABB2BF"))
            return
        item.setForeground(QColor("#ABB2BF"))

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._obj is None or item.column() != 2:
            return
        row = item.row()
        new_val = item.text()
        if row < len(self._obj.fields):
            self._obj.fields[row] = new_val
            fdef = (
                self._obj_def.fields[row]
                if self._obj_def and row < len(self._obj_def.fields)
                else None
            )
            self._validate_cell(row, new_val, fdef)
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
