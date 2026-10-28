"""结果解析业务服务。

编排 ``core/results`` 各解析器，从运行目录加载结构化结果。
实例由 ``app.py`` 构造注入。依据 R-4。
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Sequence
from pathlib import Path

from src.core.results.err_parser import ErrParser
from src.core.results.html_table_parser import HTMLTableParser
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
        err_path = self.find_output(run_dir, ".err", "eplusout.err")
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
        end_path = self.find_output(run_dir, ".end", "eplusout.end")
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
        xml_path = self.find_output(run_dir, ".xml", "eplustbl.xml")
        if not xml_path.exists():
            reader = self.open_sql_reader(run_dir)
            if reader is None:
                return self._load_html_tables(run_dir)
            try:
                groups: dict[tuple[str, str, str], ReportTable] = {}
                records = reader.get_tabular_summary()
                for record in records:
                    key = (record["report"], record["report_for"], record["table"])
                    table = groups.setdefault(key, ReportTable(*key))
                    if record["column"] not in table.columns:
                        table.columns.append(record["column"])
                    if record["row"] not in table.rows:
                        table.rows.append(record["row"])
                for table in groups.values():
                    table.cells = [["" for _ in table.columns] for _ in table.rows]
                for record in records:
                    table = groups[(record["report"], record["report_for"], record["table"])]
                    value = record["value"]
                    if record["units"]:
                        value += f" [{record['units']}]"
                    table.cells[table.rows.index(record["row"])][
                        table.columns.index(record["column"])
                    ] = value
                return list(groups.values()) or self._load_html_tables(run_dir)
            finally:
                reader.close()
        try:
            return self._table_parser.parse_file(xml_path)
        except Exception as e:
            logger.warning("解析 eplustbl.xml 失败: %s", e)
            return []

    def _load_html_tables(self, run_dir: str | Path) -> list[ReportTable]:
        """没有 XML/SQL 时读取原始 HTML，跳过启动器生成的增强报告。"""
        directory = Path(run_dir)
        candidates = sorted(
            {
                *directory.glob("*tbl.htm"),
                *directory.glob("*Table.htm"),
                *directory.glob("*-table.htm"),
                *directory.glob("*tbl.html"),
            }
        )
        if len(candidates) > 1:
            raise ValueError("目录包含多个 HTML 汇总报告，请选择单次运行目录")
        if not candidates:
            return []
        try:
            text = candidates[0].read_text(encoding="utf-8", errors="replace")
            return HTMLTableParser.parse_text(text)
        except OSError as exc:
            logger.warning("读取 HTML 汇总失败: %s", exc)
            return []

    def load_rdd_variables(self, run_dir: str | Path) -> list[VariableInfo]:
        """加载可用输出变量。

        Args:
            run_dir: 运行目录。

        Returns:
            变量信息列表，文件不存在时返回空列表。
        """
        rdd_path = self.find_output(run_dir, ".rdd", "eplusout.rdd")
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
        mdd_path = self.find_output(run_dir, ".mdd", "eplusout.mdd")
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
        sql_path = self.find_output(run_dir, ".sql", "eplusout.sql")
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

    @staticmethod
    def find_output(run_dir: str | Path, extension: str, preferred: str) -> Path:
        """查找标准或自定义前缀输出，歧义时要求选择单次运行目录。"""
        directory = Path(run_dir)
        standard = directory / preferred
        if standard.is_file():
            return standard
        matches = sorted(directory.glob("*" + extension))
        if extension == ".err":
            # 依据 R-4：SQLite 另有独立诊断文件，自定义前缀时也不能与模拟诊断混淆。
            matches = [path for path in matches if not path.name.casefold().endswith("sqlite.err")]
        if len(matches) > 1:
            raise ValueError(f"目录包含多个 {extension} 文件，请选择单次运行目录")
        return matches[0] if matches else standard

    @staticmethod
    def preview_file(path: Path) -> str:
        """读取小型文本结果，限制预览大小。"""
        if path.stat().st_size > 5 * 1024 * 1024:
            return "文件超过 5 MB，请用外部程序打开。"
        return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def export_csv(path: str, headers: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
        """导出 UTF-8 BOM CSV，便于电子表格打开。"""
        with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows(rows)

    def export_html_report(self, run_dir: str | Path, output_path: str | Path) -> str:
        """从真实输出生成离线 HTML；缺失数据在报告中说明，供后台任务调用。"""
        from src.core.results.html_report import build_report, line_chart

        tables = self.load_tables(run_dir)
        errors = self.load_errors(run_dir)
        state = self.load_run_status(run_dir)
        status = state.raw if state else "未找到运行结束标记；结果可能不完整"
        notes = ["汇总图使用所标注的单个数据列；原始汇总表保留全部列和单位。"]
        charts: list[str] = []
        reader = self.open_sql_reader(run_dir)
        if reader is not None:
            try:
                variables = reader.list_variables()
                selected = sorted(
                    variables,
                    key=lambda v: (
                        v.reporting_frequency.lower() != "hourly",
                        "temperature" not in v.name.lower(),
                        v.index,
                    ),
                )[:6]
                for period, environment in reader.list_environment_periods():
                    for variable in selected:
                        points = reader.get_timeseries(variable.index, period)
                        chart = line_chart(
                            f"{variable.name} [{variable.units}] / {variable.key_value} / {variable.reporting_frequency} / {environment}",
                            [(reader.timestamp(p).isoformat(sep=" "), p.value) for p in points],
                        )
                        if chart:
                            charts.append(chart)
                notes.append(
                    "时序按模拟环境周期分别绘图，排除暖机；自动选取最多 6 个变量，优先每小时温度。其余变量可在启动器分析。"
                )
            finally:
                reader.close()
        else:
            notes.append("没有 SQLite 数据。请使用“配置可视化输出”并添加时序变量后重新运行。")
        destination = Path(output_path)
        if destination.suffix.lower() not in (".html", ".htm"):
            raise ValueError("报告文件需使用 .html 或 .htm 后缀")
        if destination.name == "eplustbl.htm":
            raise ValueError("请使用新文件名，避免覆盖 EnergyPlus 原始报告")
        destination.write_text(
            build_report(Path(run_dir).name, status, errors, tables, charts, notes),
            encoding="utf-8",
        )
        return str(destination)
