"""验证汇总图的数据语义及单位。"""

from pathlib import Path

import pytest

from src.core.results.models import ReportTable
from src.core.results.summary_chart import prepare_summary_chart
from src.core.results.table_parser import TableParser

FIXTURE = Path(__file__).parents[1] / "fixtures" / "test_run_001" / "eplustbl.xml"


def _end_uses(
    values: list[str], rows: list[str] | None = None, title: str = "Electricity [GJ]"
) -> ReportTable:
    return ReportTable(
        "Annual Building Utility Performance Summary",
        "Entire Facility",
        "End Uses",
        [title],
        rows or ["Heating", "Cooling", "Total End Uses"],
        [[value] for value in values],
    )


def test_real_end_uses_electricity_percentage() -> None:
    table = next(t for t in TableParser().parse_file(FIXTURE) if t.table_name == "EndUses")
    chart = prepare_summary_chart(table, table.columns.index("Electricity"), pie=True)
    assert chart.labels == ("ExteriorLighting",)
    assert chart.values == (82.42,)
    assert chart.axis_label == "Electricity [GJ]"


@pytest.mark.parametrize(
    ("table", "error"),
    [
        (_end_uses(["0", "0", "0"]), "有限正数"),
        (_end_uses(["-1", "4", "3"]), "负值"),
        (_end_uses(["1", "4", "9"]), "之和"),
        (_end_uses(["1", "", "1"]), "缺少有效"),
        (_end_uses(["nan", "1", "1"]), "非有限"),
        (_end_uses(["1", "1", "2"], title="Electricity [GJ/m2]"), "可加"),
        (_end_uses(["1", "2", "3"], ["Heating", "Heating:General", "Total End Uses"]), "层级"),
        (_end_uses(["1", "2", "3"], ["Heating", "Heating", "Total End Uses"]), "重复"),
        (_end_uses(["1", "2 [kWh]", "3"]), "不一致"),
        (ReportTable("Unknown", "", "End Uses", ["Power [W]"]), "仅支持"),
        (ReportTable("AnnualBuildingUtilityPerformanceSummary", "", "EndUsesBySubcategory"), "列"),
    ],
)
def test_reject_invalid_pie(table: ReportTable, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        prepare_summary_chart(table, 0, pie=True)


def test_cumulative_water_and_rounding() -> None:
    chart = prepare_summary_chart(_end_uses(["1", "1", "2.01"], title="Water [m3]"), 0, pie=True)
    assert chart.axis_label == "Water [m3]"
    assert chart.values == (1, 1)


def test_bar_units_and_mixed_values() -> None:
    table = _end_uses(["1 [GJ]", "2 [GJ]", "3 [GJ]"], title="Electricity")
    chart = prepare_summary_chart(table, 0, pie=False)
    assert chart.axis_label == "Electricity [GJ]"
    assert chart.labels[-1] == "Total End Uses"
    table.cells[0][0] = "50 [kWh]"
    with pytest.raises(ValueError, match="混合"):
        prepare_summary_chart(table, 0, pie=False)
