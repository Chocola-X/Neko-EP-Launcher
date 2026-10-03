"""IDF 对象树形视图。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from src.core.idf.models import IDFDocument, IDFObject


class IDFObjectTree(QWidget):
    """IDF 对象树形视图。

    Signals:
        objectSelected(object): 选中对象，载荷为 IDFObject。
        objectActivated(object): 双击对象。
    """

    objectSelected = Signal(object)
    objectActivated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._doc: IDFDocument | None = None
        self._build_ui()

    def _build_ui(self) -> None:
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

    def set_document(self, doc: IDFDocument | None) -> None:
        self._doc = doc
        self._refresh()

    def _refresh(self) -> None:
        self._model.clear()
        if not self._doc:
            return
        groups: dict[str, list[tuple[int, IDFObject]]] = {}
        for idx, obj in enumerate(self._doc.objects):
            groups.setdefault(obj.type_name, []).append((idx, obj))

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
                name = obj.name() if obj.fields else ""
                label = name if name else f"#{idx + 1}"
                child = QStandardItem(label)
                child.setEditable(False)
                child.setData(obj, Qt.UserRole)
                child.setData(idx, Qt.UserRole + 1)
                type_item.appendRow(child)

        self._tree.expandToDepth(0)

    def _filter(self, text: str) -> None:
        text = text.strip().lower()
        for i in range(self._model.rowCount()):
            parent = self._model.item(i)
            visible_children = 0
            for j in range(parent.rowCount()):
                child = parent.child(j)
                obj: IDFObject | None = child.data(Qt.UserRole)
                match = True
                if text:
                    name = obj.name() if obj and obj.fields else ""
                    match = text in obj.type_name.lower() or text in name.lower() if obj else False
                self._tree.setRowHidden(j, self._tree.model().index(i, 0), not match)
                if match:
                    visible_children += 1
            self._tree.setRowHidden(i, self._tree.rootIndex(), visible_children == 0 and bool(text))

    def _on_clicked(self, index) -> None:
        item = self._model.itemFromIndex(index)
        obj = item.data(Qt.UserRole)
        if obj is not None:
            self.objectSelected.emit(obj)

    def _on_double_clicked(self, index) -> None:
        item = self._model.itemFromIndex(index)
        obj = item.data(Qt.UserRole)
        if obj is not None:
            self.objectActivated.emit(obj)

    def select_object(self, obj: IDFObject) -> None:
        for i in range(self._model.rowCount()):
            parent = self._model.item(i)
            for j in range(parent.rowCount()):
                child = parent.child(j)
                if child.data(Qt.UserRole) is obj:
                    self._tree.setCurrentIndex(child.index())
                    return
