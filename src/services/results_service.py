"""结果解析业务服务。

编排 ``core/results`` 各解析器，从运行目录加载结构化结果。
实例由 ``app.py`` 构造注入。依据 R-4。
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.core.results.err_parser import ErrParser
from src.core.results.models import ErrorRecord, ReportTable, RunStatus, VariableInfo
from src.core.results.rdd_parser import RDDParser
from src.core.results.sql_reader import SQLReader
from src.core.results.table_parser import TableParser

logger = logging.getLogger(__name__)


class ResultsService:
    """结果解析服务。"""

    def __init__(self) -> None:
        self._err_parser = ErrParser()
        self._rdd_parser = RDDParser()
        self._table_parser = TableParser()

    def load_errors(self, run_dir: str | Path) -> list[ErrorRecord]:
        """加载错误记录。

        Args:
            run_dir: 运行目录。

        Returns:
            错误记录列表，文件不存在时返回空列表。
        """
        err_path = Path(run_dir) / "eplusout.err"
        if not err_path.exists():
            return []
        try:
            return self._err_parser.parse_file(err_path)
        except Exception as e:
            logger.warning("解析 err 失败: %s", e)
            return []

    def load_run_status(self, run_dir: str | Path) -> RunStatus | None:
        """加载运行状态。

        Args:
            run_dir: 运行目录。

        Returns:
            运行状态，文件不存在时返回 None。
        """
        end_path = Path(run_dir) / "eplusout.end"
        if not end_path.exists():
            return None
        try:
            return self._err_parser.parse_end_file(end_path)
        except Exception as e:
            logger.warning("解析 end 失败: %s", e)
            return None

    def load_tables(self, run_dir: str | Path) -> list[ReportTable]:
        """加载表格汇总报告。

        Args:
            run_dir: 运行目录。

        Returns:
            表格列表，文件不存在时返回空列表。
        """
        xml_path = Path(run_dir) / "eplustbl.xml"
        if not xml_path.exists():
            return []
        try:
            return self._table_parser.parse_file(xml_path)
        except Exception as e:
            logger.warning("解析 eplustbl.xml 失败: %s", e)
            return []

    def load_rdd_variables(self, run_dir: str | Path) -> list[VariableInfo]:
        """加载可用输出变量。

        Args:
            run_dir: 运行目录。

        Returns:
            变量信息列表，文件不存在时返回空列表。
        """
        rdd_path = Path(run_dir) / "eplusout.rdd"
        if not rdd_path.exists():
            return []
        try:
            return self._rdd_parser.parse_file(rdd_path)
        except Exception as e:
            logger.warning("解析 rdd 失败: %s", e)
            return []

    def load_mdd_variables(self, run_dir: str | Path) -> list[VariableInfo]:
        """加载可用计量变量。

        Args:
            run_dir: 运行目录。

        Returns:
            变量信息列表，文件不存在时返回空列表。
        """
        mdd_path = Path(run_dir) / "eplusout.mdd"
        if not mdd_path.exists():
            return []
        try:
            return self._rdd_parser.parse_file(mdd_path)
        except Exception as e:
            logger.warning("解析 mdd 失败: %s", e)
            return []

    def open_sql_reader(self, run_dir: str | Path) -> SQLReader | None:
        """打开 SQL 读取器。

        Args:
            run_dir: 运行目录。

        Returns:
            已打开的 SQLReader，文件不存在时返回 None。
        """
        sql_path = Path(run_dir) / "eplusout.sql"
        if not sql_path.exists():
            return None
        try:
            reader = SQLReader(sql_path)
            reader.open()
            return reader
        except Exception as e:
            logger.warning("打开 sql 失败: %s", e)
            return None

    def list_output_files(self, run_dir: str | Path) -> list[tuple[str, int]]:
        """列出运行目录下的输出文件。

        Args:
            run_dir: 运行目录。

        Returns:
            (文件名, 大小字节) 列表，按文件名排序。
        """
        d = Path(run_dir)
        if not d.exists():
            return []
        result: list[tuple[str, int]] = []
        for entry in sorted(d.iterdir()):
            if entry.is_file() and entry.name != "run.json":
                result.append((entry.name, entry.stat().st_size))
        return result
