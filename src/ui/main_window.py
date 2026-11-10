"""主窗口：集成编辑器、对象树、运行面板等。

通过构造注入 ``RunManager``/``IDFService``/``ConfigService``，禁止依赖全局
单例，禁止跨层访问私有方法。
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QStyle,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.core.idf.models import IDFDocument, IDFObject
from src.persistence.run_repository import RunRepository
from src.services.config_service import ConfigService
from src.services.ep_runner import RunResult
from src.services.idd_service import IDDService
from src.services.idf_service import IDFService
from src.services.results_service import ResultsService
from src.services.run_manager import RunManager
from src.ui.dialogs.validation_dialog import ValidationDialog
from src.ui.editor.idf_editor import IDFEditor
from src.ui.results.results_view import ResultsView
from src.ui.run.history_view import HistoryView
from src.ui.run.run_panel import RunPanel
from src.ui.settings.settings_dialog import SettingsDialog
from src.ui.theme import apply_theme
from src.ui.tree.field_panel import FieldEditPanel
from src.ui.tree.idf_tree import IDFObjectTree

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """主窗口。"""

    newWindowRequested = Signal(str)
    windowClosed = Signal(object)

    def __init__(
        self,
        run_manager: RunManager,
        idf_service: IDFService,
        config_service: ConfigService,
        idd_service: IDDService | None = None,
        results_service: ResultsService | None = None,
        run_repository: RunRepository | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Neko-EP-Launcher")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 700)

        self._run_manager = run_manager
        self._idf_service = idf_service
        self._config = config_service
        self._idd_service = idd_service
        self._results_service = results_service or ResultsService()
        self._run_repository = run_repository

        self._doc: IDFDocument | None = None
        self._current_path: str = ""
        self._modified = False
        self._selected_object_index: int | None = None
        self._sync_baseline = ""

        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(600)
        self._sync_timer.timeout.connect(self._auto_sync)
        self._build_ui()
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_statusbar()

        self._update_title()
        self._update_actions()

    def _build_actions(self) -> None:
        self._act_new = QAction("新建", self)
        self._act_new.setShortcut(QKeySequence.New)
        self._act_new.triggered.connect(self._new_file)

        self._act_new_window = QAction("新建窗口", self)
        self._act_new_window.setShortcut(QKeySequence("Ctrl+Shift+N"))
        self._act_new_window.triggered.connect(lambda: self.newWindowRequested.emit(""))

        self._act_open = QAction("打开...", self)
        self._act_open.setShortcut(QKeySequence.Open)
        self._act_open.triggered.connect(lambda checked=False: self._open_file())

        self._act_open_in_new_window = QAction("在新窗口中打开...", self)
        self._act_open_in_new_window.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self._act_open_in_new_window.triggered.connect(self._open_in_new_window)

        self._act_copy_object = QAction("复制选中对象", self)
        self._act_copy_object.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self._act_copy_object.triggered.connect(self._copy_selected_object)

        self._act_paste_object = QAction("粘贴对象", self)
        self._act_paste_object.setShortcut(QKeySequence("Ctrl+Shift+V"))
        self._act_paste_object.triggered.connect(self._paste_object_from_clipboard)

        self._act_save = QAction("保存", self)
        self._act_save.setShortcut(QKeySequence.Save)
        self._act_save.triggered.connect(self._save_file)

        self._act_save_as = QAction("另存为...", self)
        self._act_save_as.setShortcut(QKeySequence.SaveAs)
        self._act_save_as.triggered.connect(self._save_as)

        self._act_quit = QAction("退出", self)
        self._act_quit.setShortcut(QKeySequence.Quit)
        self._act_quit.triggered.connect(self.close)

        self._act_undo = QAction("撤销", self)
        self._act_undo.setShortcut(QKeySequence.Undo)
        self._act_undo.triggered.connect(self._editor.undo)
        self._act_redo = QAction("重做", self)
        self._act_redo.setShortcut(QKeySequence.Redo)
        self._act_redo.triggered.connect(self._editor.redo)

        self._act_find = QAction("查找...", self)
        self._act_find.setShortcut(QKeySequence.Find)
        self._act_find.triggered.connect(self._find)

        self._act_run = QAction("运行 EnergyPlus", self)
        self._act_run.setShortcut(QKeySequence("F5"))
        self._act_run.triggered.connect(self._run_current)

        self._act_settings = QAction("设置...", self)
        self._act_settings.triggered.connect(self._show_settings)

        self._act_about = QAction("关于", self)
        self._act_about.triggered.connect(self._show_about)

        self._act_open_example = QAction("打开示例...", self)
        self._act_open_example.triggered.connect(self._open_example)

        self._act_sync_tree = QAction("从文本同步到树", self)
        self._act_sync_tree.triggered.connect(self._sync_tree_from_text)

        self._act_validate = QAction("校验 IDF", self)
        self._act_validate.triggered.connect(self._validate_idf)
        self._act_results = QAction("打开结果目录...", self)
        self._act_results.triggered.connect(self._open_results)
        self._act_outputs = QAction("配置可视化输出", self)
        self._act_outputs.triggered.connect(self._configure_outputs)

        self._act_run_config = QAction("运行配置与日志", self)
        self._act_run_config.triggered.connect(self._show_run_config)
        self._act_properties = QAction("属性编辑", self)
        self._act_properties.triggered.connect(
            lambda: self._editor_tabs.setCurrentWidget(self._field_panel)
        )
        self._act_source = QAction("IDF 源码", self)
        self._act_source.triggered.connect(lambda: self._editor_tabs.setCurrentWidget(self._editor))

        self._act_history = QAction("运行历史", self)
        self._act_history.triggered.connect(self._show_history)

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        main_splitter = QSplitter(Qt.Horizontal)

        self._tree = IDFObjectTree()
        main_splitter.addWidget(self._tree)
        self._editor_tabs = QTabWidget()
        self._field_panel = FieldEditPanel(self._idd_service)
        self._editor_tabs.addTab(self._field_panel, "属性编辑")
        self._editor = IDFEditor()
        self._editor_tabs.addTab(self._editor, "IDF 源码")
        self._results_workspace = ResultsView(self._results_service)
        self._editor_tabs.addTab(self._results_workspace, "结果分析")
        main_splitter.addWidget(self._editor_tabs)
        main_splitter.setSizes([300, 1100])
        main_splitter.setStretchFactor(1, 1)
        layout.addWidget(main_splitter)

        self.setCentralWidget(central)

        run_dock = QDockWidget("运行配置与日志", self)
        self._run_dock = run_dock
        run_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        self._run_panel = RunPanel(self._run_manager, self._config)
        run_dock.setWidget(self._run_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, run_dock)
        run_dock.hide()

        files_dock = QDockWidget("最近文件", self)
        self._recent_list = QListWidget()
        self._recent_list.itemDoubleClicked.connect(self._open_recent)
        files_dock.setWidget(self._recent_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, files_dock)
        files_dock.hide()

        if self._run_repository is not None:
            history_dock = QDockWidget("运行历史", self)
            history_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
            self._history_view = HistoryView(self._run_repository)
            self._history_view.openRunRequested.connect(self._load_results)
            history_dock.setWidget(self._history_view)
            self.addDockWidget(Qt.BottomDockWidgetArea, history_dock)
            history_dock.hide()
        else:
            self._history_view = None

        self._tree.objectSelected.connect(self._on_object_selected)
        self._tree.objectCopyRequested.connect(self._copy_object)
        self._tree.objectCopyJsonRequested.connect(self._copy_object_json)
        self._tree.objectCopyFieldsRequested.connect(self._copy_object_fields)
        self._tree.objectPasteRequested.connect(self._paste_object_from_clipboard)
        self._tree.objectDuplicateRequested.connect(self._duplicate_object)
        self._tree.objectDeleteRequested.connect(self._delete_object)
        self._field_panel.fieldEditRequested.connect(self._edit_field)
        self._field_panel.structureEditRequested.connect(self._resize_fields)
        self._field_panel.batchFieldsEditRequested.connect(self._batch_edit_fields)
        self._tree.objectActivated.connect(
            lambda obj: self._editor_tabs.setCurrentWidget(self._editor)
        )
        self._run_panel.idfSelected.connect(self._open_file)
        self._run_panel.runRequested.connect(self._run_current)
        self._editor.textChanged.connect(self._on_text_changed)
        self._results_workspace.outputRequested.connect(self._add_output)
        self._run_panel.runFinished.connect(self._on_run_finished)
        self._run_panel.reportRequested.connect(self._generate_run_report)

        self._refresh_recent()

    def _build_menus(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("文件(&F)")
        file_menu.addAction(self._act_new)
        file_menu.addAction(self._act_new_window)
        file_menu.addSeparator()
        file_menu.addAction(self._act_open)
        file_menu.addAction(self._act_open_in_new_window)
        file_menu.addAction(self._act_open_example)
        file_menu.addAction(self._act_results)
        file_menu.addSeparator()
        file_menu.addAction(self._act_save)
        file_menu.addAction(self._act_save_as)
        file_menu.addSeparator()
        recent_menu = file_menu.addMenu("最近打开")
        self._recent_menu = recent_menu
        recent_menu.aboutToShow.connect(self._update_recent_menu)
        file_menu.addSeparator()
        file_menu.addAction(self._act_quit)

        edit_menu = mb.addMenu("编辑(&E)")
        edit_menu.addAction(self._act_undo)
        edit_menu.addAction(self._act_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self._act_copy_object)
        edit_menu.addAction(self._act_paste_object)
        edit_menu.addSeparator()
        edit_menu.addAction(self._act_find)
        edit_menu.addSeparator()
        edit_menu.addAction(self._act_sync_tree)
        edit_menu.addAction(self._act_validate)
        edit_menu.addAction(self._act_outputs)

        run_menu = mb.addMenu("运行(&R)")
        run_menu.addAction(self._act_run)
        run_menu.addAction(self._act_run_config)
        run_menu.addAction(self._act_history)

        view_menu = mb.addMenu("视图(&V)")
        for dock in self.findChildren(QDockWidget):
            view_menu.addAction(dock.toggleViewAction())

        tools_menu = mb.addMenu("工具(&T)")
        tools_menu.addAction(self._act_settings)

        help_menu = mb.addMenu("帮助(&H)")
        help_menu.addAction(self._act_about)

    def _build_toolbar(self) -> None:
        tb = QToolBar("常用操作")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        actions = [
            (self._act_new_window, QStyle.SP_DesktopIcon, "新建程序窗口（Ctrl+Shift+N）"),
            (self._act_open, QStyle.SP_DialogOpenButton, "打开 IDF（Ctrl+O）"),
            (self._act_save, QStyle.SP_DialogSaveButton, "保存当前 IDF（Ctrl+S）"),
            (self._act_save_as, QStyle.SP_DialogSaveButton, "另存为新文件"),
            (self._act_properties, QStyle.SP_FileDialogDetailedView, "切换到属性编辑"),
            (self._act_source, QStyle.SP_FileIcon, "切换到 IDF 源码编辑"),
            (self._act_validate, QStyle.SP_DialogApplyButton, "校验当前模型"),
            (
                self._act_run_config,
                QStyle.SP_FileDialogContentsView,
                "设置天气文件、报告选项并查看日志",
            ),
            (self._act_run, QStyle.SP_MediaPlay, "运行当前模型（F5）"),
            (self._act_results, QStyle.SP_DirOpenIcon, "打开已有结果目录"),
            (self._act_settings, QStyle.SP_ComputerIcon, "设置 EnergyPlus 路径和系统主题"),
        ]
        for action, icon, tip in actions:
            action.setIcon(self.style().standardIcon(icon))
            action.setToolTip(tip)
            tb.addAction(action)
        self.addToolBar(tb)

    def _show_run_config(self) -> None:
        self._run_dock.show()
        self._run_dock.raise_()
        self.resizeDocks([self._run_dock], [330], Qt.Vertical)

    def _build_statusbar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_file = QLabel("就绪")
        self._status_obj = QLabel("对象: 0")
        self._status_modified = QLabel("")
        sb.addWidget(self._status_file, 1)
        sb.addPermanentWidget(self._status_modified)
        sb.addPermanentWidget(self._status_obj)

    def _update_title(self) -> None:
        name = Path(self._current_path).name if self._current_path else "未命名"
        mod = " *" if self._modified else ""
        self.setWindowTitle(f"Neko-EP-Launcher - {name}{mod}")

    def _update_actions(self) -> None:
        has_doc = self._doc is not None
        self._act_save.setEnabled(has_doc or self._modified)
        self._act_save_as.setEnabled(has_doc or self._modified)
        self._act_sync_tree.setEnabled(has_doc)

    def _update_editor_highlight(self) -> None:
        """根据文档对象起始行更新编辑器高亮。"""
        if self._doc is None:
            self._editor.set_object_lines(set())
            return
        lines = {obj.line_start - 1 for obj in self._doc.objects if obj.line_start > 0}
        self._editor.set_object_lines(lines)

    def _new_file(self) -> None:
        if not self._confirm_discard():
            return
        self._sync_baseline = ""
        self._sync_timer.stop()
        self._editor.clear()
        self._doc = IDFDocument()
        self._current_path = ""
        self._modified = False
        self._tree.set_document(self._doc)
        self._field_panel.set_document(self._doc)
        self._selected_object_index = 0 if self._doc.objects else None
        obj = self._doc.objects[0] if self._doc.objects else None
        self._field_panel.set_object(obj)
        if obj:
            self._tree.select_object(obj)
        self._editor_tabs.setCurrentWidget(self._field_panel)
        self._field_panel.setEnabled(True)
        self._update_editor_highlight()
        self._update_title()
        self._update_actions()
        self._status_file.setText("新文件")

    def _open_file(self, path: str | None = None) -> None:
        if path is None:
            start = self._current_path or self._config.config.last_idf_dir or "/"
            path, _ = QFileDialog.getOpenFileName(
                self, "打开 IDF 文件", start, "IDF 文件 (*.idf);;所有文件 (*)"
            )
            if not path:
                return
        if not self._confirm_discard():
            return
        try:
            self._doc = self._idf_service.open(path)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"解析文件失败:\n{e}")
            return
        self._sync_baseline = self._doc.raw_text
        self._current_path = path
        self._modified = False
        self._editor.blockSignals(True)
        self._editor.setPlainText(self._doc.raw_text)
        self._editor.blockSignals(False)
        self._sync_timer.stop()
        self._field_panel.setEnabled(True)
        self._status_modified.clear()
        self._tree.set_document(self._doc)
        self._field_panel.set_document(self._doc)
        self._selected_object_index = 0 if self._doc.objects else None
        obj = self._doc.objects[0] if self._doc.objects else None
        self._field_panel.set_object(obj)
        if obj:
            self._tree.select_object(obj)
        self._editor_tabs.setCurrentWidget(self._field_panel)
        self._field_panel.setEnabled(True)
        self._update_editor_highlight()
        self._run_panel.set_idf(path)
        self._config.add_recent_file(path)
        self._config.config.last_idf_dir = str(Path(path).parent)
        self._config.save()
        self._refresh_recent()
        self._update_title()
        self._update_actions()
        self._status_file.setText(path)
        self._status_obj.setText(f"对象: {self._doc.object_count()}")

    def _open_example(self) -> None:
        ex_dir = self._config.get_example_dir()
        if not ex_dir:
            QMessageBox.information(
                self, "提示", "未找到示例文件目录，请检查 EnergyPlus 路径设置。"
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "打开示例 IDF", ex_dir, "IDF 文件 (*.idf);;所有文件 (*)"
        )
        if path:
            self._open_file(path)

    def _open_recent(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path and Path(path).exists():
            self._open_file(path)

    def _save_file(self) -> None:
        self._field_panel.commit_pending()
        if not self._current_path:
            return self._save_as()
        self._do_save(self._current_path)

    def _save_as(self) -> None:
        self._field_panel.commit_pending()
        start = self._current_path or self._config.config.last_idf_dir or "/"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 IDF 文件", start, "IDF 文件 (*.idf);;所有文件 (*)"
        )
        if path:
            self._do_save(path)

    def _do_save(self, path: str) -> None:
        text = self._editor.toPlainText()
        try:
            self._idf_service.save_text(text, path)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return
        self._current_path = path
        self._run_panel.set_idf(path)
        self._modified = False
        self._status_modified.clear()
        try:
            self._doc = self._idf_service.parse(text, path)
            self._sync_baseline = text
            self._tree.set_document(self._doc)
            self._field_panel.set_document(self._doc)
            if self._selected_object_index is not None and self._selected_object_index < len(
                self._doc.objects
            ):
                self._field_panel.rebind_object(self._doc.objects[self._selected_object_index])
            self._update_editor_highlight()
        except Exception as exc:
            self.statusBar().showMessage(f"文件已保存，但解析失败: {exc}")
        self._config.add_recent_file(path)
        self._config.config.last_idf_dir = str(Path(path).parent)
        self._config.save()
        self._refresh_recent()
        self._update_title()
        self._status_file.setText(path)

    def _confirm_discard(self) -> bool:
        self._field_panel.commit_pending()
        if not self._modified:
            return True
        ret = QMessageBox.question(
            self,
            "确认",
            "当前文件已修改，是否保存？",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if ret == QMessageBox.Save:
            self._save_file()
            return not self._modified
        return ret == QMessageBox.Discard

    def _on_text_changed(self) -> None:
        # 语法高亮也会触发 textChanged，只有原文变化才应禁用属性与启动同步。
        if self._editor.toPlainText() == self._sync_baseline:
            if not self._field_panel.isEnabled():
                self._sync_timer.start(0)
            return
        self._sync_timer.start()
        self._field_panel.setEnabled(False)
        if not self._modified:
            self._modified = True
            self._status_modified.setText("[已修改]")
            self._update_title()

    def _on_object_selected(self, obj: IDFObject) -> None:
        if self._doc is None:
            return
        target_index = next(
            (i for i, candidate in enumerate(self._doc.objects) if candidate is obj), None
        )
        self._field_panel.commit_pending()
        if target_index is not None and 0 <= target_index < len(self._doc.objects):
            target_obj = self._doc.objects[target_index]
        else:
            target_obj = obj
            target_index = next(
                (i for i, candidate in enumerate(self._doc.objects) if candidate is obj), None
            )
        self._selected_object_index = target_index
        self._field_panel.set_object(target_obj)
        if target_obj and target_obj.line_start:
            self._editor.jump_to_line(target_obj.line_start)

    def _edit_field(self, field_index: int, value: str) -> None:
        if self._doc is None or self._selected_object_index is None:
            return
        try:
            self._idf_service.update_field(
                self._doc, self._selected_object_index, field_index, value
            )
            self._on_object_changed(self._doc.objects[self._selected_object_index])
        except Exception as exc:
            QMessageBox.warning(self, "属性修改失败", str(exc))

    def _resize_fields(self, append: bool) -> None:
        if self._doc is None or self._selected_object_index is None:
            return
        try:
            self._field_panel.commit_pending()
            self._idf_service.resize_fields(self._doc, self._selected_object_index, append)
            self._on_object_changed(self._doc.objects[self._selected_object_index])
            self._field_panel.set_object(self._doc.objects[self._selected_object_index])
        except Exception as exc:
            QMessageBox.warning(self, "字段修改失败", str(exc))

    def _on_object_changed(self, obj: IDFObject) -> None:
        if self._doc is None or obj is None:
            return
        focused_widget = QApplication.focusWidget()
        index = next((i for i, candidate in enumerate(self._doc.objects) if candidate is obj), 0)
        new_text = self._idf_service.serialize(self._doc)
        doc = self._idf_service.parse(new_text, self._current_path)
        if new_text != self._editor.toPlainText():
            cursor_pos = self._editor.textCursor().position()
            with QSignalBlocker(self._editor):
                cursor = self._editor.textCursor()
                cursor.beginEditBlock()
                cursor.select(QTextCursor.Document)
                cursor.insertText(new_text)
                cursor.endEditBlock()
                cursor.setPosition(min(cursor_pos, self._editor.document().characterCount() - 1))
                self._editor.setTextCursor(cursor)
        self._doc = doc
        self._sync_baseline = new_text
        target_idx = index if (0 <= index < len(doc.objects)) else (0 if doc.objects else None)
        self._selected_object_index = target_idx
        self._tree.update_document(doc)
        if target_idx is not None and doc.objects:
            self._tree.select_object(doc.objects[target_idx])
            self._field_panel.set_document(doc)
            self._field_panel.rebind_object(doc.objects[target_idx])
        if focused_widget is not None and focused_widget.isVisible():
            focused_widget.setFocus()
        self._update_editor_highlight()
        self._modified = True
        self._status_modified.setText("[已修改]")
        self._update_title()

    def _auto_sync(self) -> None:
        """自动解析文本；未完成的输入禁用字段编辑，防止覆盖新文本。"""
        self._sync_timer.stop()
        selected = self._editor.textCursor().blockNumber() + 1
        try:
            doc = self._idf_service.parse(self._editor.toPlainText(), self._current_path)
        except Exception as exc:
            self._field_panel.setEnabled(False)
            self.statusBar().showMessage(f"等待修正 IDF: {exc}")
            return
        self._doc = doc
        self._sync_baseline = self._editor.toPlainText()
        self._tree.set_document(doc)
        self._field_panel.set_document(doc)
        obj = (
            next((o for o in doc.objects if o.line_start <= selected <= o.line_end), None)
            if self._editor.hasFocus()
            else None
        )
        if (
            obj is None
            and self._selected_object_index is not None
            and self._selected_object_index < len(doc.objects)
        ):
            obj = doc.objects[self._selected_object_index]
        if obj is None and doc.objects:
            obj = doc.objects[0]
        self._selected_object_index = next((i for i, o in enumerate(doc.objects) if o is obj), None)
        if obj:
            self._tree.select_object(obj)
        self._field_panel.set_object(obj)
        self._field_panel.setEnabled(True)
        self._update_editor_highlight()
        self._update_actions()
        self._status_obj.setText(f"对象: {doc.object_count()}")
        self.statusBar().clearMessage()

    def _validate_idf(self) -> None:
        """用可缩放窗口显示当前输入的完整校验结果。"""
        try:
            self._field_panel.commit_pending()
            doc = self._idf_service.parse(self._editor.toPlainText())
            idd = self._idd_service.document if self._idd_service else None
            if idd is None:
                ValidationDialog(
                    [], "语法正确。尚未加载 IDD：请在设置中配置 EnergyPlus 以启用字段校验。", self
                ).exec()
                return
            issues = self._idf_service.validate(doc, idd)
            errors = sum(issue.severity == "error" for issue in issues)
            warnings = sum(issue.severity == "warning" for issue in issues)
            summary = (
                f"发现 {len(issues)} 个问题（{errors} 个错误、{warnings} 个警告）"
                if issues
                else "语法与字段校验通过"
            )
            ValidationDialog(issues, summary, self).exec()
        except Exception as exc:
            ValidationDialog([], f"校验失败：{exc}", self).exec()

    def _open_results(self) -> None:
        """直接分析已有 EnergyPlus 输出目录。"""
        directory = QFileDialog.getExistingDirectory(self, "打开 EnergyPlus 结果目录")
        if directory:
            self._load_results(directory)

    def _load_results(self, directory: str) -> None:
        """运行完成、历史与手动打开共用主工作区。"""
        self._editor_tabs.setCurrentWidget(self._results_workspace)
        try:
            self._results_workspace.load_from_run_dir(directory)
        except Exception as exc:
            logger.exception("加载结果失败: %s", directory)
            QMessageBox.warning(self, "结果加载失败", str(exc))

    def _on_run_finished(self, result: RunResult) -> None:
        self._load_results(result.run_dir)
        if self._history_view is not None:
            self._history_view.refresh()

    def _generate_run_report(self, directory: str) -> None:
        try:
            self._results_workspace.generate_report(
                directory, str(Path(directory) / "enhanced-report.html")
            )
        except Exception as exc:
            logger.exception("启动报告生成失败")
            QMessageBox.warning(self, "报告生成失败", str(exc))

    def _add_output(self, name: str, is_meter: bool) -> None:
        """把结果字典中的选择插入当前模型。"""
        try:
            doc = self._idf_service.parse(self._editor.toPlainText())
            if self._idf_service.add_output(doc, name, is_meter):
                cursor = self._editor.textCursor()
                cursor.beginEditBlock()
                cursor.select(QTextCursor.Document)
                cursor.insertText(self._idf_service.serialize(doc))
                cursor.endEditBlock()
                self._auto_sync()
            self.statusBar().showMessage(
                f"已配置每小时输出: {name}；保存并重新运行后查看曲线。", 8000
            )
        except Exception as exc:
            QMessageBox.warning(self, "添加输出失败", str(exc))

    def _configure_outputs(self) -> None:
        """添加 SQLite、汇总报告和变量字典请求。依据 R-2。"""
        try:
            doc = self._idf_service.parse(self._editor.toPlainText())
            self._idf_service.configure_outputs(doc)
            cursor = self._editor.textCursor()
            cursor.beginEditBlock()
            cursor.select(QTextCursor.Document)
            cursor.insertText(self._idf_service.serialize(doc))
            cursor.endEditBlock()
            self._auto_sync()
            self.statusBar().showMessage(
                "已配置 SQLite、汇总报告和变量字典；时序变量仍需在 IDF 中请求。", 8000
            )
        except Exception as exc:
            QMessageBox.warning(self, "配置失败", str(exc))

    def _sync_tree_from_text(self) -> None:
        text = self._editor.toPlainText()
        try:
            self._doc = self._idf_service.parse(text, self._current_path)
            self._sync_baseline = text
            self._tree.set_document(self._doc)
            self._field_panel.set_document(self._doc)
            if self._selected_object_index is not None and self._selected_object_index < len(
                self._doc.objects
            ):
                self._field_panel.rebind_object(self._doc.objects[self._selected_object_index])
            self._update_editor_highlight()
            self._status_obj.setText(f"对象: {self._doc.object_count()}")
            QMessageBox.information(
                self, "同步", f"已从文本同步 {self._doc.object_count()} 个对象到树视图。"
            )
        except Exception as e:
            QMessageBox.critical(self, "解析错误", str(e))

    def _run_current(self) -> None:
        self._field_panel.commit_pending()
        self._show_run_config()
        if not self._current_path and not self._editor.toPlainText().strip():
            QMessageBox.warning(self, "警告", "没有可运行的 IDF 文件")
            return
        if self._modified:
            ret = QMessageBox.question(
                self,
                "保存",
                "文件已修改，是否保存后再运行？",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if ret == QMessageBox.Cancel:
                return
            if ret == QMessageBox.Yes:
                if not self._current_path:
                    self._save_as()
                    if not self._current_path:
                        return
                self._save_file()
                if self._modified:
                    return
        if not self._current_path:
            QMessageBox.warning(self, "警告", "请先保存文件")
            return
        self._run_panel.set_idf(self._current_path)
        if not self._config.is_ep_valid():
            QMessageBox.warning(self, "警告", "未配置有效的 EnergyPlus 路径，请先在设置中配置。")
            self._show_settings()
            return
        self._run_panel.start_run()

    def _show_settings(self) -> None:
        dlg = SettingsDialog(self._config, self)
        if dlg.exec() == SettingsDialog.Accepted:
            if self._idd_service and self._config.get_idd_path():
                try:
                    self._idd_service.load(self._config.get_idd_path())
                    self._auto_sync()
                except Exception as exc:
                    QMessageBox.warning(self, "IDD 加载失败", str(exc))
            apply_theme(self._config.config.theme)

    def _show_history(self) -> None:
        """显示运行历史面板。"""
        if self._history_view is None:
            QMessageBox.information(self, "提示", "运行历史不可用")
            return
        for dock in self.findChildren(QDockWidget):
            if dock.widget() is self._history_view:
                dock.show()
                dock.raise_()
                self._history_view.refresh()
                return

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于 Neko-EP-Launcher",
            "<h3>Neko-EP-Launcher</h3>"
            "<p>Linux 桌面端 EnergyPlus 图形化启动与建模分析工具，基于 PySide6（Qt for Python）开发。</p>"
            '<p>项目仓库：<a href="https://github.com/Chocola-X/Neko-EP-Launcher">https://github.com/Chocola-X/Neko-EP-Launcher</a></p>'
            "<p>功能特性：</p><ul>"
            "<li>IDF 文件编辑（语法高亮、行号、自动同步）</li>"
            "<li>对象树形结构与 IDD 元数据驱动字段编辑</li>"
            "<li>EnergyPlus 模拟运行与实时日志</li>"
            "<li>结果结构化分析（错误诊断、汇总表格、时序曲线、能耗图表、增强 HTML 报告）</li></ul>"
            "<p>许可证：<b>GNU Affero General Public License v3（AGPL v3）</b></p>"
            '<p><a href="https://www.gnu.org/licenses/agpl-3.0.html">查看完整许可证条款</a></p>',
        )

    def _find(self) -> None:
        text, ok = QInputDialog.getText(self, "查找", "查找内容:")
        if ok and text:
            self._editor.find_text(text)

    def _refresh_recent(self) -> None:
        self._recent_list.clear()
        for path in self._config.config.recent_files:
            if Path(path).exists():
                item = QListWidgetItem(Path(path).name)
                item.setToolTip(path)
                item.setData(Qt.UserRole, path)
                self._recent_list.addItem(item)

    def _update_recent_menu(self) -> None:
        self._recent_menu.clear()
        for path in self._config.config.recent_files:
            if Path(path).exists():
                act = QAction(Path(path).name, self)
                act.setData(path)
                act.triggered.connect(lambda checked=False, p=path: self._open_file(p))
                self._recent_menu.addAction(act)

    def closeEvent(self, event) -> None:
        if not self._confirm_discard():
            event.ignore()
            return
        if self._run_manager.is_running:
            ret = QMessageBox.question(
                self,
                "确认",
                "EnergyPlus 正在运行，确定退出？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ret == QMessageBox.No:
                event.ignore()
                return
            self._run_manager.cancel()
        self._config.save()
        self.windowClosed.emit(self)
        event.accept()

    def _open_in_new_window(self) -> None:
        """在新窗口打开所选的 IDF 文件。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "在新窗口中打开 IDF 文件", "", "IDF 文件 (*.idf);;所有文件 (*)"
        )
        if path:
            self.newWindowRequested.emit(path)

    def _copy_selected_object(self) -> None:
        """复制当前选中的对象。"""
        obj = self._tree.get_selected_object()
        if obj is not None:
            self._copy_object(obj)
        else:
            self.statusBar().showMessage("当前未选中任何对象", 3000)

    def _copy_object(self, obj: IDFObject) -> None:
        """将对象序列化为标准 IDF 字符串写入剪贴板。"""
        text = self._idf_service.serialize_object(obj)
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        name_desc = f" ({obj.name()})" if obj.name() else ""
        self.statusBar().showMessage(f"已复制对象: {obj.type_name}{name_desc}", 3000)

    def _copy_object_json(self, obj: IDFObject) -> None:
        """将对象序列化为 JSON 字符串写入剪贴板。"""
        import json

        data = {
            "type": obj.type_name,
            "name": obj.name(),
            "fields": obj.fields,
        }
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(json.dumps(data, ensure_ascii=False, indent=2))
        self.statusBar().showMessage(f"已复制对象 JSON: {obj.type_name}", 3000)

    def _copy_object_fields(self, obj: IDFObject) -> None:
        """将对象的各个字段以逗号分隔复制到剪贴板。"""
        text = ", ".join(obj.fields)
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        self.statusBar().showMessage(f"已复制对象参数列表 ({len(obj.fields)}项)", 3000)

    def _paste_object_from_clipboard(self) -> None:
        """从剪贴板读取 IDF 代码或 JSON，解析并追加到当前模型。"""
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        text = clipboard.text().strip()
        if not text:
            self.statusBar().showMessage("剪贴板内容为空", 3000)
            return

        objects = self._idf_service.parse_objects(text)
        if not objects:
            try:
                import json

                data = json.loads(text)
                if isinstance(data, dict) and "type" in data and "fields" in data:
                    objects = [IDFObject(data["type"], data["fields"])]
            except Exception:
                pass

        if not objects:
            self.statusBar().showMessage("剪贴板中未找到有效的 IDF 对象", 3000)
            return

        if self._doc is None:
            self._doc = IDFDocument()

        for obj in objects:
            self._idf_service.add_object(self._doc, obj)

        target = self._doc.objects[-1]
        self._on_object_changed(target)
        self._tree.select_object(target)
        self._field_panel.set_object(target)
        self.statusBar().showMessage(f"已成功粘贴 {len(objects)} 个对象并同步更新", 3000)

    def _duplicate_object(self, obj: IDFObject) -> None:
        """复制指定对象并在当前模型中创建副本。"""
        if self._doc is None:
            return
        index = next((i for i, c in enumerate(self._doc.objects) if c is obj), None)
        if index is not None:
            new_obj = self._idf_service.duplicate_object(self._doc, index)
            if new_obj:
                self._on_object_changed(new_obj)
                self._tree.select_object(new_obj)
                self._field_panel.set_object(new_obj)
                self.statusBar().showMessage(f"已创建对象副本: {new_obj.name()}", 3000)

    def _delete_object(self, obj: IDFObject) -> None:
        """删除指定对象并刷新界面。"""
        if self._doc is None:
            return
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除对象「{obj.type_name} {obj.name()}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        index = next((i for i, c in enumerate(self._doc.objects) if c is obj), None)
        if index is not None:
            self._idf_service.remove_object(self._doc, index)
            new_text = self._idf_service.serialize(self._doc)
            self._doc = self._idf_service.parse(new_text, self._current_path)
            self._sync_baseline = new_text
            self._tree.set_document(self._doc)
            self._field_panel.set_document(self._doc)
            self._selected_object_index = 0 if self._doc.objects else None
            sel_obj = self._doc.objects[0] if self._doc.objects else None
            self._field_panel.set_object(sel_obj)
            self._update_editor_highlight()
            self._modified = True
            self._status_modified.setText("[已修改]")
            self._update_title()
            self.statusBar().showMessage(f"已删除对象 {obj.type_name}", 3000)

    def _batch_edit_fields(self, values: list[str]) -> None:
        """批量覆盖当前选中的对象字段值。"""
        if self._doc is None or self._selected_object_index is None:
            return
        for idx, val in enumerate(values):
            with contextlib.suppress(Exception):
                self._idf_service.update_field(self._doc, self._selected_object_index, idx, val)
        self._on_object_changed(self._doc.objects[self._selected_object_index])
        self._field_panel.set_object(self._doc.objects[self._selected_object_index])
        self.statusBar().showMessage(f"已批量覆盖更新 {len(values)} 个参数", 3000)
