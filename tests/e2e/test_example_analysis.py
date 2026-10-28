"""可选本地验收：从运行按钮到真实 EnergyPlus 数据、曲线与增强报告。"""

import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from src.app import Application
from src.ui.main_window import MainWindow
from src.ui.results.results_view import ResultsView


@pytest.mark.e2e
@pytest.mark.parametrize("arguments", ["-D", "-D -p smoke -s C"])
def test_official_example_analysis(qtbot, tmp_path, monkeypatch, arguments) -> None:
    installation = os.environ.get("ENERGYPLUS_HOME")
    if not installation:
        pytest.skip("设置 ENERGYPLUS_HOME 后运行真实模拟")
    root = Path(installation)
    example = root / "ExampleFiles" / "1ZoneUncontrolled_DDChanges.idf"
    original = example.read_bytes()
    container = Application(tmp_path / "config.json", tmp_path / "runs")
    container.config_service.config.energyplus_path = str(root)
    container.config_service.config.run_options = arguments
    container.config_service.config.enhanced_report = True
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args))
    window = MainWindow(
        container.run_manager,
        container.idf_service,
        container.config_service,
        results_service=container.results_service,
        run_repository=container.run_repository,
    )
    qtbot.addWidget(window)
    window.show()
    window._open_file(str(example))
    window._show_run_config()
    with qtbot.waitSignal(container.run_manager.runFinished, timeout=120000) as completed:
        qtbot.mouseClick(window._run_panel._btn_run, Qt.LeftButton)
    result = completed.args[0]
    assert result.success, result.log_text
    assert example.read_bytes() == original
    view = window._results_workspace
    assert window.findChildren(ResultsView) == [view]
    assert window._editor_tabs.currentWidget() is view
    assert view._summary_view._report_list.count() > 0
    assert view._timeseries_plot._var_list.count() > 0
    qtbot.waitUntil(lambda: not view._timeseries_plot._jobs, timeout=30000)
    assert view._timeseries_plot._rows
    assert view._timeseries_plot._figure.axes[0].lines
    qtbot.waitUntil(lambda: view._report_job is None, timeout=30000)
    report = Path(result.run_dir) / "enhanced-report.html"
    assert report.is_file()
    assert "<svg" in report.read_text()
    assert "<table" in report.read_text()
    assert messages
