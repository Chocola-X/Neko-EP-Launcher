"""结果解析的共享数据模型。

依据 R-4 Output Details and Examples。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class ErrorRecord:
    """``eplusout.err`` 中的一条错误/警告记录。依据 R-4c。

    Attributes:
        severity: 严重级别（Warning/Severe/Fatal/Info）。
        message: 错误描述。
        line_in_idf: IDF 中对应行号（1-based），无法定位时为 None。
        object_type: 相关对象类型名，无则为空串。
        object_name: 相关对象名称，无则为空串。
    """

    severity: str
    message: str
    line_in_idf: int | None = None
    object_type: str = ""
    object_name: str = ""


@dataclass(slots=True, frozen=True)
class RunStatus:
    """运行状态（来自 ``eplusout.end``）。

    Attributes:
        success: 是否成功完成。
        warnings: 警告数。
        severes: 严重错误数。
        elapsed: 耗时描述。
        raw: 原始文本。
    """

    success: bool
    warnings: int
    severes: int
    elapsed: str
    raw: str


@dataclass(slots=True, frozen=True)
class VariableInfo:
    """可用输出变量信息（来自 ``eplusout.rdd``/``.mdd``）。依据 R-4e。

    Attributes:
        object_type: IDF 对象类型（Output:Variable 或 Output:Meter 等）。
        key_value: 键值（``*`` 表示全部）。
        variable_name: 变量名。
        reporting_frequency: 报告频率（hourly/daily/monthly 等）。
        units: 单位（来自 ``!-`` 注释）。
        is_meter: 是否为计量变量。
    """

    object_type: str
    key_value: str
    variable_name: str
    reporting_frequency: str
    units: str
    is_meter: bool = False


@dataclass(slots=True, frozen=True)
class ReportCell:
    """表格中的一个单元格。

    Attributes:
        value: 单元格值。
        units: 单位。
    """

    value: str
    units: str = ""


@dataclass(slots=True)
class ReportTable:
    """``eplustbl.xml`` 中的一张表格。依据 R-4d。

    Attributes:
        report_name: 报告名（如 AnnualBuildingUtilityPerformanceSummary）。
        report_for: 报告范围（如 Entire Facility）。
        table_name: 表格名。
        columns: 列标题列表。
        rows: 行标题列表。
        cells: 二维数据（rows x columns），值为字符串。
        notes: 表格附注。
    """

    report_name: str
    report_for: str
    table_name: str
    columns: list[str] = field(default_factory=list)
    rows: list[str] = field(default_factory=list)
    cells: list[list[str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class TimeSeriesPoint:
    """时序数据中的一个时间点。

    Attributes:
        year: 年。
        month: 月。
        day: 日。
        hour: 时。
        minute: 分。
        value: 变量值。
    """

    year: int
    month: int
    day: int
    hour: int
    minute: int
    value: float


@dataclass(slots=True, frozen=True)
class ReportVariable:
    """``eplusout.sql`` ReportDataDictionary 中的一条变量定义。依据 R-4b。

    Attributes:
        index: ReportDataDictionaryIndex。
        is_meter: 是否为计量。
        type: 类型（Avg/Sum 等）。
        index_group: 索引组。
        timestep_type: 时间步类型。
        key_value: 键值。
        name: 变量名。
        reporting_frequency: 报告频率。
        units: 单位。
    """

    index: int
    is_meter: bool
    type: str
    index_group: str
    timestep_type: str
    key_value: str
    name: str
    reporting_frequency: str
    units: str
