"""准备汇总图数据，终端用能分类依据 R-2 与 R-4d。"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from src.core.results.models import ReportTable

END_USE_ROWS: frozenset[str] = frozenset({
    "heating", "cooling", "interiorlighting", "exteriorlighting",
    "interiorequipment", "exteriorequipment", "fans", "pumps", "heatrejection",
    "humidification", "heatrecovery", "watersystems", "refrigeration", "generators",
})
END_USE_ENERGY_COLUMNS: frozenset[str] = frozenset({
    "electricity", "naturalgas", "gasoline", "diesel", "coal", "fueloilno1", "fueloilno2",
    "propane", "otherfuel", "otherfuel1", "otherfuel2", "districtcooling", "districtheating",
    "steam",
})
ENERGY_UNITS: frozenset[str] = frozenset({
    "J", "kJ", "MJ", "GJ", "Wh", "kWh", "MWh", "Btu", "kBtu", "MBtu", "therm", "ton-hrs",
})
VOLUME_UNITS: frozenset[str] = frozenset({"m3", "ft3", "gal", "L", "l"})


@dataclass(slots=True, frozen=True)
class SummaryChartData:
    """单量纲汇总图数据，标签和值一一对应。"""

    labels: tuple[str, ...]
    values: tuple[float, ...]
    axis_label: str


def _split_unit(text: str) -> tuple[str, str]:
    match = re.fullmatch(r"(.*?)\s*(?:\[([^\[\]]+)\]|\(([^()]+)\))\s*", text)
    if match:
        return match[1].strip(), (match[2] or match[3]).strip()
    return text.strip(), ""


def _name(text: str) -> str:
    return "".join(text.casefold().split())


def prepare_summary_chart(table: ReportTable, column: int, *, pie: bool) -> SummaryChartData:
    """提取所选列的可比较数据。

    Args:
        table: 原始汇总表。
        column: 数据列索引。
        pie: 是否要求互斥且可加的分项。

    Returns:
        图表标签及数值，单位来自列标题或单元格。

    Raises:
        ValueError: 缺少数据，或所选数据不适用于请求的图表。
    """
    if not 0 <= column < len(table.columns):
        raise ValueError("请选择数据列")
    if pie and (
        _name(table.report_name) != "annualbuildingutilityperformancesummary"
        or _name(table.table_name) != "enduses"
    ):
        raise ValueError("饼图仅支持年度建筑性能汇总中的终端用能表，请选择柱状图")

    title, header_unit = _split_unit(table.columns[column])
    resource = _name(title)
    if pie and resource != "water" and resource not in END_USE_ENERGY_COLUMNS:
        raise ValueError("所选列不是终端用能表中的已知资源")
    units: dict[str, str] = {}
    entries: list[tuple[str, float]] = []
    names: set[str] = set()
    total: float | None = None
    for index, label in enumerate(table.rows):
        row = table.cells[index] if index < len(table.cells) else []
        text, cell_unit = _split_unit(row[column] if column < len(row) else "")
        try:
            value = float(text)
        except ValueError:
            if pie:
                raise ValueError(f"终端用能分项缺少有效数值：{label}") from None
            continue
        if not math.isfinite(value):
            raise ValueError(f"数据包含非有限数值：{label}")
        if header_unit and cell_unit and header_unit.replace("³", "3") != cell_unit.replace(
            "³", "3"
        ):
            raise ValueError("数据列包含与列标题不一致的单位")
        unit = cell_unit or header_unit
        units.setdefault(unit.replace("³", "3"), unit)
        if pie:
            name = _name(label)
            if name == "hotwater":
                name = "watersystems"
            if name in names or (name != "totalenduses" and name not in END_USE_ROWS):
                raise ValueError(f"终端用能表包含重复项或未知层级：{label}")
            if value < 0:
                raise ValueError("饼图不支持负值，请选择柱状图")
            names.add(name)
            if name == "totalenduses":
                total = value
                continue
        entries.append((label, value))

    if len(units) > 1:
        raise ValueError("所选列混合了不同单位，无法绘制")
    unit_key, unit = next(iter(units.items()), ("", ""))
    if pie:
        allowed = VOLUME_UNITS if resource == "water" else ENERGY_UNITS
        if unit_key not in allowed:
            raise ValueError("饼图需要统一且可加的能量或体积单位")
        subtotal = sum(value for _, value in entries)
        if subtotal <= 0 or not math.isfinite(subtotal):
            raise ValueError("饼图总量必须为有限正数")
        # EnergyPlus 终端用能表通常显示两位小数，各行及总计独立舍入。
        if total is not None and abs(total - subtotal) > 0.005 * (len(entries) + 1) + 1e-9:
            raise ValueError("终端用能分项之和与总计不一致，无法绘制饼图")
        entries = [(label, value) for label, value in entries if value > 0]
    if not entries:
        raise ValueError("所选列没有可绘制的数值")
    return SummaryChartData(
        tuple(label for label, _ in entries),
        tuple(value for _, value in entries),
        f"{title} [{unit}]" if unit else title,
    )
