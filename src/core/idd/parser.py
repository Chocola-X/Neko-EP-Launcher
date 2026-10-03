"""IDD 文件解析器。

解析 ``Energy+.idd``（IDD 格式），构建 ``IDDDocument``。依据 R-10。

IDD 格式要点：
- ``\\group Name`` 标记组
- 对象类型名行形如 ``Material,`` 或最后一个字段 ``N7 ; \\field Name``
- ``\\field`` 开始字段定义，``\\type``/``\\units``/``\\default``/``\\key`` 等填充属性
- 对象以 ``;`` 结束（最后一个字段分隔符为分号）
"""

from __future__ import annotations

import contextlib
import logging
import re
from pathlib import Path

from src.core.exceptions import IDDFormatError
from src.core.idd.models import FieldDef, IDDDocument, ObjectDef

logger = logging.getLogger(__name__)

_VERSION_RE = re.compile(r"!IDD_Version\s+(\S+)")
_GROUP_RE = re.compile(r"\\group\s+(.+?)\s*$")


class IDDParser:
    """IDD 文件解析器。"""

    def parse_file(self, path: str | Path) -> IDDDocument:
        """解析 IDD 文件。

        Raises:
            IDDformatError: 文件无法读取或格式错误。
        """
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise IDDFormatError(0, f"无法读取 IDD 文件: {e}") from e
        return self.parse_text(text)

    def parse_text(self, text: str) -> IDDDocument:
        """解析 IDD 文本。

        Raises:
            IDDFormatError: 格式错误。
        """
        doc = IDDDocument()
        lines = text.splitlines()
        for line in lines:
            m = _VERSION_RE.match(line.strip())
            if m:
                doc.version = m.group(1)
                break

        current_group = ""
        current_obj: ObjectDef | None = None
        current_field: FieldDef | None = None
        in_object = False
        pending_close = False

        for line_no, raw in enumerate(lines, 1):
            line = raw.strip()
            if not line or line.startswith("!"):
                continue

            if line.startswith("\\"):
                self._handle_meta(
                    line,
                    line_no,
                    doc,
                    current_obj,
                    current_field,
                )
                m = _GROUP_RE.match(line)
                if m:
                    current_group = m.group(1)
                continue

            if pending_close and current_obj is not None:
                self._finalize_extensible(current_obj)
                doc.add(current_obj)
                current_obj = None
                current_field = None
                in_object = False
                pending_close = False

            if not in_object:
                type_name = self._extract_type_name(line, line_no)
                current_obj = ObjectDef(name=type_name, group=current_group)
                in_object = True
                if line.rstrip().endswith(";"):
                    pending_close = True
                continue

            is_last = self._is_last_field_line(line)
            current_field = FieldDef()
            assert current_obj is not None
            current_obj.fields.append(current_field)
            meta_part = self._extract_field_meta(line)
            if meta_part:
                self._handle_meta(meta_part, line_no, doc, current_obj, current_field)
            if is_last:
                pending_close = True

        if pending_close and current_obj is not None:
            self._finalize_extensible(current_obj)
            doc.add(current_obj)

        logger.info("IDD 解析完成: %d 个对象定义, 版本 %s", doc.object_count(), doc.version)
        return doc

    def _handle_meta(
        self,
        line: str,
        line_no: int,
        doc: IDDDocument,
        obj: ObjectDef | None,
        field: FieldDef | None,
    ) -> None:
        """处理 \\xxx 元数据行。"""
        parts = line.split(None, 1)
        tag = parts[0]
        value = parts[1].strip() if len(parts) > 1 else ""

        if tag == "\\group":
            return

        if obj is None:
            return

        if tag == "\\memo":
            obj.memo = value
            return
        if tag == "\\min-fields":
            with contextlib.suppress(ValueError):
                obj.min_fields = int(value)
            return
        if tag == "\\unique-object":
            obj.unique_object = True
            return

        if field is None:
            return

        if tag == "\\field":
            field.name = value
        elif tag == "\\type":
            field.type = value
        elif tag == "\\units":
            field.units = value
        elif tag == "\\ip-units":
            field.ip_units = value
        elif tag == "\\default":
            field.default = value
        elif tag == "\\required-field":
            field.required = True
        elif tag == "\\key":
            field.key_choices.append(value)
        elif tag == "\\object-list":
            field.object_lists.append(value)
        elif tag == "\\reference":
            field.references.append(value)
        elif tag == "\\note":
            field.note = value
        elif tag == "\\autosizable":
            field.autosizable = True
        elif tag == "\\autocalculatable":
            field.autocalculatable = True
        elif tag == "\\begin-extensible":
            field.begin_extensible = True
        elif tag == "\\deprecated":
            field.deprecated = True
        elif tag == "\\retaincase":
            field.retaincase = True
        elif tag == "\\minimum":
            field.minimum = self._parse_float(value)
        elif tag == "\\minimum>":
            field.minimum_greater = self._parse_float(value)
        elif tag == "\\maximum":
            field.maximum = self._parse_float(value)
        elif tag == "\\maximum<":
            field.maximum_less = self._parse_float(value)

    @staticmethod
    def _parse_float(value: str) -> float | None:
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _extract_type_name(line: str, line_no: int) -> str:
        """从对象首行提取类型名（去掉末尾 , 或 ;）。"""
        stripped = line.rstrip()
        for term in (",", ";"):
            if stripped.endswith(term):
                stripped = stripped[:-1]
        name = stripped.strip()
        if not name:
            raise IDDFormatError(line_no, "对象类型名为空")
        return name

    @staticmethod
    def _is_last_field_line(line: str) -> bool:
        """判断字段行是否为最后字段（分号在第一个 \\ 之前出现）。"""
        backslash_pos = line.find("\\")
        semi_pos = line.find(";")
        if semi_pos < 0:
            return False
        if backslash_pos < 0:
            return True
        return semi_pos < backslash_pos

    @staticmethod
    def _extract_field_meta(line: str) -> str:
        """提取字段行中的 \\xxx 元数据部分。"""
        backslash_pos = line.find("\\")
        if backslash_pos < 0:
            return ""
        return line[backslash_pos:]

    @staticmethod
    def _finalize_extensible(obj: ObjectDef) -> None:
        """对象结束时计算可扩展字段集大小。"""
        for idx, f in enumerate(obj.fields):
            if f.begin_extensible:
                obj.extensible_size = len(obj.fields) - idx
                return
