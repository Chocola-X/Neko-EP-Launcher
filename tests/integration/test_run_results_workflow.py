"""运行完成到主分析工作区的真实信号链与数据回归。"""

import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from src.app import Application
from src.services.ep_runner import RunResult
from src.services.results_service import ResultsService
from src.ui.main_window import MainWindow
from src.ui.results.results_view import ResultsView

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def workflow(qtbot, tmp_path, monkeypatch):
    container = Application(tmp_path / "config.json", tmp_path / "runs")
    executable = tmp_path / "ep" / "energyplus"
    executable.parent.mkdir()
    executable.touch()
    (executable.parent / "Energy+.idd").touch()
    container.config_service.config.energyplus_path = str(executable.parent)
    window = MainWindow(
        container.run_manager,
        container.idf_service,
        container.config_service,
        results_service=container.results_service,
        run_repository=container.run_repository,
    )
    qtbot.addWidget(window)
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args))
    window.show()
    yield container, window, messages
    qtbot.waitUntil(lambda: not window._results_workspace._timeseries_plot._jobs, timeout=10000)
    qtbot.waitUntil(lambda: window._results_workspace._report_job is None, timeout=10000)


def finish_run(container, directory: Path, success=True) -> RunResult:
    result = RunResult(
        directory.name,
        str(directory),
        str(directory / "input.idf"),
        success=success,
        exit_code=0 if success else 1,
    )
    container.ep_runner.finished.emit(result)
    return result


def test_completed_run_populates_only_main_analysis(workflow, qtbot, tmp_path) -> None:
    container, window, messages = workflow
    directory = tmp_path / "complete"
    shutil.copytree(FIXTURES / "test_run_001", directory)
    finish_run(container, directory)
    view = window._results_workspace
    assert window.findChildren(ResultsView) == [view]
    assert not window._run_panel.findChildren(ResultsView)
    assert window._editor_tabs.currentWidget() is view
    assert view._summary_view._report_list.count() > 0
    assert view._raw_view._file_tree.topLevelItemCount() > 0
    assert view._timeseries_plot._var_list.count() > 0
    qtbot.waitUntil(lambda: not view._timeseries_plot._jobs, timeout=10000)
    assert view._timeseries_plot._rows
    assert view._timeseries_plot._figure.axes
    assert messages


def test_html_only_previous_run_and_missing_sql_notice(workflow, tmp_path) -> None:
    container, window, _ = workflow
    directory = tmp_path / "html-only"
    directory.mkdir()
    shutil.copyfile(FIXTURES / "eplustbl-html-only.htm", directory / "eplustbl.htm")
    finish_run(container, directory)
    view = window._results_workspace
    assert view._summary_view._report_list.count() == 2
    assert view._tabs.currentWidget() is view._summary_view
    assert "未生成 SQLite" in view._status.text()
    assert "生成分析数据" in view._timeseries_plot._info_label.text() or "无 SQL" in (
        view._timeseries_plot._info_label.text()
    )


def test_failed_run_replaces_old_results_with_diagnostics(workflow, tmp_path, qtbot) -> None:
    container, window, _ = workflow
    directory = tmp_path / "complete"
    shutil.copytree(FIXTURES / "test_run_001", directory)
    finish_run(container, directory)
    view = window._results_workspace
    # 允许上次查询仍在途，切换后不能把旧数据写回。
    directory = tmp_path / "failed"
    directory.mkdir()
    (directory / "eplusout.err").write_text("   ** Fatal ** Bad model input\n")
    finish_run(container, directory, success=False)
    qtbot.waitUntil(lambda: not view._timeseries_plot._jobs, timeout=10000)
    assert view._run_dir == str(directory)
    assert view._error_view._table.rowCount() == 1
    assert view._tabs.currentWidget() is view._error_view
    assert view._summary_view._report_list.count() == 0
    assert view._summary_view._table_widget.rowCount() == 0
    assert view._timeseries_plot._reader is None
    assert not view._timeseries_plot._rows
    assert view._raw_view._file_tree.topLevelItemCount() == 1


@pytest.mark.parametrize("analysis_outputs", [True, False])
def test_run_button_prepares_copy_and_remembers_option(
    workflow, monkeypatch, tmp_path, qtbot, analysis_outputs
) -> None:
    container, window, _ = workflow
    source = tmp_path / "input.idf"
    original = "! 原始模型\nVersion, 9.4;\nZone, Z;\nOutput:SQLite, Simple;\n"
    source.write_text(original)
    window._open_file(str(source))
    assert window._run_panel._analysis_outputs.isChecked()
    window._run_panel._analysis_outputs.setChecked(analysis_outputs)
    captured = []

    def run(**kwargs):
        captured.append(kwargs)
        return RunResult("run", str(kwargs["run_dir"]), str(source))

    monkeypatch.setattr(container.ep_runner, "run", run)
    window._show_run_config()
    qtbot.mouseClick(window._run_panel._btn_run, Qt.LeftButton)
    assert len(captured) == 1
    assert source.read_text() == original
    copy = captured[0]["run_dir"] / source.name
    doc = container.idf_service.open(copy)
    assert doc.get_objects_by_type("Output:SQLite")[0].fields == [
        "SimpleAndTabular" if analysis_outputs else "Simple"
    ]
    assert len(doc.get_objects_by_type("Output:SQLite")) == 1
    assert bool(doc.get_objects_by_type("Output:Table:SummaryReports")) == analysis_outputs
    container.config_service.reload()
    assert container.config_service.config.analysis_outputs == analysis_outputs


def test_automatic_report_uses_main_workspace(workflow, tmp_path, qtbot) -> None:
    container, window, _ = workflow
    directory = tmp_path / "reported"
    directory.mkdir()
    shutil.copyfile(FIXTURES / "eplustbl-html-only.htm", directory / "eplustbl.htm")
    # 与 start_run 保存的运行选项一致，完成信号从真实运行器进入。
    window._run_panel._report_for_run = True
    finish_run(container, directory)
    view = window._results_workspace
    qtbot.waitUntil(lambda: view._report_job is None, timeout=10000)
    assert (directory / "enhanced-report.html").is_file()
    assert "<table" in (directory / "enhanced-report.html").read_text()
    assert view._report_button.isEnabled()


def test_history_opens_main_workspace(workflow, tmp_path) -> None:
    container, window, _ = workflow
    directory = tmp_path / "runs" / "previous"
    directory.mkdir()
    shutil.copyfile(FIXTURES / "eplustbl-html-only.htm", directory / "eplustbl.htm")
    finish_run(container, directory)
    history = window._history_view
    history._table.setCurrentCell(0, 0)
    window._editor_tabs.setCurrentWidget(window._editor)
    history._table.doubleClicked.emit(history._table.currentIndex())
    assert window._editor_tabs.currentWidget() is window._results_workspace
    assert window._results_workspace._run_dir == str(directory)


def test_loading_error_is_visible(workflow, monkeypatch, tmp_path) -> None:
    container, _window, messages = workflow
    monkeypatch.setattr(
        container.results_service, "load_tables", Mock(side_effect=ValueError("bad"))
    )
    finish_run(container, tmp_path)
    assert any("结果加载失败" in str(message) and "bad" in str(message) for message in messages)


@pytest.mark.parametrize("filename", ["eplustbl.htm", "customTable.htm", "custom-table.htm"])
def test_service_html_fallback_and_report(tmp_path, filename) -> None:
    shutil.copyfile(FIXTURES / "eplustbl-html-only.htm", tmp_path / filename)
    service = ResultsService()
    service.export_html_report(tmp_path, tmp_path / "enhanced-report.html")
    # 增强报告不能被再次当成原始数据解析。
    assert len(service.load_tables(tmp_path)) == 2
    assert "Site and Source Energy" in (tmp_path / "enhanced-report.html").read_text()


@pytest.mark.parametrize("name", ["smokeSqlite.err", "smoke-sqlite.err", "smokesqlite.err"])
def test_simulation_diagnostics_ignore_sqlite_log(tmp_path, name) -> None:
    (tmp_path / name).write_text("SQLite3 message")
    (tmp_path / "smoke.err").write_text("   ** Fatal ** Bad model input\n")
    errors = ResultsService().load_errors(tmp_path)
    assert len(errors) == 1
    assert errors[0].severity == "Fatal"


def test_html_report_ambiguity_and_read_failure(tmp_path, monkeypatch) -> None:
    source = tmp_path / "eplustbl.htm"
    source.write_text("content")
    (tmp_path / "otherTable.htm").write_text("content")
    service = ResultsService()
    with pytest.raises(ValueError, match="多个 HTML"):
        service.load_tables(tmp_path)
    (tmp_path / "otherTable.htm").unlink()
    monkeypatch.setattr(Path, "read_text", Mock(side_effect=OSError("unreadable")))
    assert service.load_tables(tmp_path) == []


def test_bad_run_copy_configuration_does_not_launch(workflow, tmp_path, monkeypatch) -> None:
    from src.services.run_manager import RunRequest

    container, _window, _messages = workflow
    source = tmp_path / "broken.idf"
    source.write_text("Zone, incomplete")
    launch = Mock()
    monkeypatch.setattr(container.ep_runner, "run", launch)
    assert (
        container.run_manager.start("energyplus", RunRequest(str(source), analysis_outputs=True))
        is None
    )
    launch.assert_not_called()
    assert source.read_text() == "Zone, incomplete"
