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


def test_idf_automatic_keywords_follow_field_capability() -> None:
    """9.4 IDF 解析允许两种自动关键字互用，普通数值字段仍拒绝。"""
    for autosizable, autocalculatable in [
        (True, False),
        (False, True),
        (True, True),
        (False, False),
    ]:
        field = FieldDef(autosizable=autosizable, autocalculatable=autocalculatable)
        for value in ("Autosize", "AUTOCALCULATE", "aUtoSize"):
            assert field.accepts_automatic_value(value) == (autosizable or autocalculatable)
        for value in ("Automatic", "0", "NaN", ""):
            assert not field.accepts_automatic_value(value)
