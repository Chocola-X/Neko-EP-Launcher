"""IDF 词法解析，记录字段字符区间以支持全文保真编辑。依据 R-2。"""

from __future__ import annotations

from pathlib import Path

from src.core.exceptions import IDFParseError
from src.core.idf.models import IDFDocument, IDFObject


class IDFParser:
    """支持引号、注释、宏变量、括号以及同一行多个对象的解析器。"""

    def parse_file(self, path: str | Path) -> IDFDocument:
        """读取 IDF；读取或语法错误时抛出 IDFParseError。"""
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise IDFParseError(0, f"无法读取文件 {p}: {exc}") from exc
        return self.parse_text(text, str(p))

    def parse_text(self, text: str, source_path: str = "") -> IDFDocument:
        """解析全文并记录 1-based 行号；语法不完整时抛出 IDFParseError。"""
        doc = IDFDocument(raw_text=text, source_path=source_path)
        obj: IDFObject | None = None
        token: list[str] = []
        token_start = -1
        token_end = 0
        quote = ""
        depth = 0
        line = 1
        start_line = 1
        delimiter_line = -1
        last_field = -1
        last_obj: IDFObject | None = None
        i = 0
        while i < len(text):
            ch = text[i]
            if not quote and ch == "!":
                end = text.find("\n", i)
                end = len(text) if end < 0 else end
                comment = text[i:end]
                if comment.startswith("!-") and delimiter_line == line and last_obj is not None:
                    if last_field >= 0:
                        last_obj.field_names[last_field] = comment[2:].strip()
                        last_obj.comments[last_field] = comment
                elif obj is None and not doc.objects:
                    doc.header_comments.append(comment)
                i = end
                continue
            if quote:
                token.append(ch)
                token_end = i + 1
                if ch == quote:
                    quote = ""
            elif ch in "\"'":
                if token_start < 0:
                    token_start = i
                    start_line = line
                quote = ch
                token.append(ch)
                token_end = i + 1
            elif ch in ",;" and depth == 0:
                value = "".join(token).strip()
                if obj is None:
                    if not value:
                        raise IDFParseError(line, "对象类型名为空")
                    obj = IDFObject(
                        type_name=value,
                        original_type=value,
                        line_start=start_line,
                        source_start=token_start,
                    )
                else:
                    obj.fields.append(value)
                    obj.field_names.append("")
                    obj.comments.append("")
                    obj.field_spans.append(
                        (
                            token_start if token_start >= 0 else i,
                            token_end if token_start >= 0 else i,
                        )
                    )
                last_obj = obj
                last_field = len(obj.fields) - 1
                delimiter_line = line
                token = []
                token_start = -1
                if ch == ";":
                    obj.source_end = i + 1
                    obj.line_end = line
                    obj.raw_lines = text[obj.source_start : obj.source_end].splitlines()
                    obj.original_fields = tuple(obj.fields)
                    doc.objects.append(obj)
                    doc.source_spans.append((obj.source_start, obj.source_end))
                    obj = None
            else:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth < 0:
                        raise IDFParseError(line, "右括号没有匹配的左括号")
                if not ch.isspace():
                    if token_start < 0:
                        token_start = i
                        start_line = line
                    token_end = i + 1
                token.append(ch)
            if ch == "\n":
                line += 1
            i += 1
        if quote:
            raise IDFParseError(line, "字符串引号未闭合")
        if depth:
            raise IDFParseError(line, "括号未闭合")
        if obj is not None or "".join(token).strip():
            raise IDFParseError(line, "对象缺少结尾分号", "".join(token).strip()[:80])
        return doc
