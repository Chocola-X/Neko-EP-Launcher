"""``err_parser`` 单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.exceptions import ResultParseError
from src.core.results.err_parser import ErrParser

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "test_run_001"


class TestErrParser:
    """ErrParser 测试。"""

    def setup_method(self) -> None:
        self.parser = ErrParser()

    def test_parse_clean_run(self) -> None:
        """无错误的运行应返回空列表。"""
        err_path = FIXTURES / "eplusout.err"
        records = self.parser.parse_file(err_path)
        assert isinstance(records, list)
        assert len(records) == 0

    def test_parse_warning(self) -> None:
        """解析 Warning 记录。"""
        text = """   ************* Simulation Error Summary *************
   ** Warning ** Some warning message
   ** Severe ** Some severe message
   ************* EnergyPlus Completed Successfully-- 1 Warning; 1 Severe Errors
"""
        records = self.parser.parse_text(text)
        assert len(records) == 2
        assert records[0].severity == "Warning"
        assert records[0].message == "Some warning message"
        assert records[1].severity == "Severe"
        assert records[1].message == "Some severe message"

    def test_parse_with_object_ref(self) -> None:
        """解析带对象引用的错误。"""
        text = """   ** Warning ** Check field values
   **   ~~~   ** ...in object=Material, id=CONCRETE
"""
        records = self.parser.parse_text(text)
        assert len(records) == 1
        assert records[0].severity == "Warning"
        assert records[0].object_type == "Material"
        assert records[0].object_name == "CONCRETE"

    def test_parse_with_line_ref(self) -> None:
        """解析带行号引用的错误。"""
        text = """   ** Severe ** Bad value
   **   ~~~   ** in line=42
"""
        records = self.parser.parse_text(text)
        assert len(records) == 1
        assert records[0].line_in_idf == 42

    def test_parse_empty(self) -> None:
        """空文本返回空列表。"""
        records = self.parser.parse_text("")
        assert records == []

    def test_parse_end_success(self) -> None:
        """解析成功的 end 文件。"""
        text = "EnergyPlus Completed Successfully-- 0 Warning; 0 Severe Errors; Elapsed Time=00hr 00min  0.99sec"
        status = self.parser.parse_end_text(text)
        assert status.success is True
        assert status.warnings == 0
        assert status.severes == 0
        assert "0.99sec" in status.elapsed

    def test_parse_end_with_errors(self) -> None:
        """解析有错误的 end 文件。"""
        text = "EnergyPlus Completed Successfully-- 2 Warning; 1 Severe Errors; Elapsed Time=00hr 01min  5.00sec"
        status = self.parser.parse_end_text(text)
        assert status.success is True
        assert status.warnings == 2
        assert status.severes == 1

    def test_parse_end_file(self) -> None:
        """从文件解析 end。"""
        end_path = FIXTURES / "eplusout.end"
        status = self.parser.parse_end_file(end_path)
        assert status.success is True
        assert status.warnings == 0

    def test_parse_file_not_found(self) -> None:
        """文件不存在应抛异常。"""
        with pytest.raises(ResultParseError):
            self.parser.parse_file("/nonexistent/err.txt")
