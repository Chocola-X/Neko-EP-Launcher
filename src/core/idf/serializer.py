"""以原文字符区间替换字段，保留注释、空行与缩进。依据 R-2。"""

from __future__ import annotations

from src.core.idf.models import IDFDocument, IDFObject


class IDFSerializer:
    """IDF 文档保真序列化器。"""

    def serialize(self, doc: IDFDocument) -> str:
        """保留原文，按逆序应用修改；新增对象追加到文末。"""
        if not doc.raw_text:
            parts = [*doc.header_comments, *(self.serialize_object(o) for o in doc.objects)]
            return "\n\n".join(parts)
        edits: list[tuple[int, int, str]] = []
        active = {(o.source_start, o.source_end) for o in doc.objects if o.source_start >= 0}
        for start, end in doc.source_spans:
            if (start, end) not in active:
                edits.append((start, end, ""))
        additions: list[str] = []
        for obj in doc.objects:
            if obj.source_start < 0:
                additions.append(self.serialize_object(obj))
            elif obj.type_name != obj.original_type or len(obj.fields) != len(obj.field_spans):
                edits.append((obj.source_start, obj.source_end, self._format_object(obj)))
            else:
                for i, (start, end) in enumerate(obj.field_spans):
                    if obj.fields[i] != obj.original_fields[i]:
                        edits.append((start, end, obj.fields[i]))
        text = doc.raw_text
        for start, end, value in sorted(edits, reverse=True):
            text = text[:start] + value + text[end:]
        if additions:
            text += "\n\n" if text and not text.endswith("\n\n") else ""
            text += "\n\n".join(additions) + "\n"
        return text

    def serialize_object(self, obj: IDFObject) -> str:
        """序列化独立对象；文档级保真请使用 serialize。"""
        return self._format_object(obj)

    @staticmethod
    def _format_object(obj: IDFObject) -> str:
        if not obj.fields:
            return f"{obj.type_name};"
        lines = [f"{obj.type_name},"]
        for idx, value in enumerate(obj.fields):
            name = obj.field_names[idx] if idx < len(obj.field_names) else ""
            delimiter = ";" if idx == len(obj.fields) - 1 else ","
            suffix = f"  !- {name}" if name else ""
            lines.append(f"    {value}{delimiter}{suffix}")
        return "\n".join(lines)
