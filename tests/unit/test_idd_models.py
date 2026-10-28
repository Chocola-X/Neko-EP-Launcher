"""扩展字段组元数据映射测试。"""

from src.core.idd.models import FieldDef, ObjectDef


def test_extensible_field_mapping() -> None:
    fixed = FieldDef("Name")
    x = FieldDef("X", begin_extensible=True)
    y = FieldDef("Y")
    definition = ObjectDef("Vertices", fields=[fixed, x, y], extensible_size=2)
    assert definition.get_field(0) is fixed
    assert definition.get_field(3) is x
    assert definition.get_field(4) is y
    assert definition.get_field(-1) is None
    assert ObjectDef("Empty").get_field(0) is None
