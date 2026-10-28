"""EnergyPlus HTML 汇总表解析，依据 R-4d 与 9.4 原始报告结构。"""

from __future__ import annotations

from html.parser import HTMLParser

from src.core.results.models import ReportTable


class HTMLTableParser(HTMLParser):
    """读取原始报告的 FullName 标记与表格，忽略目录和页面导航。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._name: tuple[str, str, str] | None = None
        self._inside_table = False
        self._inside_cell = False
        self._cell: list[str] = []
        self._row: list[str] = []
        self._rows: list[list[str]] = []
        self.tables: list[ReportTable] = []

    def handle_comment(self, data: str) -> None:
        """读取 EnergyPlus 在每张数据表前写入的来源名称。"""
        data = data.strip()
        if data.startswith("FullName:"):
            parts = data[len("FullName:") :].split("_", 2)
            self._name = (parts[0], parts[1], parts[2]) if len(parts) == 3 else None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """收集单元格内容，保留换行间隔与内联格式中的文本。"""
        if tag == "table" and self._name is not None:
            self._inside_table = True
            self._rows = []
        elif self._inside_table:
            if tag == "tr":
                self._row = []
            elif tag in ("td", "th"):
                self._inside_cell = True
                self._cell = []
            elif tag == "br" and self._inside_cell:
                self._cell.append(" ")

    def handle_data(self, data: str) -> None:
        """累积已解码 HTML 实体的单元格文本。"""
        if self._inside_cell:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        """把行列转换成与 XML/SQLite 相同的 ReportTable。"""
        if not self._inside_table:
            return
        if tag in ("td", "th") and self._inside_cell:
            self._row.append(" ".join("".join(self._cell).split()))
            self._inside_cell = False
        elif tag == "tr" and self._row:
            self._rows.append(self._row)
            self._row = []
        elif tag == "table":
            if self._name is not None and len(self._rows) > 1:
                columns = self._rows[0][1:]
                if columns:
                    self.tables.append(
                        ReportTable(
                            *self._name,
                            columns=columns,
                            rows=[row[0] for row in self._rows[1:]],
                            cells=[
                                (row[1:] + [""] * len(columns))[: len(columns)]
                                for row in self._rows[1:]
                            ],
                        )
                    )
            self._inside_table = False
            self._inside_cell = False
            self._name = None

    @classmethod
    def parse_text(cls, text: str) -> list[ReportTable]:
        """解析一份完整 HTML 文本；无数据表时返回空列表。"""
        parser = cls()
        parser.feed(text)
        parser.close()
        return parser.tables
