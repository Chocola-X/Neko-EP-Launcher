"""EnergyPlus 图形化启动器主入口（<30 行）。"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.app import Application, setup_logging
from src.ui.main_window import MainWindow


def main() -> int:
    setup_logging()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("EnergyPlus Launcher")
    app.setOrganizationName("EnergyPlusLauncher")
    app.setStyle("Fusion")

    container = Application()
    container.apply_theme()
    container.load_idd()
    window = MainWindow(
        run_manager=container.run_manager,
        idf_service=container.idf_service,
        config_service=container.config_service,
        idd_service=container.idd_service,
        results_service=container.results_service,
        run_repository=container.run_repository,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
