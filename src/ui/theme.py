"""主题与调色板。"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_theme(theme: str) -> None:
    """应用主题。

    Args:
        theme: 主题名（system/light/dark/fusion）。
    """
    if theme == "dark":
        _apply_dark()
    elif theme == "light":
        QApplication.setPalette(QApplication.style().standardPalette())
    elif theme == "fusion":
        QApplication.setStyle("Fusion")


def _apply_dark() -> None:
    """应用暗色主题。"""
    QApplication.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(40, 44, 52))
    pal.setColor(QPalette.WindowText, QColor(220, 220, 220))
    pal.setColor(QPalette.Base, QColor(29, 32, 38))
    pal.setColor(QPalette.AlternateBase, QColor(40, 44, 52))
    pal.setColor(QPalette.Text, QColor(220, 220, 220))
    pal.setColor(QPalette.Button, QColor(60, 64, 72))
    pal.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    pal.setColor(QPalette.Highlight, QColor(86, 182, 194))
    pal.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    QApplication.setPalette(pal)
