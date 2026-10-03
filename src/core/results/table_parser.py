"""``eplustbl.xml`` 表格汇总报告解析器。依据 R-4d。

XML 结构：
::

    <EnergyPlusTabularReports>
      <AnnualBuildingUtilityPerformanceSummary>
        <for>Entire Facility</for>
        <SiteAndSourceEnergy>
          <name>TotalSiteEnergy</name>
          <TotalEnergy units="GJ">82.42</TotalEnergy>
          ...
        </SiteAndSourceEnergy>
      </AnnualBuildingUtilityPerformanceSummary>
    </EnergyPlusTabularReports>

每个顶层报告节点（如 ``AnnualBuildingUtilityPerformanceSummary``）含一个 ``<for>``
子节点和若干表格节点。表格节点的子节点含 ``<name>`` 行名和带 ``units`` 属性的数据列。
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from src.core.exceptions import ResultParseError
from src.core.results.models import ReportTable

logger = logging.getLogger(__name__)


class TableParser:
    """``eplustbl.xml`` 解析器。"""

    def parse_file(self, path: str | Path) -> list[ReportTable]:
        """解析 eplustbl.xml 为表格列表。

        Raises:
            ResultParseError: 文件无法读取或 XML 格式错误。
        """
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise ResultParseError(f"无法读取 eplustbl.xml: {e}") from e
        return self.parse_text(text)

    def parse_text(self, text: str) -> list[ReportTable]:
        """解析 XML 文本。

        Raises:
            ResultParseError: XML 格式错误。
        """
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            raise ResultParseError(f"XML 解析错误: {e}") from e

        tables: list[ReportTable] = []

        for report_node in root:
            report_name = report_node.tag
            report_for = ""
            notes: list[str] = []
            for child in report_node:
                if child.tag == "for":
                    report_for = (child.text or "").strip()
                elif child.tag == "note" and child.text:
                    notes.append(child.text.strip())

            table_groups: dict[str, list[ET.Element]] = {}
            for table_node in report_node:
                if table_node.tag in ("for", "note"):
                    continue
                table_groups.setdefault(table_node.tag, []).append(table_node)

            for table_name, row_nodes in table_groups.items():
                table = self._parse_table(
                    report_name, report_for, table_name, row_nodes, notes
                )
                if table is not None:
                    tables.append(table)

        logger.info("eplustbl.xml 解析完成: %d 张表格", len(tables))
        return tables

    @staticmethod
    def _parse_table(
        report_name: str,
        report_for: str,
        table_name: str,
        row_nodes: list[ET.Element],
        notes: list[str],
    ) -> ReportTable | None:
        """解析单个表格（同名节点按行分组）。

        每个行节点的子节点中 ``<name>`` 为行名，其余为数据列。
        """
        columns: list[str] = []
        rows: list[str] = []
        cells: list[list[str]] = []

        for row_node in row_nodes:
            row_name = ""
            row_values: list[str] = []

            for cell_node in row_node:
                tag = cell_node.tag
                text_val = (cell_node.text or "").strip()
                if tag == "name":
                    row_name = text_val
                else:
                    if tag not in columns:
                        columns.append(tag)
                    units = cell_node.get("units", "")
                    if units:
                        row_values.append(f"{text_val} [{units}]")
                    else:
                        row_values.append(text_val)

            if row_name:
                rows.append(row_name)
                while len(row_values) < len(columns):
                    row_values.append("")
                cells.append(row_values)

        if not rows:
            return None

        return ReportTable(
            report_name=report_name,
            report_for=report_for,
            table_name=table_name,
            columns=columns,
            rows=rows,
            cells=cells,
            notes=notes,
        )
