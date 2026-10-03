"""``eplusout.sql`` 读取器。依据 R-4b。

使用标准库 ``sqlite3`` 读取 EnergyPlus 输出的 SQLite 数据库。禁止 SQLAlchemy。
关键表：
- ``ReportDataDictionary``：变量定义（KeyValue/Name/ReportingFrequency/Units 等）
- ``ReportData``：时序数据（TimeIndex/ReportDataDictionaryIndex/Value）
- ``Time``：时间信息（Year/Month/Day/Hour/Minute 等）
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from src.core.exceptions import ResultParseError
from src.core.results.models import ReportVariable, TimeSeriesPoint

logger = logging.getLogger(__name__)


class SQLReader:
    """``eplusout.sql`` 读取器。"""

    def __init__(self, path: str | Path) -> None:
        """初始化读取器。

        Args:
            path: ``eplusout.sql`` 路径。

        Raises:
            ResultParseError: 文件无法打开。
        """
        self._path = Path(path)
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> SQLReader:
        self.open()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    def open(self) -> None:
        """打开数据库连接。

        Raises:
            ResultParseError: 文件无法打开。
        """
        try:
            self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            raise ResultParseError(f"无法打开 sql 文件: {e}") from e

    def close(self) -> None:
        """关闭连接。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        """返回当前连接。"""
        if self._conn is None:
            raise ResultParseError("数据库未打开")
        return self._conn

    def list_variables(self) -> list[ReportVariable]:
        """列出所有可用变量（``ReportDataDictionary``）。"""
        cur = self.connection.execute(
            """
            SELECT ReportDataDictionaryIndex, IsMeter, Type, IndexGroup,
                   TimestepType, KeyValue, Name, ReportingFrequency, Units
            FROM ReportDataDictionary
            ORDER BY ReportDataDictionaryIndex
            """
        )
        return [
            ReportVariable(
                index=row[0],
                is_meter=bool(row[1]),
                type=row[2] or "",
                index_group=row[3] or "",
                timestep_type=row[4] or "",
                key_value=row[5] or "",
                name=row[6] or "",
                reporting_frequency=row[7] or "",
                units=row[8] or "",
            )
            for row in cur.fetchall()
        ]

    def find_variable(
        self,
        name: str,
        key_value: str = "",
        reporting_frequency: str = "",
    ) -> ReportVariable | None:
        """查找指定变量。

        Args:
            name: 变量名。
            key_value: 键值，空串表示不限制。
            reporting_frequency: 报告频率，空串表示不限制。
        """
        query = "SELECT ReportDataDictionaryIndex, IsMeter, Type, IndexGroup, TimestepType, KeyValue, Name, ReportingFrequency, Units FROM ReportDataDictionary WHERE Name = ?"
        params: list[str | int] = [name]
        if key_value:
            query += " AND KeyValue = ?"
            params.append(key_value)
        if reporting_frequency:
            query += " AND ReportingFrequency = ?"
            params.append(reporting_frequency)
        query += " LIMIT 1"
        row = self.connection.execute(query, params).fetchone()
        if row is None:
            return None
        return ReportVariable(
            index=row[0],
            is_meter=bool(row[1]),
            type=row[2] or "",
            index_group=row[3] or "",
            timestep_type=row[4] or "",
            key_value=row[5] or "",
            name=row[6] or "",
            reporting_frequency=row[7] or "",
            units=row[8] or "",
        )

    def get_timeseries(
        self,
        rdd_index: int,
        env_period_index: int | None = None,
    ) -> list[TimeSeriesPoint]:
        """取指定变量的时序数据。

        Args:
            rdd_index: ``ReportDataDictionaryIndex``。
            env_period_index: 环境周期索引，None 表示全部。
        """
        query = """
            SELECT t.Year, t.Month, t.Day, t.Hour, t.Minute, rd.Value
            FROM ReportData rd
            JOIN Time t ON rd.TimeIndex = t.TimeIndex
            WHERE rd.ReportDataDictionaryIndex = ?
        """
        params: list[str | int] = [rdd_index]
        if env_period_index is not None:
            query += " AND t.EnvironmentPeriodIndex = ?"
            params.append(env_period_index)
        query += " ORDER BY rd.TimeIndex"
        cur = self.connection.execute(query, params)
        return [
            TimeSeriesPoint(
                year=row[0] or 0,
                month=row[1] or 0,
                day=row[2] or 0,
                hour=row[3] or 0,
                minute=row[4] or 0,
                value=row[5],
            )
            for row in cur.fetchall()
        ]

    def list_environment_periods(self) -> list[tuple[int, str]]:
        """列出环境周期（如设计日、全年模拟）。"""
        cur = self.connection.execute(
            "SELECT EnvironmentPeriodIndex, EnvironmentName FROM EnvironmentPeriods ORDER BY EnvironmentPeriodIndex"
        )
        return [(row[0], row[1] or "") for row in cur.fetchall()]

    def get_tabular_summary(self) -> list[dict[str, str]]:
        """获取表格汇总数据（TabularData 表）。

        返回扁平的字典列表，每项含 report/table/row/column/value/units。
        """
        query = """
            SELECT
                (SELECT Value FROM Strings WHERE StringsIndex = r.ReportNameIndex) AS ReportName,
                (SELECT Value FROM Strings WHERE StringsIndex = r.ReportForStringIndex) AS ReportFor,
                (SELECT Value FROM Strings WHERE StringsIndex = r.TableNameIndex) AS TableName,
                (SELECT Value FROM Strings WHERE StringsIndex = r.RowNameIndex) AS RowName,
                (SELECT Value FROM Strings WHERE StringsIndex = r.ColumnNameIndex) AS ColumnName,
                (SELECT Value FROM Strings WHERE StringsIndex = r.UnitsIndex) AS Units,
                td.Value
            FROM TabularData td
            JOIN TabularData r ON td.TabularDataIndex = r.TabularDataIndex
            WHERE td.Value IS NOT NULL
            LIMIT 100
        """
        try:
            cur = self.connection.execute(query)
            return [
                {
                    "report": row[0] or "",
                    "report_for": row[1] or "",
                    "table": row[2] or "",
                    "row": row[3] or "",
                    "column": row[4] or "",
                    "units": row[5] or "",
                    "value": str(row[6]) if row[6] is not None else "",
                }
                for row in cur.fetchall()
            ]
        except sqlite3.Error:
            return []
