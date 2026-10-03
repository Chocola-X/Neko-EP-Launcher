"""EnergyPlus IDF 文件解析器。

IDF 文件格式：
    Object,
        field1,        !- Field Name 1
        field2;        !- Field Name 2

采用逐字符扫描方法，正确处理引号、括号、注释。
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class IDFObject:
    """IDF 对象。"""
    type_name: str
    fields: List[str] = field(default_factory=list)
    field_names: List[str] = field(default_factory=list)
    comments: List[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0
    raw_text: str = ""

    def get_field(self, index):
        if 0 <= index < len(self.fields):
            return self.fields[index]
        return ""

    def set_field(self, index, value):
        while len(self.fields) <= index:
            self.fields.append("")
            self.field_names.append("")
        self.fields[index] = value


@dataclass
class IDFDocument:
    """IDF 文档。"""
    objects: List[IDFObject] = field(default_factory=list)
    header_comments: List[str] = field(default_factory=list)
    raw_text: str = ""
    source_path: str = ""

    def get_objects_by_type(self, type_name):
        tn_lower = type_name.lower()
        return [o for o in self.objects if o.type_name.lower() == tn_lower]

    def get_object_types(self):
        seen = []
        for o in self.objects:
            if o.type_name not in seen:
                seen.append(o.type_name)
        return seen


class IDFParser:
    """IDF 文件解析器。"""

    FIELD_NAME_RE = re.compile(r"!\-\s*(.+?)\s*$")

    def parse_file(self, path) -> IDFDocument:
        path = Path(path)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return self.parse_text(text, str(path))

    def parse_text(self, text, source_path="") -> IDFDocument:
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
            if obj:
                doc.objects.append(obj)
        return doc

    def _parse_object(self, lines, start_idx):
        n = len(lines)
        type_name = None
        fields = []
        field_names = []
        comments = []
        raw_lines = []

        current_token = []
        in_squote = False
        in_dquote = False
        depth = 0
        obj_finished = False
        i = start_idx

        while i < n and not obj_finished:
            line = lines[i]
            raw_lines.append(line)
            j = 0
            L = len(line)
            while j < L:
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
                    m = self.FIELD_NAME_RE.match(cmt)
                    if m and fields:
                        field_names[len(fields) - 1] = m.group(1).strip()
                    j = L
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
                    break
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
            raw_text="\n".join(raw_lines),
        )
        return obj, i

    def serialize(self, doc: IDFDocument) -> str:
        """将文档序列化为 IDF 文本。"""
        lines = []
        for c in doc.header_comments:
            lines.append(c)
        if doc.header_comments:
            lines.append("")
        for obj in doc.objects:
            lines.append(self._serialize_object(obj))
            lines.append("")
        return "\n".join(lines)

    def _serialize_object(self, obj: IDFObject) -> str:
        lines = [f"{obj.type_name},"]
        n_fields = len(obj.fields)
        if n_fields == 0:
            lines[-1] = f"{obj.type_name};"
            return "\n".join(lines)
        for idx, val in enumerate(obj.fields):
            fname = obj.field_names[idx] if idx < len(obj.field_names) else ""
            terminator = ";" if idx == n_fields - 1 else ","
            if fname:
                lines.append(f"    {val:<24}{terminator}  !- {fname}")
            else:
                lines.append(f"    {val}{terminator}")
        return "\n".join(lines)


parser = IDFParser()
