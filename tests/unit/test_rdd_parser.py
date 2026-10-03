"""``rdd_parser`` 单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.exceptions import ResultParseError
from src.core.results.rdd_parser import RDDParser

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "test_run_001"


class TestRDDParser:
    """RDDParser 测试。"""

    def setup_method(self) -> None:
        self.parser = RDDParser()

    def test_parse_rdd_file(self) -> None:
        """解析真实 rdd 文件。"""
        rdd_path = FIXTURES / "eplusout.rdd"
        variables = self.parser.parse_file(rdd_path)
        assert len(variables) > 0
        assert all(not v.is_meter for v in variables)
        first = variables[0]
        assert first.object_type == "Output:Variable"
        assert first.variable_name != ""

    def test_parse_mdd_file(self) -> None:
        """解析真实 mdd 文件。"""
        mdd_path = FIXTURES / "eplusout.mdd"
        variables = self.parser.parse_file(mdd_path)
        assert len(variables) > 0
        assert all(v.is_meter for v in variables)
        assert any("Output:Meter" in v.object_type for v in variables)

    def test_parse_text_basic(self) -> None:
        """解析基本文本。"""
        text = """! Output:Variable Objects (applicable to this run)
Output:Variable,*,Site Outdoor Air Drybulb Temperature,hourly; !- Zone Average [C]
Output:Variable,*,Site Wind Speed,daily; !- Zone Average [m/s]
"""
        variables = self.parser.parse_text(text)
        assert len(variables) == 2
        assert variables[0].key_value == "*"
        assert variables[0].variable_name == "Site Outdoor Air Drybulb Temperature"
        assert variables[0].reporting_frequency == "hourly"
        assert variables[0].units == "C"
        assert variables[1].units == "m/s"

    def test_parse_empty(self) -> None:
        """空文本返回空列表。"""
        variables = self.parser.parse_text("")
        assert variables == []

    def test_parse_only_comments(self) -> None:
        """只有注释行返回空列表。"""
        text = "! comment line\n! another comment"
        variables = self.parser.parse_text(text)
        assert variables == []

    def test_parse_meter_flag(self) -> None:
        """is_meter 标志正确设置。"""
        text = "Output:Meter,Electricity:Facility,hourly; !- [J]"
        variables = self.parser.parse_text(text, is_meter=True)
        assert len(variables) == 1
        assert variables[0].is_meter is True
        assert variables[0].units == "J"

    def test_parse_file_not_found(self) -> None:
        """文件不存在应抛异常。"""
        with pytest.raises(ResultParseError):
            self.parser.parse_file("/nonexistent/rdd.txt")
