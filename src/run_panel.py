"""运行面板：配置运行参数、显示实时输出、查看结果文件。"""
import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QComboBox, QLabel, QPlainTextEdit, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QGroupBox,
    QSplitter, QTreeWidget, QTreeWidgetItem, QCheckBox
)

from .config import config
from .ep_runner import EPRunner, RunResult


class RunPanel(QWidget):
    """运行面板。"""

    runStarted = Signal(str)
    runFinished = Signal(object)

    def __init__(self, runner: EPRunner, parent=None):
        super().__init__(parent)
        self._runner = runner
        self._idf_path = ""
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
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

        self._extra_args = QLineEdit(config.run_options)
        self._extra_args.setPlaceholderText("例如: -r -p")
        config_layout.addRow("附加参数:", self._extra_args)

        layout.addWidget(config_group)

        btn_row = QHBoxLayout()
        self._btn_run = QPushButton("运行")
        self._btn_run.setStyleSheet(
            "QPushButton { background-color: #98C379; color: black; "
            "font-weight: bold; padding: 6px 20px; }"
            "QPushButton:disabled { background-color: #7F848E; }")
        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setEnabled(False)
        self._btn_cancel.setStyleSheet(
            "QPushButton { background-color: #E06C75; color: black; "
            "padding: 6px 20px; }")
        self._btn_run.clicked.connect(self._start_run)
        self._btn_cancel.clicked.connect(self._runner.cancel)
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

    def _build_result_tab(self):
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

    def _connect_signals(self):
        self._runner.lineOutput.connect(self._append_log)
        self._runner.stateChanged.connect(self._on_state)
        self._runner.finished.connect(self._on_finished)
        self._runner.error.connect(self._on_error)

    def set_idf(self, path):
        self._idf_path = path
        self._idf_label.setText(path)

    def _pick_idf(self):
        start = self._idf_path or config.last_idf_dir or "/"
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 IDF 文件", start,
            "IDF 文件 (*.idf);;所有文件 (*)")
        if path:
            self.set_idf(path)
            config.last_idf_dir = str(Path(path).parent)
            config.save()

    def _pick_weather(self):
        start = config.weather_dir or config.energyplus_path or "/"
        path, _ = QFileDialog.getOpenFileName(
            self, "选择天气文件", start,
            "EPW 文件 (*.epw);;所有文件 (*)")
        if path:
            if self._weather.findText(path) < 0:
                self._weather.addItem(path)
            self._weather.setCurrentText(path)
            config.last_weather_file = path
            config.save()

    def _refresh_weather(self):
        self._weather.clear()
        wd = config.weather_dir or config.get_default_weather_dir()
        if wd and Path(wd).exists():
            for epw in sorted(Path(wd).glob("*.epw")):
                self._weather.addItem(str(epw))
        if config.last_weather_file:
            if self._weather.findText(config.last_weather_file) < 0:
                self._weather.addItem(config.last_weather_file)
            self._weather.setCurrentText(config.last_weather_file)

    def _start_run(self):
        if not self._idf_path:
            QMessageBox.warning(self, "警告", "请先选择 IDF 文件")
            return
        ep_exe = config.get_ep_executable()
        if not ep_exe:
            QMessageBox.warning(self, "警告",
                                "未找到 EnergyPlus 可执行文件，请检查设置")
            return
        wf = self._weather.currentText().strip()
        if wf and not Path(wf).exists():
            wf = ""
        run_id = self._run_id.text().strip()
        extra = self._extra_args.text().strip()
        self._log.clear()
        self._runner.run(ep_exe, self._idf_path, wf, extra, run_id)

    def _append_log(self, line):
        color = None
        if line.startswith("** Warning") or "Warning" in line:
            color = "#E5C07B"
        elif line.startswith("** Error") or "Error" in line.lower():
            color = "#E06C75"
        elif line.startswith("**") and "Fatal" in line:
            color = "#E06C75"
        elif line.startswith("=== "):
            color = "#56B6C2"
        if color:
            self._log.appendHtml(
                f'<span style="color:{color};">{line}</span>')
        else:
            self._log.appendPlainText(line)
        self._log.moveCursor(QTextCursor.End)

    def _on_state(self, state):
        running = (state == EPRunner.STATE_RUNNING)
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

    def _on_finished(self, result: RunResult):
        self._populate_results(result)
        self.runFinished.emit(result)
        if result.success:
            QMessageBox.information(
                self, "运行完成",
                f"EnergyPlus 运行成功！\n耗时: {result.elapsed:.2f}s\n"
                f"输出目录: {result.run_dir}")
        else:
            QMessageBox.warning(
                self, "运行失败",
                f"EnergyPlus 运行失败 (退出码: {result.exit_code})\n"
                f"请查看日志和 .err 文件")

    def _on_error(self, msg):
        self._append_log(f"[错误] {msg}")

    def _populate_results(self, result: RunResult):
        self._file_tree.clear()
        run_dir = Path(result.run_dir)
        if not run_dir.exists():
            return
        for name in result.output_files:
            fpath = run_dir / name
            size = fpath.stat().st_size if fpath.exists() else 0
            size_str = f"{size/1024:.1f} KB" if size >= 1024 else f"{size} B"
            item = QTreeWidgetItem([name, size_str])
            item.setData(0, Qt.UserRole, str(fpath))
            if name.endswith(".err"):
                item.setForeground(0, QColor("#E06C75"))
            elif name.endswith(".csv"):
                item.setForeground(0, QColor("#98C379"))
            elif name.endswith(".eso"):
                item.setForeground(0, QColor("#56B6C2"))
            self._file_tree.addTopLevelItem(item)

    def _on_file_clicked(self, item, _):
        path = item.data(0, Qt.UserRole)
        if not path or not Path(path).exists():
            return
        try:
            if Path(path).stat().st_size > 5 * 1024 * 1024:
                self._file_view.setPlainText(
                    "[文件过大，请使用外部编辑器查看]")
                return
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                self._file_view.setPlainText(f.read())
        except Exception as e:
            self._file_view.setPlainText(f"[读取失败: {e}]")
