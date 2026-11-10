"""字段编辑面板（元数据驱动）。

基于 IDD ObjectDef 渲染字段：choice→下拉、object-list→可搜索下拉、
real/integer→带校验输入框，显示单位/默认/必填标记，非法值即时标红。
依据 R-2/R-10。
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QCompleter,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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

    fieldEditRequested = Signal(int, str)
    structureEditRequested = Signal(bool)
    batchFieldsEditRequested = Signal(list)

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
        self._type_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._name_label = QLabel("-")
        self._line_label = QLabel("-")
        info_layout.addRow("类型:", self._type_label)
        info_layout.addRow("名称:", self._name_label)
        info_layout.addRow("行号:", self._line_label)
        layout.addWidget(info_group)

        self._hint = QLabel("请在左侧选择对象，然后直接在“值”栏输入。")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)
        table_group = QGroupBox("属性（Enter 或离开输入框后提交）")
        table_layout = QVBoxLayout(table_group)
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["#", "字段名", "值", "单位/说明"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self._table.setColumnWidth(1, 230)
        self._table.setColumnWidth(3, 180)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.verticalHeader().setDefaultSectionSize(34)
        self._table.verticalHeader().setVisible(False)
        self._table.itemChanged.connect(self._on_item_changed)
        table_layout.addWidget(self._table)
        layout.addWidget(table_group, 1)

        btn_layout = QHBoxLayout()
        self._btn_add = QPushButton("＋ 添加末尾字段")
        self._btn_del = QPushButton("－ 删除末尾字段")
        self._btn_copy_params = QPushButton("📋 复制全部参数")
        self._btn_paste_params = QPushButton("📥 粘贴覆盖参数")
        self._btn_copy_params.setToolTip("将当前对象的所有字段参数复制到剪贴板，支持跨窗口粘贴")
        self._btn_paste_params.setToolTip("从剪贴板读取参数并覆盖到当前对象的字段中")
        self._btn_add.clicked.connect(self._add_field)
        self._btn_del.clicked.connect(self._del_field)
        self._btn_copy_params.clicked.connect(self._copy_all_params)
        self._btn_paste_params.clicked.connect(self._paste_all_params)
        btn_layout.addWidget(self._btn_add)
        btn_layout.addWidget(self._btn_del)
        btn_layout.addWidget(self._btn_copy_params)
        btn_layout.addWidget(self._btn_paste_params)
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

        self._hint.setText(
            "直接修改值，按 Enter 或切换字段提交；Ctrl+S 保存到文件。"
            if self._obj_def
            else "当前未加载 IDD：仍可编辑字段值；在设置中配置 EnergyPlus 可显示字段定义。"
        )
        count = max(len(obj.fields), min(30, len(self._obj_def.fields)) if self._obj_def else 0)
        self._table.setRowCount(count)
        for i in range(count):
            val = obj.get_field(i)
            fdef = self._obj_def.get_field(i) if self._obj_def else None
            fname = obj.field_names[i] if i < len(obj.field_names) else ""
            self._fill_row(i, val, fname, fdef)
        self._table.blockSignals(False)

    def _fill_row(self, row: int, value: str, name: str, fdef: FieldDef | None) -> None:
        display_name = (fdef.name if fdef and fdef.name else name) or f"字段 {row + 1}"
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
        editor = None
        if fdef and (fdef.key_choices or fdef.object_lists):
            combo = QComboBox()
            combo.setEditable(True)
            choices = list(fdef.key_choices)
            if fdef.object_lists and self._doc and self._idd:
                for candidate in self._doc.objects:
                    definition = self._idd.get_object_def(candidate.type_name)
                    if definition:
                        for i, field in enumerate(definition.fields):
                            if set(field.references) & set(fdef.object_lists):
                                choices.append(candidate.get_field(i))
            combo.addItems(["", *sorted(set(choices))])
            combo.setCurrentText(value)
            combo.completer().setFilterMode(Qt.MatchContains)
            combo.completer().setCompletionMode(QCompleter.PopupCompletion)
            combo.lineEdit().editingFinished.connect(lambda r=row: self._commit_row(r))
            combo.activated.connect(lambda index, r=row: self._commit_row(r))
            self._table.setCellWidget(row, 2, combo)
            editor = combo
        else:
            edit = QLineEdit(value)
            edit.setPlaceholderText(fdef.default if fdef and fdef.default else "输入值…")
            edit.setClearButtonEnabled(True)
            edit.editingFinished.connect(lambda r=row: self._commit_row(r))
            self._table.setCellWidget(row, 2, edit)
            editor = edit
        editor.setAccessibleName(display_name or f"字段 {row + 1}")
        editor.setToolTip(fdef.note if fdef else "修改后按 Enter 提交")
        if item_tip := val_item.toolTip():
            editor.setToolTip(item_tip)
        self._update_editor_validation(row)

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
        self._table.setItem(row, 3, unit_item)

    def _validate_cell(self, row: int, value: str, fdef: FieldDef | None) -> None:
        item = self._table.item(row, 2)
        if item is None:
            return
        if not value.strip():
            if fdef and fdef.required:
                item.setForeground(QColor("#E06C75"))
            else:
                item.setForeground(self.palette().color(QPalette.Text))
            return
        if fdef and fdef.type in ("real", "integer"):
            if (fdef.autosizable and value.casefold() == "autosize") or (
                fdef.autocalculatable and value.casefold() == "autocalculate"
            ):
                item.setForeground(QColor("#98C379"))
                return
            try:
                num = float(value)
            except ValueError:
                item.setForeground(QColor("#E06C75"))
                return
            if not math.isfinite(num) or (fdef.type == "integer" and not num.is_integer()):
                item.setForeground(QColor("#E06C75"))
                item.setToolTip("需要有限的数值；整数字段不可含小数")
                return
            if (fdef.minimum_greater is not None and num <= fdef.minimum_greater) or (
                fdef.maximum_less is not None and num >= fdef.maximum_less
            ):
                item.setForeground(QColor("#E06C75"))
                item.setToolTip("超出允许的开区间")
                return
            if (fdef.minimum is not None and num < fdef.minimum) or (
                fdef.maximum is not None and num > fdef.maximum
            ):
                item.setForeground(QColor("#E5C07B"))
            else:
                item.setForeground(self.palette().color(QPalette.Text))
            return
        item.setForeground(self.palette().color(QPalette.Text))

    def _update_editor_validation(self, row: int) -> None:
        editor = self._table.cellWidget(row, 2)
        item = self._table.item(row, 2)
        if editor is None or item is None:
            return
        color = item.foreground().color()
        if color in (QColor("#E06C75"), QColor("#E5C07B")):
            palette = QPalette()
            palette.setColor(
                QPalette.Text,
                QColor("#ba1a1a")
                if self.palette().color(QPalette.Base).lightness() > 128
                else QColor("#ffb4ab"),
            )
            editor.setPalette(palette)
            editor.setToolTip(
                item.toolTip() or "字段值不符合类型、范围或必填要求，请修正后校验模型。"
            )
        else:
            editor.setPalette(QPalette())

    def rebind_object(self, obj: IDFObject | None) -> None:
        """解析后更新只读对象引用，保留正在使用的输入框和焦点。"""
        self._obj = obj
        if obj is not None:
            self._name_label.setText(obj.name())
            self._line_label.setText(f"{obj.line_start} - {obj.line_end}")
            for row in range(self._table.rowCount()):
                editor = self._table.cellWidget(row, 2)
                value = obj.get_field(row)
                if isinstance(editor, QLineEdit) and editor.text() != value:
                    editor.setText(value)
                elif isinstance(editor, QComboBox) and editor.currentText() != value:
                    editor.setCurrentText(value)

    def commit_pending(self) -> None:
        """保存、切换对象或运行前提交当前输入框，支持键盘快捷键保存。"""
        if self._obj is None or not self.isEnabled():
            return
        for row in range(self._table.rowCount()):
            editor = self._table.cellWidget(row, 2)
            if editor is None:
                continue
            value = editor.currentText() if isinstance(editor, QComboBox) else editor.text()
            if (
                editor.hasFocus()
                or (isinstance(editor, QComboBox) and editor.lineEdit().hasFocus())
                or (value != self._obj.get_field(row))
            ):
                self._commit_row(row)
                return

    def _commit_row(self, row: int) -> None:
        if self._obj is None or not self.isEnabled():
            return
        editor = self._table.cellWidget(row, 2)
        value = editor.currentText() if isinstance(editor, QComboBox) else editor.text()
        if value == self._obj.get_field(row):
            return
        self._table.blockSignals(True)
        self._table.item(row, 2).setText(value)
        self._validate_cell(row, value, self._obj_def.get_field(row) if self._obj_def else None)
        self._table.blockSignals(False)
        self._update_editor_validation(row)
        self.fieldEditRequested.emit(row, value)
        target_focus = editor.lineEdit() if isinstance(editor, QComboBox) else editor
        if target_focus and target_focus.isVisible():
            target_focus.setFocus()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._obj is not None and item.column() == 2:
            self.fieldEditRequested.emit(item.row(), item.text())

    def _add_field(self) -> None:
        if self._obj is not None:
            self.structureEditRequested.emit(True)

    def _del_field(self) -> None:
        if self._obj is not None:
            self.structureEditRequested.emit(False)

    def _copy_all_params(self) -> None:
        if self._obj is None:
            return
        text = ", ".join(self._obj.fields)
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        self._hint.setText(f"已复制当前对象的 {len(self._obj.fields)} 个参数到剪贴板。")

    def _paste_all_params(self) -> None:
        if self._obj is None or not self.isEnabled():
            return
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        text = clipboard.text().strip()
        if not text:
            return
        clean_text = text.rstrip(";").strip()
        if "\n" in clean_text:
            parts = [p.strip() for p in clean_text.splitlines() if p.strip()]
        else:
            parts = [p.strip() for p in clean_text.split(",")]
        if parts:
            self.batchFieldsEditRequested.emit(parts)
            self._hint.setText(f"已从剪贴板粘贴覆盖 {len(parts)} 个参数。")
