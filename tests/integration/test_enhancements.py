"""编辑与分析工作流回归测试。"""

from pathlib import Path

import pytest

from src.app import Application
from src.core.exceptions import ResultParseError
from src.core.idd.models import FieldDef, IDDDocument, ObjectDef
from src.core.results.models import ReportTable
from src.core.results.sql_reader import SQLReader
from src.services.idf_service import IDFService
from src.services.results_service import ResultsService
from src.ui.main_window import MainWindow
from src.ui.results.summary_plot import SummaryPlotView
from src.ui.results.timeseries_plot import TimeseriesPlotView

FIXTURE = Path(__file__).parents[1] / "fixtures" / "test_run_001"


def test_output_configuration_idempotent() -> None:
    service = IDFService()
    doc = service.parse("! model\nZone, Z;\nOutput:SQLite, Simple;\n")
    service.configure_outputs(doc)
    service.configure_outputs(doc)
    assert len(doc.get_objects_by_type("Output:SQLite")) == 1
    assert doc.get_objects_by_type("Output:SQLite")[0].fields == ["SimpleAndTabular"]
    assert service.add_output(doc, "Zone Mean Air Temperature", False)
    assert not service.add_output(doc, "Zone Mean Air Temperature", False)
    assert service.add_output(doc, "Electricity:Facility", True)
    assert len(service.parse(service.serialize(doc)).objects) == 6


def test_missing_required_and_invalid_integer() -> None:
    idd = IDDDocument()
    idd.add(ObjectDef("Test", fields=[FieldDef("Count", type="integer", required=True)]))
    service = IDFService()
    for text in ["Test;", "Test, 1.5;", "Test, nan;"]:
        assert service.validate(service.parse(text), idd)


def test_sql_readonly_and_custom_prefix(tmp_path: Path) -> None:
    path = tmp_path / "absent.sql"
    with pytest.raises(ResultParseError):
        SQLReader(path).open()
    assert not path.exists()
    (tmp_path / "custom.err").write_text("")
    assert ResultsService.find_output(tmp_path, ".err", "eplusout.err").name == "custom.err"
    (tmp_path / "another.err").write_text("")
    with pytest.raises(ValueError):
        ResultsService.find_output(tmp_path, ".err", "eplusout.err")


def test_csv_export(tmp_path: Path) -> None:
    output = tmp_path / "data.csv"
    ResultsService.export_csv(str(output), ["时间", "值"], [["a,b", "2"]])
    assert '"a,b",2' in output.read_text(encoding="utf-8-sig")


def test_summary_uses_selected_column() -> None:
    table = ReportTable("Report", "Facility", "Energy", ["A", "B"], ["row"], [["1", "8"]])
    assert SummaryPlotView._extract_numeric_data(table, 1) == [("row", 8.0)]


def test_async_timeseries(qtbot) -> None:
    view = TimeseriesPlotView()
    qtbot.addWidget(view)
    reader = SQLReader(FIXTURE / "eplusout.sql")
    reader.open()
    view.set_reader(reader)
    view._var_list.setCurrentRow(0)
    qtbot.waitUntil(lambda: not view._jobs, timeout=10000)
    assert view._rows
    assert view._figure.axes
    assert view._data_table.rowCount() > 0
    view.clear()
    with pytest.raises(ResultParseError):
        _ = reader.connection


def test_editor_sync_and_field_undo(qtbot, tmp_path: Path) -> None:
    app = Application(tmp_path / "config.json", tmp_path / "runs")
    window = MainWindow(
        app.run_manager, app.idf_service, app.config_service, app.idd_service, app.results_service
    )
    qtbot.addWidget(window)
    window._new_file()
    window._editor.setPlainText("! keep\nZone, A;\n")
    window._auto_sync()
    obj = window._doc.objects[0]
    obj.set_field(0, "B")
    window._on_object_changed(obj)
    assert window._editor.toPlainText() == "! keep\nZone, B;\n"
    window._editor.undo()
    assert window._editor.toPlainText() == "! keep\nZone, A;\n"
    window._modified = False


def test_offline_report_from_real_results(tmp_path: Path) -> None:
    output = tmp_path / "report.html"
    result = ResultsService().export_html_report(FIXTURE, output)
    assert result == str(output)
    html = output.read_text()
    assert "<svg" in html and "<table" in html
    assert "Site Outdoor Air" in html or "Temperature" in html
    assert "https://" not in html


def test_report_with_missing_outputs(tmp_path: Path) -> None:
    output = tmp_path / "report.html"
    ResultsService().export_html_report(tmp_path, output)
    assert "没有 SQLite" in output.read_text()
    with pytest.raises(ValueError):
        ResultsService().export_html_report(tmp_path, tmp_path / "eplustbl.htm")


def test_sql_fallback_summary(tmp_path: Path) -> None:
    import shutil

    shutil.copyfile(FIXTURE / "eplusout.sql", tmp_path / "custom.sql")
    tables = ResultsService().load_tables(tmp_path)
    assert tables
    assert any("Energy" in t.table_name for t in tables)


def test_report_background_export(qtbot, tmp_path: Path, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    from src.ui.results.results_view import ResultsView

    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args))
    view = ResultsView(ResultsService())
    qtbot.addWidget(view)
    output = tmp_path / "enhanced.html"
    view.generate_report(str(FIXTURE), str(output))
    qtbot.waitUntil(lambda: view._report_job is None, timeout=10000)
    assert output.is_file()
    assert messages
    assert view._report_button.isEnabled()


def test_open_action_displays_picker(qtbot, tmp_path: Path, monkeypatch) -> None:
    from PySide6.QtWidgets import QFileDialog

    calls = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (calls.append(args) or ("", "")))
    container = Application(tmp_path / "config.json", tmp_path / "runs")
    window = MainWindow(container.run_manager, container.idf_service, container.config_service)
    qtbot.addWidget(window)
    window._act_open.trigger()
    assert len(calls) == 1
