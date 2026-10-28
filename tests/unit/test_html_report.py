"""离线报告生成及模型文本转义测试。"""

from src.core.results.html_report import bar_chart, build_report, line_chart
from src.core.results.models import ErrorRecord, ReportTable


def test_report_escapes_model_text() -> None:
    payload = "<script>alert(1)</script>"
    table = ReportTable(payload, "", payload, ["x"], [payload], [[payload]])
    html = build_report(payload, payload, [ErrorRecord("Warning", payload)], [table], [], [payload])
    assert payload not in html
    assert "&lt;script&gt;" in html
    assert 'src="http' not in html and 'href="http' not in html
    assert "筛选报告" in html


def test_curve_empty_nonfinite_constant_and_sampling() -> None:
    assert line_chart("none", []) == ""
    assert line_chart("none", [("t", float("nan"))]) == ""
    html = line_chart("Temperature [C]", [(str(i), 2.0) for i in range(1500)])
    assert "<svg" in html and "1500 条记录" in html
    assert html.count("<circle") <= 600


def test_energy_columns_and_empty_chart() -> None:
    assert bar_chart(ReportTable("r", "", "t")) == ""
    table = ReportTable(
        "r", "", "EndUses", ["Electricity", "Other"], ["Heating"], [["4 [GJ]", "8"]]
    )
    html = bar_chart(table)
    assert "Electricity" in html and "4 [GJ]" in html
    assert ">8<" not in html
    table.cells = [["invalid", "8"]]
    assert bar_chart(table) == ""
