"""IDF 文件解析器。

逐字符扫描，正确处理单/双引号字符串、``$`` 宏变量、行尾 ``!-`` 字段名注释、
嵌套括号、``!`` 行注释、逗号/分号终止符。解析记录每个对象的行号范围用于错误
定位与跳转。依据 R-2。
"""

from __future__ import annotations

import re
from pathlib import Path

from src.core.exceptions import IDFParseError
from src.core.idf.models import IDFDocument, IDFObject

_FIELD_NAME_RE = re.compile(r"!\-\s*(.+?)\s*$")


class IDFParser:
    """IDF 文件解析器（纯逻辑，无 I/O 副作用除 parse_file 外）。"""

    def parse_file(self, path: str | Path) -> IDFDocument:
        """解析文件，返回 IDFDocument。

        Args:
            path: IDF 文件路径。

        Raises:
            IDFParseError: 文件无法读取或解析失败。
        """
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise IDFParseError(0, f"无法读取文件 {p}: {e}") from e
        return self.parse_text(text, str(p))

    def parse_text(self, text: str, source_path: str = "") -> IDFDocument:
        """解析文本，返回 IDFDocument。

        Args:
            text: IDF 文本内容。
            source_path: 来源路径（仅记录，不读取）。

        Raises:
            IDFParseError: 解析失败。
        """
        doc = IDFDocument(raw_text=text, source_path=source_path)
        lines = text.splitlines()
        n = len(lines)

        i = 0
        while i < n:
            s = lines[i].strip()
            if not s:
                i += 1
                continue
            if s.startswith("!"):
                if not doc.objects:
                    doc.header_comments.append(lines[i])
                i += 1
                continue
            break

        while i < n:
            s = lines[i].strip()
            if not s or s.startswith("!"):
                i += 1
                continue
            obj, i = self._parse_object(lines, i)
            if obj is not None:
                doc.objects.append(obj)
        return doc

    def _parse_object(self, lines: list[str], start_idx: int) -> tuple[IDFObject | None, int]:
        """从 start_idx 解析一个对象，返回 (对象, 下一行索引)。"""
        n = len(lines)
        type_name: str | None = None
        fields: list[str] = []
        field_names: list[str] = []
        comments: list[str] = []
        raw_lines: list[str] = []

        current_token: list[str] = []
        in_squote = False
        in_dquote = False
        depth = 0
        obj_finished = False
        i = start_idx

        while i < n and not obj_finished:
            line = lines[i]
            raw_lines.append(line)
            j = 0
            length = len(line)
            while j < length:
                ch = line[j]
                if in_squote:
                    current_token.append(ch)
                    if ch == "'":
                        in_squote = False
                    j += 1
                    continue
                if in_dquote:
                    current_token.append(ch)
                    if ch == '"':
                        in_dquote = False
                    j += 1
                    continue
                if ch == "'":
                    in_squote = True
                    current_token.append(ch)
                    j += 1
                    continue
                if ch == '"':
                    in_dquote = True
                    current_token.append(ch)
                    j += 1
                    continue
                if ch == "!":
                    cmt = line[j:]
                    m = _FIELD_NAME_RE.match(cmt)
                    if m and fields:
                        field_names[len(fields) - 1] = m.group(1).strip()
                    j = length
                    break
                if ch == "(":
                    depth += 1
                    current_token.append(ch)
                    j += 1
                    continue
                if ch == ")":
                    depth -= 1
                    current_token.append(ch)
                    j += 1
                    continue
                if ch == "," and depth == 0:
                    tok = "".join(current_token).strip()
                    if type_name is None:
                        type_name = tok
                    else:
                        fields.append(tok)
                        field_names.append("")
                        comments.append("")
                    current_token = []
                    j += 1
                    continue
                if ch == ";" and depth == 0:
                    tok = "".join(current_token).strip()
                    if type_name is None:
                        type_name = tok
                    else:
                        fields.append(tok)
                        field_names.append("")
                        comments.append("")
                    current_token = []
                    obj_finished = True
                    j += 1
                    continue
                current_token.append(ch)
                j += 1
            i += 1

        if type_name is None:
            return None, i

        while len(field_names) < len(fields):
            field_names.append("")
        while len(comments) < len(fields):
            comments.append("")

        obj = IDFObject(
            type_name=type_name,
            fields=fields,
            field_names=field_names,
            comments=comments,
            line_start=start_idx + 1,
            line_end=i,
            raw_lines=raw_lines,
        )
        return obj, i
