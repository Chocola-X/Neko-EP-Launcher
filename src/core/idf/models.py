"""IDF 文档与对象数据模型。

依据 EnergyPlus Input Output Reference（R-2）：IDF 由若干对象组成，每个对象
形如 ``Object, field1, field2;``，字段后可附 ``!- FieldName`` 注释。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class IDFObject:
    """IDF 对象。

    Attributes:
        type_name: 对象类型名（如 ``Material``）。
        fields: 字段值列表。
        field_names: 字段名列表（来自 ``!-`` 注释，可能为空串）。
        comments: 字段附加注释列表（保留原文）。
        line_start: 对象起始行（1-based）。
        line_end: 对象结束行（1-based）。
        raw_lines: 对象原文行列表（用于保真序列化）。
    """

    type_name: str
    fields: list[str] = field(default_factory=list)
    field_names: list[str] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0
    raw_lines: list[str] = field(default_factory=list)

    source_start: int = -1
    source_end: int = -1
    field_spans: list[tuple[int, int]] = field(default_factory=list)
    original_type: str = ""
    original_fields: tuple[str, ...] = ()

    def get_field(self, index: int) -> str:
        """安全取字段值，越界返回空串。"""
        if 0 <= index < len(self.fields):
            return self.fields[index]
        return ""

    def set_field(self, index: int, value: str) -> None:
        """设置字段值，必要时扩展字段列表。"""
        while len(self.fields) <= index:
            self.fields.append("")
            self.field_names.append("")
            self.comments.append("")
        self.fields[index] = value

    def name(self) -> str:
        """返回对象名称字段（通常为第一个字段）。"""
        return self.get_field(0)


@dataclass(slots=True)
class IDFDocument:
    """IDF 文档。

    Attributes:
        objects: 对象列表。
        header_comments: 文件头部注释行。
        raw_text: 原始全文（保真用）。
        source_path: 来源文件路径。
    """

    objects: list[IDFObject] = field(default_factory=list)
    header_comments: list[str] = field(default_factory=list)
    raw_text: str = ""
    source_path: str = ""

    source_spans: list[tuple[int, int]] = field(default_factory=list)

    def get_objects_by_type(self, type_name: str) -> list[IDFObject]:
        """按类型名查询对象（大小写不敏感）。"""
        tn_lower = type_name.lower()
        return [o for o in self.objects if o.type_name.lower() == tn_lower]

    def get_object_types(self) -> list[str]:
        """返回去重后的对象类型名列表（保持出现顺序）。"""
        seen: list[str] = []
        for o in self.objects:
            if o.type_name not in seen:
                seen.append(o.type_name)
        return seen

    def object_count(self) -> int:
        """返回对象总数。"""
        return len(self.objects)


@dataclass(slots=True, frozen=True)
class ValidationIssue:
    """校验问题。

    Attributes:
        severity: 严重级别（error/warning）。
        message: 描述。
        object_type: 对象类型名。
        object_name: 对象名称字段。
        field_index: 字段索引（0-based，-1 表示对象级）。
        field_name: 字段名。
        object_index: 文档内对象索引（0-based），用于准确定位同名对象。
    """

    severity: str
    message: str
    object_type: str = ""
    object_name: str = ""
    field_index: int = -1
    field_name: str = ""
    object_index: int = -1
