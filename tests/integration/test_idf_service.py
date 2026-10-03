"""IDF 服务集成测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.idf_service import IDFService

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_idf_service_open() -> None:
    idf = FIXTURES / "1ZoneUncontrolled.idf"
    if not idf.exists():
        pytest.skip("fixture 缺失")
    svc = IDFService()
    doc = svc.open(idf)
    assert doc.object_count() > 0
    assert doc.source_path == str(idf)


def test_idf_service_parse_serialize() -> None:
    svc = IDFService()
    doc = svc.parse("Material,\n    A,\n    0.1;\n")
    assert doc.object_count() == 1
    text = svc.serialize(doc)
    assert "Material" in text
    assert "A" in text


def test_idf_service_save(tmp_path: Path) -> None:
    svc = IDFService()
    out = tmp_path / "out.idf"
    svc.save_text("Material,\n    A;\n", out)
    assert out.read_text(encoding="utf-8") == "Material,\n    A;\n"
