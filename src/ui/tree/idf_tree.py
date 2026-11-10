"""IDF 对象树形视图。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
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
    objectCopyRequested = Signal(object)
    objectCopyJsonRequested = Signal(object)
    objectCopyFieldsRequested = Signal(object)
    objectPasteRequested = Signal()
    objectDuplicateRequested = Signal(object)
    objectDeleteRequested = Signal(object)

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
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._tree, 1)

        self._model = QStandardItemModel()
        self._tree.setModel(self._model)
        self._tree.selectionModel().currentChanged.connect(
            lambda current, previous: self._on_clicked(current)
        )
        self._tree.doubleClicked.connect(self._on_double_clicked)

    def set_document(self, doc: IDFDocument | None) -> None:
        self._doc = doc
        self._refresh()

    def update_document(self, doc: IDFDocument) -> None:
        """字段提交后替换模型引用与名称，保留树索引、展开状态及点击目标。"""
        self._doc = doc
        for i in range(self._model.rowCount()):
            parent = self._model.item(i)
            for j in range(parent.rowCount()):
                child = parent.child(j)
                index = child.data(Qt.UserRole + 1)
                if 0 <= index < len(doc.objects):
                    obj = doc.objects[index]
                    child.setData(obj, Qt.UserRole)
                    child.setText(obj.name() or f"#{index + 1}")
        self._filter(self._search.text())

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
        self._filter(self._search.text())

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
        obj = item.data(Qt.UserRole) if item is not None else None
        if obj is not None:
            self.objectSelected.emit(obj)

    def _on_double_clicked(self, index) -> None:
        item = self._model.itemFromIndex(index)
        obj = item.data(Qt.UserRole) if item is not None else None
        if obj is not None:
            self.objectActivated.emit(obj)

    def select_object(self, obj: IDFObject) -> None:
        for i in range(self._model.rowCount()):
            parent = self._model.item(i)
            for j in range(parent.rowCount()):
                child = parent.child(j)
                if child.data(Qt.UserRole) is obj:
                    self._tree.selectionModel().blockSignals(True)
                    self._tree.setCurrentIndex(child.index())
                    self._tree.selectionModel().blockSignals(False)
                    return

    def get_selected_object(self) -> IDFObject | None:
        """获取当前选中的对象。"""
        indexes = self._tree.selectionModel().selectedIndexes()
        if not indexes:
            return None
        item = self._model.itemFromIndex(indexes[0])
        return item.data(Qt.UserRole) if item is not None else None

    def _show_context_menu(self, pos) -> None:
        index = self._tree.indexAt(pos)
        item = self._model.itemFromIndex(index) if index.isValid() else None
        obj: IDFObject | None = item.data(Qt.UserRole) if item is not None else None

        menu = QMenu(self)
        if obj is not None:
            act_copy = menu.addAction("复制对象 (Ctrl+C)")
            act_copy.triggered.connect(lambda: self.objectCopyRequested.emit(obj))

            act_copy_params = menu.addAction("复制参数列表")
            act_copy_params.triggered.connect(lambda: self.objectCopyFieldsRequested.emit(obj))

            act_copy_json = menu.addAction("复制为 JSON")
            act_copy_json.triggered.connect(lambda: self.objectCopyJsonRequested.emit(obj))

            menu.addSeparator()
            act_dup = menu.addAction("创建对象副本")
            act_dup.triggered.connect(lambda: self.objectDuplicateRequested.emit(obj))

            act_del = menu.addAction("删除对象 (Delete)")
            act_del.triggered.connect(lambda: self.objectDeleteRequested.emit(obj))

            menu.addSeparator()

        act_paste = menu.addAction("粘贴对象 (Ctrl+V)")
        act_paste.triggered.connect(lambda: self.objectPasteRequested.emit())

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Copy):
            if obj := self.get_selected_object():
                self.objectCopyRequested.emit(obj)
                event.accept()
                return
        elif event.matches(QKeySequence.StandardKey.Paste):
            self.objectPasteRequested.emit()
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Delete and (obj := self.get_selected_object()):
            self.objectDeleteRequested.emit(obj)
            event.accept()
            return
        super().keyPressEvent(event)
