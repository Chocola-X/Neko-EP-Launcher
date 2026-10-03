"""IDF 序列化器（保真）。

策略：优先基于对象原文行（``raw_lines``）重新生成，保留缩进、字段对齐、
``!-`` 注释与空行；仅替换字段值本身。当原文缺失或字段数与原文不匹配（增删
字段）时，回退到格式化输出。保证往返一致性：``parse(serialize(parse(t)))``
与 ``parse(t)`` 对象集合等价。依据 R-2。
"""

from __future__ import annotations

from src.core.idf.models import IDFDocument, IDFObject


class IDFSerializer:
    """IDF 文档序列化器。"""

    def serialize(self, doc: IDFDocument) -> str:
        """将文档序列化为 IDF 文本。

        Args:
            doc: IDF 文档。

        Returns:
            IDF 文本。
        """
        lines: list[str] = list(doc.header_comments)
        if doc.header_comments:
            lines.append("")
        for obj in doc.objects:
            lines.extend(self.serialize_object(obj).splitlines())
            lines.append("")
        if lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines)

    def serialize_object(self, obj: IDFObject) -> str:
        """序列化单个对象，优先保真，回退格式化。"""
        if obj.raw_lines:
            preserved = self._preserve_object(obj)
            if preserved is not None:
                return preserved
        return self._format_object(obj)

    def _preserve_object(self, obj: IDFObject) -> str | None:
        """基于原文行保真序列化，返回 None 表示无法保真需回退。"""
        spans = self._locate_field_spans(obj.raw_lines)
        if spans is None:
            return None
        if len(spans) != len(obj.fields):
            return None
        out_lines = list(obj.raw_lines)
        for (line_idx, start, end), new_val in zip(spans, obj.fields, strict=True):
            if line_idx >= len(out_lines):
                return None
            line = out_lines[line_idx]
            out_lines[line_idx] = line[:start] + new_val + line[end:]
        return "\n".join(out_lines)

    def _locate_field_spans(self, raw_lines: list[str]) -> list[tuple[int, int, int]] | None:
        """定位各字段值在原文行中的 (行索引, 起始列, 结束列)。

        返回 None 表示扫描未找到完整对象（原文不完整）。
        """
        spans: list[tuple[int, int, int]] = []
        type_name: str | None = None
        current_token_start: tuple[int, int] | None = None
        in_squote = False
        in_dquote = False
        depth = 0
        obj_finished = False

        for line_idx, line in enumerate(raw_lines):
            if obj_finished:
                break
            j = 0
            length = len(line)
            while j < length:
                ch = line[j]
                if in_squote:
                    if ch == "'":
                        in_squote = False
                    j += 1
                    continue
                if in_dquote:
                    if ch == '"':
                        in_dquote = False
                    j += 1
                    continue
                if ch == "'":
                    in_squote = True
                    j += 1
                    continue
                if ch == '"':
                    in_dquote = True
                    j += 1
                    continue
                if ch == "!":
                    j = length
                    break
                if ch == "(":
                    depth += 1
                    j += 1
                    continue
                if ch == ")":
                    depth -= 1
                    j += 1
                    continue
                if ch in (",", ";") and depth == 0:
                    if current_token_start is None:
                        return None
                    s_line, s_col = current_token_start
                    tok_start = s_col
                    tok_end = j
                    while tok_start < tok_end and line[tok_start] in " \t":
                        tok_start += 1
                    while tok_end > tok_start and line[tok_end - 1] in " \t":
                        tok_end -= 1
                    if type_name is None:
                        type_name = line[tok_start:tok_end]
                    else:
                        spans.append((s_line, tok_start, tok_end))
                    current_token_start = None
                    if ch == ";":
                        obj_finished = True
                        j += 1
                        break
                    j += 1
                    continue
                if current_token_start is None and ch not in " \t":
                    current_token_start = (line_idx, j)
                j += 1
            if not obj_finished and current_token_start is not None:
                pass
        if not obj_finished:
            return None
        return spans

    def _format_object(self, obj: IDFObject) -> str:
        """格式化输出（增删字段后回退用），保持可读对齐。"""
        if not obj.fields:
            return f"{obj.type_name};"
        lines = [f"{obj.type_name},"]
        n_fields = len(obj.fields)
        for idx, val in enumerate(obj.fields):
            fname = obj.field_names[idx] if idx < len(obj.field_names) else ""
            terminator = ";" if idx == n_fields - 1 else ","
            if fname:
                lines.append(f"    {val:<24}{terminator}  !- {fname}")
            else:
                lines.append(f"    {val}{terminator}")
        return "\n".join(lines)
