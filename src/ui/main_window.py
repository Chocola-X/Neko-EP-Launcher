"""主窗口：集成编辑器、对象树、运行面板等。

通过构造注入 ``RunManager``/``IDFService``/``ConfigService``，禁止依赖全局
单例，禁止跨层访问私有方法。
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
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
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.core.idf.models import IDFDocument, IDFObject
from src.services.config_service import ConfigService
from src.services.idf_service import IDFService
from src.services.run_manager import RunManager
from src.ui.editor.idf_editor import IDFEditor
from src.ui.run.run_panel import RunPanel
from src.ui.settings.settings_dialog import SettingsDialog
from src.ui.theme import apply_theme
from src.ui.tree.field_panel import FieldEditPanel
from src.ui.tree.idf_tree import IDFObjectTree

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """主窗口。"""

    def __init__(
        self,
        run_manager: RunManager,
        idf_service: IDFService,
        config_service: ConfigService,
    ) -> None:
        super().__init__()
        self.setWindowTitle("EnergyPlus 启动器")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 700)

        self._run_manager = run_manager
        self._idf_service = idf_service
        self._config = config_service

        self._doc: IDFDocument | None = None
        self._current_path: str = ""
        self._modified = False

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

        self._act_open = QAction("打开...", self)
        self._act_open.setShortcut(QKeySequence.Open)
        self._act_open.triggered.connect(self._open_file)

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

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        main_splitter = QSplitter(Qt.Horizontal)

        left_splitter = QSplitter(Qt.Vertical)
        self._tree = IDFObjectTree()
        self._field_panel = FieldEditPanel()
        left_splitter.addWidget(self._tree)
        left_splitter.addWidget(self._field_panel)
        left_splitter.setSizes([400, 300])
        main_splitter.addWidget(left_splitter)

        self._editor_tabs = QTabWidget()
        self._editor = IDFEditor()
        self._editor_tabs.addTab(self._editor, "文本编辑")
        main_splitter.addWidget(self._editor_tabs)
        main_splitter.setSizes([400, 1000])
        layout.addWidget(main_splitter)

        self.setCentralWidget(central)

        run_dock = QDockWidget("运行面板", self)
        run_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        self._run_panel = RunPanel(self._run_manager, self._config)
        run_dock.setWidget(self._run_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, run_dock)

        files_dock = QDockWidget("最近文件", self)
        self._recent_list = QListWidget()
        self._recent_list.itemDoubleClicked.connect(self._open_recent)
        files_dock.setWidget(self._recent_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, files_dock)
        files_dock.hide()

        self._tree.objectSelected.connect(self._on_object_selected)
        self._field_panel.objectChanged.connect(self._on_object_changed)
        self._editor.textChanged.connect(self._on_text_changed)

        self._refresh_recent()

    def _build_menus(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("文件(&F)")
        file_menu.addAction(self._act_new)
        file_menu.addAction(self._act_open)
        file_menu.addAction(self._act_open_example)
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
        edit_menu.addAction(self._act_find)
        edit_menu.addSeparator()
        edit_menu.addAction(self._act_sync_tree)

        run_menu = mb.addMenu("运行(&R)")
        run_menu.addAction(self._act_run)

        view_menu = mb.addMenu("视图(&V)")
        for dock in self.findChildren(QDockWidget):
            view_menu.addAction(dock.toggleViewAction())

        tools_menu = mb.addMenu("工具(&T)")
        tools_menu.addAction(self._act_settings)

        help_menu = mb.addMenu("帮助(&H)")
        help_menu.addAction(self._act_about)

    def _build_toolbar(self) -> None:
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        tb.addAction(self._act_new)
        tb.addAction(self._act_open)
        tb.addAction(self._act_save)
        tb.addSeparator()
        tb.addAction(self._act_undo)
        tb.addAction(self._act_redo)
        tb.addSeparator()
        tb.addAction(self._act_run)
        tb.addSeparator()
        tb.addAction(self._act_settings)
        self.addToolBar(tb)

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
        self.setWindowTitle(f"EnergyPlus 启动器 - {name}{mod}")

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
        self._editor.clear()
        self._doc = IDFDocument()
        self._current_path = ""
        self._modified = False
        self._tree.set_document(self._doc)
        self._field_panel.set_object(None)
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
        self._current_path = path
        self._modified = False
        self._editor.setPlainText(self._doc.raw_text)
        self._tree.set_document(self._doc)
        self._field_panel.set_object(None)
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
        if not self._current_path:
            return self._save_as()
        self._do_save(self._current_path)

    def _save_as(self) -> None:
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
        except OSError as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return
        self._current_path = path
        self._modified = False
        try:
            self._doc = self._idf_service.parse(text, path)
            self._tree.set_document(self._doc)
            self._update_editor_highlight()
        except Exception:
            pass
        self._config.add_recent_file(path)
        self._config.config.last_idf_dir = str(Path(path).parent)
        self._config.save()
        self._refresh_recent()
        self._update_title()
        self._status_file.setText(path)

    def _confirm_discard(self) -> bool:
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
        if not self._modified:
            self._modified = True
            self._status_modified.setText("[已修改]")
            self._update_title()

    def _on_object_selected(self, obj: IDFObject) -> None:
        self._field_panel.set_object(obj)
        if obj and obj.line_start:
            self._editor.jump_to_line(obj.line_start)

    def _on_object_changed(self, obj: IDFObject) -> None:
        if self._doc is None or obj is None:
            return
        new_text = self._idf_service.serialize(self._doc)
        if new_text != self._editor.toPlainText():
            cursor_pos = self._editor.textCursor().position()
            self._editor.setPlainText(new_text)
            cursor = self._editor.textCursor()
            cursor.setPosition(min(cursor_pos, len(new_text)))
            self._editor.setTextCursor(cursor)
            self._update_editor_highlight()
        self._modified = True
        self._status_modified.setText("[已修改]")
        self._update_title()

    def _sync_tree_from_text(self) -> None:
        text = self._editor.toPlainText()
        try:
            self._doc = self._idf_service.parse(text, self._current_path)
            self._tree.set_document(self._doc)
            self._update_editor_highlight()
            self._status_obj.setText(f"对象: {self._doc.object_count()}")
            QMessageBox.information(
                self, "同步", f"已从文本同步 {self._doc.object_count()} 个对象到树视图。"
            )
        except Exception as e:
            QMessageBox.critical(self, "解析错误", str(e))

    def _run_current(self) -> None:
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
            apply_theme(self._config.config.theme)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于 EnergyPlus 启动器",
            "<h3>EnergyPlus 图形化启动器</h3>"
            "<p>基于 PySide6 开发的 EnergyPlus 配置编辑与运行工具。</p>"
            "<p>功能：</p><ul>"
            "<li>IDF 文件编辑（语法高亮、行号）</li>"
            "<li>对象树形结构与字段表格编辑</li>"
            "<li>EnergyPlus 运行与实时日志</li>"
            "<li>结果文件查看</li></ul>"
            "<p>开发者：华为云码道(CodeArts)代码智能体</p>",
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
        event.accept()
