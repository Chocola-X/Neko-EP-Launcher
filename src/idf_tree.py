"""IDF 对象树形视图和字段编辑面板。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QSplitter, QLabel,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPushButton, QGroupBox, QFormLayout, QComboBox, QPlainTextEdit,
    QStyledItemDelegate
)

from .idf_parser import IDFDocument, IDFObject


class IDFObjectTree(QWidget):
    """IDF 对象树形视图。"""

    objectSelected = Signal(object)
    objectActivated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("按对象类型或名称过滤...")
        self._search.textChanged.connect(self._filter)
        search_layout.addWidget(self._search, 1)
        layout.addLayout(search_layout)

        self._tree = QTreeView()
        self._tree.setUniformRowHeights(True)
        self._tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tree.setHeaderHidden(True)
        self._tree.setAlternatingRowColors(True)
        layout.addWidget(self._tree, 1)

        self._model = QStandardItemModel()
        self._tree.setModel(self._model)
        self._tree.clicked.connect(self._on_clicked)
        self._tree.doubleClicked.connect(self._on_double_clicked)

    def set_document(self, doc: IDFDocument):
        self._doc = doc
        self._refresh()

    def _refresh(self):
        self._model.clear()
        if not self._doc:
            return
        groups = {}
        for idx, obj in enumerate(self._doc.objects):
            t = obj.type_name
            groups.setdefault(t, []).append((idx, obj))

        root = self._model.invisibleRootItem()
        for type_name, items in sorted(groups.items()):
            type_item = QStandardItem(f"{type_name}  ({len(items)})")
            type_item.setEditable(False)
            type_item.setData(None, Qt.UserRole)
            font = type_item.font()
            font.setBold(True)
            type_item.setFont(font)
            type_item.setForeground(QColor("#56B6C2"))
            root.appendRow(type_item)
            for idx, obj in items:
                name = obj.get_field(0) if obj.fields else ""
                label = name if name else f"#{idx + 1}"
                child = QStandardItem(label)
                child.setEditable(False)
                child.setData(obj, Qt.UserRole)
                child.setData(idx, Qt.UserRole + 1)
                type_item.appendRow(child)

        self._tree.expandToDepth(0)

    def _filter(self, text):
        text = text.strip().lower()
        for i in range(self._model.rowCount()):
            parent = self._model.item(i)
            visible_children = 0
            for j in range(parent.rowCount()):
                child = parent.child(j)
                obj = child.data(Qt.UserRole)
                match = True
                if text:
                    name = obj.get_field(0) if obj and obj.fields else ""
                    match = (text in obj.type_name.lower()
                             or text in name.lower())
                idx = self._tree.model().index(j, 0,
                                                self._tree.model().index(i, 0))
                self._tree.setRowHidden(j, self._tree.model().index(i, 0),
                                        not match)
                if match:
                    visible_children += 1
            self._tree.setRowHidden(i, self._tree.rootIndex(),
                                    visible_children == 0 and bool(text))

    def _on_clicked(self, index):
        item = self._model.itemFromIndex(index)
        obj = item.data(Qt.UserRole)
        if obj is not None:
            self.objectSelected.emit(obj)

    def _on_double_clicked(self, index):
        item = self._model.itemFromIndex(index)
        obj = item.data(Qt.UserRole)
        if obj is not None:
            self.objectActivated.emit(obj)

    def select_object(self, obj: IDFObject):
        for i in range(self._model.rowCount()):
            parent = self._model.item(i)
            for j in range(parent.rowCount()):
                child = parent.child(j)
                if child.data(Qt.UserRole) is obj:
                    idx = child.index()
                    self._tree.setCurrentIndex(idx)
                    return


class FieldEditPanel(QWidget):
    """字段编辑面板，显示选中对象的字段表格。"""

    fieldChanged = Signal(object, int, str)
    objectChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._obj = None
        self._build_ui()

    def _build_ui(self):
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

    def set_object(self, obj: IDFObject):
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
        self._name_label.setText(obj.get_field(0) if obj.fields else "-")
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

    def _on_item_changed(self, item):
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

    def _add_field(self):
        if self._obj is None:
            return
        self._obj.fields.append("")
        self._obj.field_names.append("")
        self._obj.comments.append("")
        self.set_object(self._obj)
        self.objectChanged.emit(self._obj)

    def _del_field(self):
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
