"""可选本地验收：真实热致变色构造跨窗口复制，目标只改临时副本。"""

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from src.app import Application


@pytest.mark.e2e
def test_thermochromic_construction_transfer(qtbot, tmp_path, monkeypatch) -> None:
    installation = os.environ.get("ENERGYPLUS_HOME")
    if not installation:
        pytest.skip("设置 ENERGYPLUS_HOME 后验证官方热致变色示例")
    root = Path(installation)
    container = Application(tmp_path / "config.json", tmp_path / "runs")
    container.idd_service.load(root / "Energy+.idd")
    target_path = tmp_path / "target.idf"
    original_target = os.environ.get("NEKO_COPY_TARGET")
    if original_target:
        target_bytes = Path(original_target).read_bytes()
        target_path.write_bytes(target_bytes)
    else:
        target_path.write_text("Zone,Target Zone,0;")
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args))
    source = container.create_window(root / "ExampleFiles" / "ThermochromicWindow.idf")
    target = container.create_window(target_path)
    for win in (source, target):
        qtbot.addWidget(win, before_close_func=lambda w: setattr(w, "_modified", False))
    index = next(
        i
        for i, obj in enumerate(source._doc.objects)
        if obj.type_name == "Construction" and obj.name() == "TCwindow"
    )
    source._copy_objects((index,), True)
    copied = container.idf_service.parse_objects(QApplication.clipboard().text())
    assert len(copied) == 46
    before = len(target._doc.objects)
    target._paste_object_from_clipboard()
    assert not messages
    assert len(target._doc.objects) == before + 46
    target._save_file()
    reopened = container.idf_service.open(target_path)
    copied_names = {obj.name() for obj in copied}
    issues = container.idf_service.validate(reopened, container.idd_service.document)
    assert not [issue for issue in issues if issue.object_name in copied_names]
    assert target._doc.get_objects_by_type("WindowMaterial:GlazingGroup:Thermochromic")
    if original_target:
        assert Path(original_target).read_bytes() == target_bytes
    QApplication.clipboard().clear()
