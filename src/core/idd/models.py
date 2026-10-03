"""IDD 元数据数据模型。

依据 R-10（Energy+.idd）：每个对象定义含字段列表，每个字段含类型、单位、
默认值、选择项、引用关系等元数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class FieldDef:
    """字段定义。

    Attributes:
        name: 字段名。
        type: 字段类型（alpha/real/integer/choice/object-list/external-list/node）。
        units: 单位（SI）。
        ip_units: IP 单位。
        default: 默认值。
        required: 是否必填。
        key_choices: choice 类型的可选值列表。
        object_lists: object-list 类型的引用列表名。
        references: 该字段作为引用源的名（用于被其他对象引用）。
        minimum: 最小值（含）。
        minimum_greater: 最小值（不含）。
        maximum: 最大值（含）。
        maximum_less: 最大值（不含）。
        note: 字段说明。
        autosizable: 是否可自动 sizing。
        autocalculatable: 是否可自动计算。
        begin_extensible: 是否为可扩展字段集起点。
        deprecated: 是否已废弃。
        retaincase: 是否保留大小写。
    """

    name: str = ""
    type: str = "alpha"
    units: str = ""
    ip_units: str = ""
    default: str = ""
    required: bool = False
    key_choices: list[str] = field(default_factory=list)
    object_lists: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    minimum: float | None = None
    minimum_greater: float | None = None
    maximum: float | None = None
    maximum_less: float | None = None
    note: str = ""
    autosizable: bool = False
    autocalculatable: bool = False
    begin_extensible: bool = False
    deprecated: bool = False
    retaincase: bool = False


@dataclass(slots=True)
class ObjectDef:
    """对象定义。

    Attributes:
        name: 对象类型名。
        group: 所属组名。
        memo: 对象说明。
        min_fields: 最少字段数。
        unique_object: 是否唯一对象。
        fields: 字段定义列表。
        extensible_size: 可扩展字段集大小（0 表示不可扩展）。
    """

    name: str
    group: str = ""
    memo: str = ""
    min_fields: int = 0
    unique_object: bool = False
    fields: list[FieldDef] = field(default_factory=list)
    extensible_size: int = 0

    def field_count(self) -> int:
        """返回字段数。"""
        return len(self.fields)


@dataclass(slots=True)
class IDDDocument:
    """IDD 文档。

    Attributes:
        version: EnergyPlus 版本。
        objects: 对象定义列表。
        objects_by_name: 按类型名索引（小写）。
    """

    version: str = ""
    objects: list[ObjectDef] = field(default_factory=list)
    objects_by_name: dict[str, ObjectDef] = field(default_factory=dict)

    def add(self, obj: ObjectDef) -> None:
        """添加对象定义并更新索引。"""
        self.objects.append(obj)
        self.objects_by_name[obj.name.lower()] = obj

    def get(self, name: str) -> ObjectDef | None:
        """按类型名查询（大小写不敏感）。"""
        return self.objects_by_name.get(name.lower())

    def object_count(self) -> int:
        """返回对象定义总数。"""
        return len(self.objects)
