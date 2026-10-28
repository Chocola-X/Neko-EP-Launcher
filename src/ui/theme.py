"""系统原生外观与可选调色板，支持从自定义主题恢复。"""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class ThemeController(QObject):
    """按 QApplication 保存原生样式，避免模块单例和启动时覆盖系统设置。"""

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self.setObjectName("launcherThemeController")
        self._app = app
        self._native_style = app.style().objectName()
        self._native_palette = QPalette(app.palette())
        self._theme = "system"
        hints = app.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._system_changed)

    def _system_changed(self) -> None:
        if self._theme == "system":
            self._native_palette = self._app.style().standardPalette()
            self._app.setPalette(self._native_palette)

    def apply(self, theme: str) -> None:
        """恢复原生外观，或显式选用浅色、深色、Fusion。"""
        previous = self._theme
        self._theme = theme
        self._app.setStyleSheet("")
        if theme == "system":
            if previous != "system":
                self._app.setStyle(self._native_style)
                self._app.setPalette(self._native_palette)
            return
        self._app.setStyle("Fusion")
        palette = self._app.style().standardPalette()
        if theme == "dark":
            for role, color in [
                (QPalette.Window, "#282c34"),
                (QPalette.WindowText, "#dcdcdc"),
                (QPalette.Base, "#1d2026"),
                (QPalette.AlternateBase, "#282c34"),
                (QPalette.Text, "#dcdcdc"),
                (QPalette.Button, "#3c4048"),
                (QPalette.ButtonText, "#dcdcdc"),
                (QPalette.Highlight, "#56b6c2"),
                (QPalette.HighlightedText, "#000000"),
            ]:
                palette.setColor(role, QColor(color))
        self._app.setPalette(palette)


def apply_theme(theme: str) -> None:
    """设置主题，默认跟随 Qt 平台插件提供的系统外观。"""
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    controller = app.findChild(ThemeController, "launcherThemeController")
    if controller is None:
        controller = ThemeController(app)
    controller.apply(theme)
