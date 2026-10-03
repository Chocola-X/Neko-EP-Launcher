"""设置对话框：配置 EnergyPlus 路径、天气文件等。"""
import os
from pathlib import Path

from PySide6.QtCore import Qt, QDir
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout, QLineEdit, QPushButton,
    QFileDialog, QLabel, QGroupBox, QComboBox, QCheckBox, QDialogButtonBox,
    QMessageBox, QTabWidget, QWidget
)

from .config import Config, config


class SettingsDialog(QDialog):
    """设置对话框。"""

    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self.setWindowTitle("设置")
        self.setMinimumWidth(640)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "通用")
        tabs.addTab(self._build_run_tab(), "运行")
        tabs.addTab(self._build_paths_tab(), "路径")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel |
            QDialogButtonBox.Apply
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self._apply)
        layout.addWidget(buttons)

        self._validate_ep_path()

    def _build_general_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        group = QGroupBox("外观")
        g_layout = QFormLayout(group)
        self._theme = QComboBox()
        self._theme.addItems(["system", "light", "dark", "fusion"])
        self._theme.setCurrentText(self._cfg.theme)
        g_layout.addRow("主题:", self._theme)
        layout.addWidget(group)
        layout.addStretch()
        return tab

    def _build_run_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        ep_group = QGroupBox("EnergyPlus 可执行文件")
        ep_layout = QFormLayout(ep_group)
        self._ep_path = QLineEdit(self._cfg.energyplus_path)
        ep_btn = QPushButton("浏览...")
        ep_btn.clicked.connect(self._browse_ep)
        ep_row = QHBoxLayout()
        ep_row.addWidget(self._ep_path, 1)
        ep_row.addWidget(ep_btn)
        ep_layout.addRow("EnergyPlus 目录:", ep_row)

        self._ep_status = QLabel("")
        self._ep_status.setWordWrap(True)
        ep_layout.addRow("状态:", self._ep_status)
        layout.addWidget(ep_group)

        opt_group = QGroupBox("运行参数")
        opt_layout = QFormLayout(opt_group)
        self._run_options = QLineEdit(self._cfg.run_options)
        self._run_options.setPlaceholderText("例如: -r -p")
        opt_layout.addRow("附加参数:", self._run_options)
        layout.addWidget(opt_group)

        self._ep_path.textChanged.connect(self._validate_ep_path)
        return tab

    def _build_paths_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        wd_group = QGroupBox("天气文件目录")
        wd_layout = QFormLayout(wd_group)
        self._weather_dir = QLineEdit(self._cfg.weather_dir)
        wd_btn = QPushButton("浏览...")
        wd_btn.clicked.connect(self._browse_weather_dir)
        wd_row = QHBoxLayout()
        wd_row.addWidget(self._weather_dir, 1)
        wd_row.addWidget(wd_btn)
        wd_layout.addRow("目录:", wd_row)

        auto_btn = QPushButton("使用 EnergyPlus 默认天气目录")
        auto_btn.clicked.connect(self._use_default_weather)
        wd_layout.addRow("", auto_btn)
        layout.addWidget(wd_group)

        wf_group = QGroupBox("默认天气文件")
        wf_layout = QFormLayout(wf_group)
        self._weather_file = QLineEdit(self._cfg.last_weather_file)
        wf_btn = QPushButton("浏览...")
        wf_btn.clicked.connect(self._browse_weather_file)
        wf_row = QHBoxLayout()
        wf_row.addWidget(self._weather_file, 1)
        wf_row.addWidget(wf_btn)
        wf_layout.addRow("文件:", wf_row)
        layout.addWidget(wf_group)

        layout.addStretch()
        return tab

    def _browse_ep(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择 EnergyPlus 目录", self._ep_path.text() or "/")
        if path:
            self._ep_path.setText(path)

    def _browse_weather_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择天气文件目录", self._weather_dir.text() or "/")
        if path:
            self._weather_dir.setText(path)

    def _use_default_weather(self):
        ep = self._ep_path.text().strip()
        if ep:
            wd = Path(ep) / "WeatherData"
            if wd.exists():
                self._weather_dir.setText(str(wd))
                return
        QMessageBox.information(self, "提示", "未找到默认天气目录。")

    def _browse_weather_file(self):
        start = self._weather_dir.text() or self._ep_path.text() or "/"
        path, _ = QFileDialog.getOpenFileName(
            self, "选择天气文件", start, "EPW 文件 (*.epw);;所有文件 (*)")
        if path:
            self._weather_file.setText(path)

    def _validate_ep_path(self):
        ep = self._ep_path.text().strip()
        if not ep:
            self._ep_status.setText("未设置")
            self._ep_status.setStyleSheet("color: gray;")
            return
        p = Path(ep)
        if not p.exists():
            self._ep_status.setText("目录不存在")
            self._ep_status.setStyleSheet("color: red;")
            return
        exe = None
        for name in ("energyplus", "energyplus-9.4.0"):
            cand = p / name
            if cand.exists() and os.access(cand, os.X_OK):
                exe = cand
                break
        idd = p / "Energy+.idd"
        if exe and idd.exists():
            self._ep_status.setText(f"有效 (可执行: {exe.name})")
            self._ep_status.setStyleSheet("color: green;")
        elif exe:
            self._ep_status.setText("找到可执行文件，但缺少 Energy+.idd")
            self._ep_status.setStyleSheet("color: orange;")
        else:
            self._ep_status.setText("未找到 energyplus 可执行文件")
            self._ep_status.setStyleSheet("color: red;")

    def _apply(self):
        self._cfg.energyplus_path = self._ep_path.text().strip()
        self._cfg.weather_dir = self._weather_dir.text().strip()
        self._cfg.last_weather_file = self._weather_file.text().strip()
        self._cfg.theme = self._theme.currentText()
        self._cfg.run_options = self._run_options.text().strip()
        self._cfg.save()

    def _on_accept(self):
        self._apply()
        self.accept()
