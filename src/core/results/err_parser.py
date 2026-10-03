"""``eplusout.err`` 解析器。依据 R-4c。

错误文件格式：
- ``** Warning **`` / ``** Severe **`` / ``** Fatal **`` / ``** Info **`` 开始一条记录
- 后续行可含 ``in object=TYPE, id=NAME`` 定位对象
- ``~~~~~~~~~`` 行为续行补充信息
- ``*************`` 行为段落分隔（如 Simulation Error Summary）
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from src.core.exceptions import ResultParseError
from src.core.results.models import ErrorRecord, RunStatus

logger = logging.getLogger(__name__)

_SEVERITY_RE = re.compile(r"\*\*\s*(Warning|Severe|Fatal|Info)\s*\*\*\s*(.*)")
_OBJECT_RE = re.compile(r"in object=(\S+),\s*id=(\S+)")
_LINE_RE = re.compile(r"in line=(\d+)", re.IGNORECASE)
_END_RE = re.compile(
    r"EnergyPlus Completed Successfully--\s*(\d+)\s*Warning;\s*(\d+)\s*Severe Errors;?\s*(Elapsed Time=.*)?"
)
_END_FAIL_RE = re.compile(r"EnergyPlus(?:\s+Completed)?\s*(?:Successfully)?", re.IGNORECASE)


class ErrParser:
    """``eplusout.err`` 解析器。"""

    def parse_file(self, path: str | Path) -> list[ErrorRecord]:
        """解析 err 文件为错误记录列表。

        Raises:
            ResultParseError: 文件无法读取。
        """
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise ResultParseError(f"无法读取 err 文件: {e}") from e
        return self.parse_text(text)

    def parse_text(self, text: str) -> list[ErrorRecord]:
        """解析 err 文本。"""
        records: list[ErrorRecord] = []
        current_severity: str | None = None
        current_message: str = ""
        current_obj_type: str = ""
        current_obj_name: str = ""
        current_line: int | None = None

        for raw in text.splitlines():
            line = raw.strip()

            m = _SEVERITY_RE.search(line)
            if m:
                if current_severity is not None:
                    records.append(
                        ErrorRecord(
                            severity=current_severity,
                            message=current_message.strip(),
                            line_in_idf=current_line,
                            object_type=current_obj_type,
                            object_name=current_obj_name,
                        )
                    )
                current_severity = m.group(1)
                current_message = m.group(2)
                current_obj_type = ""
                current_obj_name = ""
                current_line = None
                continue

            if current_severity is not None:
                if line.startswith("**********"):
                    records.append(
                        ErrorRecord(
                            severity=current_severity,
                            message=current_message.strip(),
                            line_in_idf=current_line,
                            object_type=current_obj_type,
                            object_name=current_obj_name,
                        )
                    )
                    current_severity = None
                    continue

                obj_m = _OBJECT_RE.search(line)
                if obj_m:
                    current_obj_type = obj_m.group(1)
                    current_obj_name = obj_m.group(2).rstrip(",")

                line_m = _LINE_RE.search(line)
                if line_m:
                    current_line = int(line_m.group(1))

                if (
                    line
                    and not line.startswith("**")
                    and not line.startswith("~~")
                    and not obj_m
                    and not line_m
                ):
                    current_message += " " + line

        if current_severity is not None:
            records.append(
                ErrorRecord(
                    severity=current_severity,
                    message=current_message.strip(),
                    line_in_idf=current_line,
                    object_type=current_obj_type,
                    object_name=current_obj_name,
                )
            )

        logger.info("err 解析完成: %d 条记录", len(records))
        return records

    def parse_end_file(self, path: str | Path) -> RunStatus:
        """解析 ``eplusout.end`` 获取运行状态。

        Raises:
            ResultParseError: 文件无法读取。
        """
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8", errors="replace").strip()
        except OSError as e:
            raise ResultParseError(f"无法读取 end 文件: {e}") from e
        return self.parse_end_text(text)

    @staticmethod
    def parse_end_text(text: str) -> RunStatus:
        """解析 end 文本。"""
        m = _END_RE.search(text)
        if m:
            return RunStatus(
                success=True,
                warnings=int(m.group(1)),
                severes=int(m.group(2)),
                elapsed=m.group(3) or "",
                raw=text,
            )
        success = "Successfully" in text and "Error" not in text.split("Successfully")[-1]
        return RunStatus(
            success=success,
            warnings=-1,
            severes=-1,
            elapsed="",
            raw=text,
        )
