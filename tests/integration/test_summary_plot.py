"""以真实结果验证饼图百分比和导出。"""

from pathlib import Path
from unittest.mock import Mock

from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.core.results.table_parser import TableParser
from src.ui.results.summary_plot import SummaryPlotView


def test_summary_plot_excludes_total_from_pie(qtbot, tmp_path: Path, monkeypatch) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "test_run_001" / "eplustbl.xml"
    table = next(t for t in TableParser().parse_file(fixture) if t.table_name == "EndUses")
    view = SummaryPlotView()
    qtbot.addWidget(view)
    view.set_tables([table])
    view._table_list.setCurrentRow(0)
    assert view._figure.axes[0].get_ylabel() == "Electricity [GJ]"
    view._chart_type.setCurrentText("饼图")
    assert [text.get_text() for text in view._figure.axes[0].texts] == [
        "ExteriorLighting", "100.0%",
    ]
    output = tmp_path / "chart.png"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_: (str(output), ""))
    monkeypatch.setattr(QMessageBox, "information", Mock())
    view._btn_export.click()
    assert output.read_bytes().startswith(b"\x89PNG")
    view._column.setCurrentText("NaturalGas")
    assert not view._figure.axes
    assert "正数" in view._notice.text()
    assert not view._btn_export.isEnabled()
