"""运行面板：配置运行参数、显示实时输出、查看结果文件。

通过构造注入 ``ConfigService`` 与 ``RunManager``，禁止依赖全局单例。
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.services.config_service import ConfigService
from src.services.ep_runner import EPRunner, RunResult
from src.services.run_manager import RunManager, RunRequest

logger = logging.getLogger(__name__)


class RunPanel(QWidget):
    """运行面板。

    Signals:
        runFinished(object): 运行完成，载荷为 RunResult。
    """

    runFinished = Signal(object)

    def __init__(
        self,
        run_manager: RunManager,
        config_service: ConfigService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._run_manager = run_manager
        self._config = config_service
        self._idf_path = ""
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        config_group = QGroupBox("运行配置")
        config_layout = QFormLayout(config_group)

        self._idf_label = QLineEdit()
        self._idf_label.setReadOnly(True)
        self._idf_label.setPlaceholderText("尚未选择 IDF 文件")
        idf_row = QHBoxLayout()
        idf_row.addWidget(self._idf_label, 1)
        self._btn_idf = QPushButton("选择...")
        self._btn_idf.clicked.connect(self._pick_idf)
        idf_row.addWidget(self._btn_idf)
        config_layout.addRow("IDF 文件:", idf_row)

        self._weather = QComboBox()
        self._weather.setEditable(True)
        self._refresh_weather()
        wf_row = QHBoxLayout()
        wf_row.addWidget(self._weather, 1)
        self._btn_wf = QPushButton("浏览...")
        self._btn_wf.clicked.connect(self._pick_weather)
        wf_row.addWidget(self._btn_wf)
        self._btn_refresh_wf = QPushButton("刷新")
        self._btn_refresh_wf.clicked.connect(self._refresh_weather)
        wf_row.addWidget(self._btn_refresh_wf)
        config_layout.addRow("天气文件:", wf_row)

        self._run_id = QLineEdit()
        self._run_id.setPlaceholderText("留空则使用时间戳")
        config_layout.addRow("运行 ID:", self._run_id)

        self._extra_args = QLineEdit(self._config.config.run_options)
        self._extra_args.setPlaceholderText("例如: -r -p")
        config_layout.addRow("附加参数:", self._extra_args)

        layout.addWidget(config_group)

        btn_row = QHBoxLayout()
        self._btn_run = QPushButton("运行")
        self._btn_run.setStyleSheet(
            "QPushButton { background-color: #98C379; color: black; "
            "font-weight: bold; padding: 6px 20px; }"
            "QPushButton:disabled { background-color: #7F848E; }"
        )
        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setEnabled(False)
        self._btn_cancel.setStyleSheet(
            "QPushButton { background-color: #E06C75; color: black; padding: 6px 20px; }"
        )
        self._btn_run.clicked.connect(self.start_run)
        self._btn_cancel.clicked.connect(self._run_manager.cancel)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_run)
        btn_row.addWidget(self._btn_cancel)
        layout.addLayout(btn_row)

        self._status = QLabel("就绪")
        self._status.setStyleSheet("color: gray;")
        layout.addWidget(self._status)

        tabs = QTabWidget()
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        font = QFont("Monospace")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self._log.setFont(font)
        tabs.addTab(self._log, "运行日志")

        result_tab = self._build_result_tab()
        tabs.addTab(result_tab, "结果文件")
        layout.addWidget(tabs, 1)

    def _build_result_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderLabels(["文件名", "大小"])
        self._file_tree.setColumnWidth(0, 280)
        self._file_tree.itemClicked.connect(self._on_file_clicked)
        splitter.addWidget(self._file_tree)

        self._file_view = QPlainTextEdit()
        self._file_view.setReadOnly(True)
        self._file_view.setFont(QFont("Monospace"))
        splitter.addWidget(self._file_view)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter, 1)
        return tab

    def _connect_signals(self) -> None:
        self._run_manager.lineOutput.connect(self._append_log)
        self._run_manager.stateChanged.connect(self._on_state)
        self._run_manager.runFinished.connect(self._on_finished)
        self._run_manager.error.connect(self._on_error)

    def set_idf(self, path: str) -> None:
        self._idf_path = path
        self._idf_label.setText(path)

    def start_run(self) -> bool:
        """启动运行，返回是否成功提交。"""
        if not self._idf_path:
            QMessageBox.warning(self, "警告", "请先选择 IDF 文件")
            return False
        ep_exe = self._config.get_ep_executable()
        if not ep_exe:
            QMessageBox.warning(self, "警告", "未找到 EnergyPlus 可执行文件，请检查设置")
            return False
        wf = self._weather.currentText().strip()
        if wf and not Path(wf).exists():
            wf = ""
        run_id = self._run_id.text().strip()
        extra = self._extra_args.text().strip()
        self._log.clear()
        request = RunRequest(
            idf_path=self._idf_path,
            weather_path=wf,
            run_id=run_id,
            extra_args=extra,
        )
        result = self._run_manager.start(ep_exe, request)
        return result is not None

    def _pick_idf(self) -> None:
        start = self._idf_path or self._config.config.last_idf_dir or "/"
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 IDF 文件", start, "IDF 文件 (*.idf);;所有文件 (*)"
        )
        if path:
            self.set_idf(path)
            self._config.config.last_idf_dir = str(Path(path).parent)
            self._config.save()

    def _pick_weather(self) -> None:
        start = self._config.config.weather_dir or self._config.config.energyplus_path or "/"
        path, _ = QFileDialog.getOpenFileName(
            self, "选择天气文件", start, "EPW 文件 (*.epw);;所有文件 (*)"
        )
        if path:
            if self._weather.findText(path) < 0:
                self._weather.addItem(path)
            self._weather.setCurrentText(path)
            self._config.config.last_weather_file = path
            self._config.save()

    def _refresh_weather(self) -> None:
        self._weather.clear()
        wd = self._config.config.weather_dir or self._config.get_default_weather_dir()
        if wd and Path(wd).exists():
            for epw in sorted(Path(wd).glob("*.epw")):
                self._weather.addItem(str(epw))
        last = self._config.config.last_weather_file
        if last:
            if self._weather.findText(last) < 0:
                self._weather.addItem(last)
            self._weather.setCurrentText(last)

    def _append_log(self, line: str) -> None:
        color: str | None = None
        if line.startswith("** Warning") or "Warning" in line:
            color = "#E5C07B"
        elif (
            line.startswith("** Error")
            or "Error" in line.lower()
            or (line.startswith("**") and "Fatal" in line)
        ):
            color = "#E06C75"
        elif line.startswith("=== "):
            color = "#56B6C2"
        if color:
            self._log.appendHtml(f'<span style="color:{color};">{line}</span>')
        else:
            self._log.appendPlainText(line)
        self._log.moveCursor(QTextCursor.End)

    def _on_state(self, state: str) -> None:
        running = state == EPRunner.STATE_RUNNING
        self._btn_run.setEnabled(not running)
        self._btn_cancel.setEnabled(running)
        if running:
            self._status.setText("运行中...")
            self._status.setStyleSheet("color: #E5C07B; font-weight: bold;")
        elif state == EPRunner.STATE_FINISHED:
            self._status.setText("完成")
            self._status.setStyleSheet("color: #98C379; font-weight: bold;")
        elif state == EPRunner.STATE_ERROR:
            self._status.setText("错误")
            self._status.setStyleSheet("color: #E06C75; font-weight: bold;")
        else:
            self._status.setText("就绪")
            self._status.setStyleSheet("color: gray;")

    def _on_finished(self, result: RunResult) -> None:
        self._populate_results(result)
        self.runFinished.emit(result)
        if result.success:
            QMessageBox.information(
                self,
                "运行完成",
                f"EnergyPlus 运行成功！\n耗时: {result.elapsed:.2f}s\n输出目录: {result.run_dir}",
            )
        else:
            QMessageBox.warning(
                self,
                "运行失败",
                f"EnergyPlus 运行失败 (退出码: {result.exit_code})\n请查看日志和 .err 文件",
            )

    def _on_error(self, msg: str) -> None:
        self._append_log(f"[错误] {msg}")

    def _populate_results(self, result: RunResult) -> None:
        self._file_tree.clear()
        run_dir = Path(result.run_dir)
        if not run_dir.exists():
            return
        for name in result.output_files:
            fpath = run_dir / name
            size = fpath.stat().st_size if fpath.exists() else 0
            size_str = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
            item = QTreeWidgetItem([name, size_str])
            item.setData(0, Qt.UserRole, str(fpath))
            if name.endswith(".err"):
                item.setForeground(0, QColor("#E06C75"))
            elif name.endswith(".csv"):
                item.setForeground(0, QColor("#98C379"))
            elif name.endswith(".eso"):
                item.setForeground(0, QColor("#56B6C2"))
            self._file_tree.addTopLevelItem(item)

    def _on_file_clicked(self, item: QTreeWidgetItem, _) -> None:
        path = item.data(0, Qt.UserRole)
        if not path or not Path(path).exists():
            return
        try:
            if Path(path).stat().st_size > 5 * 1024 * 1024:
                self._file_view.setPlainText("[文件过大，请使用外部编辑器查看]")
                return
            self._file_view.setPlainText(Path(path).read_text(encoding="utf-8", errors="replace"))
        except OSError as e:
            self._file_view.setPlainText(f"[读取失败: {e}]")
