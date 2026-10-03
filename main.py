"""EnergyPlus 图形化启动器主入口。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.config import config
from src.main_window import MainWindow


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("EnergyPlus Launcher")
    app.setOrganizationName("EnergyPlusLauncher")
    app.setStyle("Fusion")

    if config.theme == "dark":
        from PySide6.QtGui import QPalette, QColor
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
        app.setPalette(pal)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
