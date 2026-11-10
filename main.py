"""Neko-EP-Launcher 主入口（<30 行）。"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.app import Application, setup_logging


def main() -> int:
    setup_logging()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Neko-EP-Launcher")
    app.setOrganizationName("Neko-EP-Launcher")

    container = Application()
    container.apply_theme()
    container.load_idd()
    container.create_window()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
