"""原始 HTML 汇总报告回归，包含真实输出与缺失单元格。"""

from pathlib import Path

from src.core.results.html_table_parser import HTMLTableParser

FIXTURE = Path(__file__).parents[1] / "fixtures" / "eplustbl-html-only.htm"


def test_real_html_report() -> None:
    tables = HTMLTableParser.parse_text(FIXTURE.read_text())
    assert len(tables) == 2
    first = tables[0]
    assert first.report_name == "Annual Building Utility Performance Summary"
    assert first.report_for == "Entire Facility"
    assert first.table_name == "Site and Source Energy"
    assert first.columns[0] == "Total Energy [GJ]"
    assert first.rows[0] == "Total Site Energy"
    assert first.cells[0] == ["0.00", "0.00", ""]


def test_ignore_navigation_and_empty_tables() -> None:
    text = """<table><tr><td>目录</td></tr></table>
    <!-- FullName:Report_Facility_Empty --><table></table>
    <!-- FullName:invalid --><table><tr><td>ignored</td></tr></table>
    <!-- FullName:Report_Facility_Heading --><table><tr><td>row</td></tr></table>"""
    assert HTMLTableParser.parse_text(text) == []


def test_entities_inline_markup_and_missing_cells() -> None:
    text = """<!-- FullName:Report_Facility_Table_With_Underscores -->
    <table><tr><th></th><th>One</th><th>Two</th></tr>
    <tr><td>A &amp; B</td><td><b>12</b><br>kWh</td></tr>
    <tr><td>C</td><td>&nbsp;</td><td>3</td></tr></table>"""
    table = HTMLTableParser.parse_text(text)[0]
    assert table.table_name == "Table_With_Underscores"
    assert table.rows == ["A & B", "C"]
    assert table.cells == [["12 kWh", ""], ["", "3"]]
