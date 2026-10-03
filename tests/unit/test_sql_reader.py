"""``sql_reader`` 单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.exceptions import ResultParseError
from src.core.results.models import ReportVariable, TimeSeriesPoint
from src.core.results.sql_reader import SQLReader

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "test_run_001"
SQL_PATH = FIXTURES / "eplusout.sql"


@pytest.fixture
def reader() -> SQLReader:
    """创建并打开 SQLReader，测试后关闭。"""
    r = SQLReader(SQL_PATH)
    r.open()
    yield r
    r.close()


class TestSQLReader:
    """SQLReader 测试。"""

    def test_open_close(self) -> None:
        """测试打开和关闭。"""
        r = SQLReader(SQL_PATH)
        r.open()
        assert r.connection is not None
        r.close()

    def test_context_manager(self) -> None:
        """测试上下文管理器。"""
        with SQLReader(SQL_PATH) as r:
            assert r.connection is not None

    def test_list_variables(self, reader: SQLReader) -> None:
        """列出变量。"""
        variables = reader.list_variables()
        assert len(variables) > 0
        assert all(isinstance(v, ReportVariable) for v in variables)
        assert all(v.name != "" for v in variables)

    def test_find_variable(self, reader: SQLReader) -> None:
        """查找变量。"""
        variables = reader.list_variables()
        if variables:
            v = variables[0]
            found = reader.find_variable(v.name, v.key_value, v.reporting_frequency)
            assert found is not None
            assert found.name == v.name

    def test_find_variable_not_found(self, reader: SQLReader) -> None:
        """查找不存在的变量返回 None。"""
        result = reader.find_variable("NonexistentVariable12345")
        assert result is None

    def test_get_timeseries(self, reader: SQLReader) -> None:
        """取时序数据。"""
        variables = reader.list_variables()
        if variables:
            points = reader.get_timeseries(variables[0].index)
            assert isinstance(points, list)
            if points:
                assert isinstance(points[0], TimeSeriesPoint)

    def test_list_environment_periods(self, reader: SQLReader) -> None:
        """列出环境周期。"""
        periods = reader.list_environment_periods()
        assert isinstance(periods, list)
        if periods:
            assert isinstance(periods[0], tuple)
            assert len(periods[0]) == 2

    def test_file_not_found(self) -> None:
        """文件不存在应抛异常。"""
        with pytest.raises(ResultParseError):
            r = SQLReader("/nonexistent/test.sql")
            r.open()

    def test_connection_before_open(self) -> None:
        """未打开时访问 connection 抛异常。"""
        r = SQLReader(SQL_PATH)
        with pytest.raises(ResultParseError):
            _ = r.connection
