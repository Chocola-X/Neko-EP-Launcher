"""``eplusout.rdd``/``.mdd`` 解析器。依据 R-4e。

文件格式为 IDF 风格：
::

    ! Output:Variable Objects (applicable to this run)
    Output:Variable,*,Site Outdoor Air Drybulb Temperature,hourly; !- Zone Average [C]

每行是一个对象定义，``!-`` 注释含报告类型与单位。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from src.core.exceptions import ResultParseError
from src.core.results.models import VariableInfo

logger = logging.getLogger(__name__)

_UNIT_RE = re.compile(r"\[(.*?)\]")


class RDDParser:
    """``eplusout.rdd``/``.mdd`` 解析器。"""

    def parse_file(self, path: str | Path) -> list[VariableInfo]:
        """解析 rdd/mdd 文件为变量信息列表。

        Raises:
            ResultParseError: 文件无法读取。
        """
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise ResultParseError(f"无法读取 rdd/mdd 文件: {e}") from e
        is_meter = p.suffix.lower() == ".mdd"
        return self.parse_text(text, is_meter)

    def parse_text(self, text: str, is_meter: bool = False) -> list[VariableInfo]:
        """解析 rdd/mdd 文本。

        Args:
            text: 文本内容。
            is_meter: 是否为计量变量（mdd）。
        """
        variables: list[VariableInfo] = []

        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("!"):
                continue

            comment = ""
            semi = line.find(";")
            if semi >= 0:
                comment_part = line[semi + 1:]
                cmt = comment_part.find("!-")
                if cmt >= 0:
                    comment = comment_part[cmt + 3:].strip()
                line = line[:semi]

            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue

            obj_type = parts[0]
            if not obj_type.startswith("Output:"):
                continue

            key_value = parts[1] if len(parts) > 1 else ""
            var_name = parts[2] if len(parts) > 2 else ""
            freq = parts[3] if len(parts) > 3 else ""

            units = ""
            m = _UNIT_RE.search(comment)
            if m:
                units = m.group(1)

            variables.append(
                VariableInfo(
                    object_type=obj_type,
                    key_value=key_value,
                    variable_name=var_name,
                    reporting_frequency=freq,
                    units=units,
                    is_meter=is_meter,
                )
            )

        logger.info("rdd/mdd 解析完成: %d 个变量", len(variables))
        return variables
