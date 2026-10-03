"""``table_parser`` 单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.exceptions import ResultParseError
from src.core.results.table_parser import TableParser

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "test_run_001"


class TestTableParser:
    """TableParser 测试。"""

    def setup_method(self) -> None:
        self.parser = TableParser()

    def test_parse_real_file(self) -> None:
        """解析真实 eplustbl.xml。"""
        xml_path = FIXTURES / "eplustbl.xml"
        tables = self.parser.parse_file(xml_path)
        assert len(tables) > 0
        assert any(t.report_name == "AnnualBuildingUtilityPerformanceSummary" for t in tables)

    def test_parse_simple_xml(self) -> None:
        """解析简单 XML。"""
        text = """<?xml version="1.0"?>
<EnergyPlusTabularReports>
  <AnnualBuildingUtilityPerformanceSummary>
    <for>Entire Facility</for>
    <SiteAndSourceEnergy>
      <name>TotalSiteEnergy</name>
      <TotalEnergy units="GJ">82.42</TotalEnergy>
      <EnergyPerTotalBuildingArea units="MJ/m2">354.86</EnergyPerTotalBuildingArea>
    </SiteAndSourceEnergy>
  </AnnualBuildingUtilityPerformanceSummary>
</EnergyPlusTabularReports>
"""
        tables = self.parser.parse_text(text)
        assert len(tables) == 1
        t = tables[0]
        assert t.report_name == "AnnualBuildingUtilityPerformanceSummary"
        assert t.report_for == "Entire Facility"
        assert t.table_name == "SiteAndSourceEnergy"
        assert "TotalEnergy" in t.columns
        assert "EnergyPerTotalBuildingArea" in t.columns
        assert t.rows[0] == "TotalSiteEnergy"
        assert "82.42" in t.cells[0][0]

    def test_parse_empty(self) -> None:
        """空报告节点返回空列表。"""
        text = '<?xml version="1.0"?>\n<EnergyPlusTabularReports>\n</EnergyPlusTabularReports>'
        tables = self.parser.parse_text(text)
        assert tables == []

    def test_parse_invalid_xml(self) -> None:
        """无效 XML 抛异常。"""
        with pytest.raises(ResultParseError):
            self.parser.parse_text("not valid xml <<")

    def test_parse_file_not_found(self) -> None:
        """文件不存在应抛异常。"""
        with pytest.raises(ResultParseError):
            self.parser.parse_file("/nonexistent/tables.xml")

    def test_table_with_note(self) -> None:
        """含 note 的表格。"""
        text = """<?xml version="1.0"?>
<EnergyPlusTabularReports>
  <SomeReport>
    <for>Entire Facility</for>
    <note>Some note text</note>
    <SomeTable>
      <name>Row1</name>
      <Col1>100</Col1>
    </SomeTable>
  </SomeReport>
</EnergyPlusTabularReports>
"""
        tables = self.parser.parse_text(text)
        assert len(tables) == 1
        assert tables[0].rows[0] == "Row1"
        assert tables[0].columns[0] == "Col1"
        assert tables[0].cells[0][0] == "100"
