"""多窗口支持与跨窗口参数/对象复制集成测试。"""

from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.app import Application


def test_application_creates_and_tracks_multiple_windows(qtbot, tmp_path: Path) -> None:
    """验证 Application 可创建并独立管理多个主窗口。"""
    container = Application(tmp_path / "config.json", tmp_path / "runs")

    win1 = container.create_window()
    win2 = container.create_window()

    qtbot.addWidget(win1, before_close_func=lambda w: setattr(w, "_modified", False))
    qtbot.addWidget(win2, before_close_func=lambda w: setattr(w, "_modified", False))

    assert len(container.windows) == 2
    assert win1 in container.windows
    assert win2 in container.windows
    assert win1 is not win2

    # 关闭其中一个窗口，另一个不受影响
    win1.close()
    assert win1 not in container.windows
    assert win2 in container.windows
    assert len(container.windows) == 1


def test_multiple_windows_open_different_idf_files(qtbot, tmp_path: Path) -> None:
    """验证两个窗口可独立加载不同的 IDF 文件，模型互不干扰。"""
    container = Application(tmp_path / "config.json", tmp_path / "runs")

    file1 = tmp_path / "model_a.idf"
    file1.write_text("Zone, OfficeZone, 0;\n")
    file2 = tmp_path / "model_b.idf"
    file2.write_text("Material, Insulation, Rough, 0.05, 0.04, 30, 1200;\n")

    win1 = container.create_window(file1)
    win2 = container.create_window(file2)

    qtbot.addWidget(win1, before_close_func=lambda w: setattr(w, "_modified", False))
    qtbot.addWidget(win2, before_close_func=lambda w: setattr(w, "_modified", False))

    assert win1._doc is not None
    assert win2._doc is not None
    assert len(win1._doc.objects) == 1
    assert win1._doc.objects[0].type_name == "Zone"
    assert win1._doc.objects[0].name() == "OfficeZone"

    assert len(win2._doc.objects) == 1
    assert win2._doc.objects[0].type_name == "Material"
    assert win2._doc.objects[0].name() == "Insulation"


def test_new_window_action_triggers_application_window_creation(qtbot, tmp_path: Path) -> None:
    """验证主窗口菜单新建窗口动作可成功触发新窗口生成。"""
    container = Application(tmp_path / "config.json", tmp_path / "runs")
    win1 = container.create_window()
    qtbot.addWidget(win1, before_close_func=lambda w: setattr(w, "_modified", False))

    assert len(container.windows) == 1
    # 触发新建窗口动作
    win1._act_new_window.trigger()
    assert len(container.windows) == 2

    win2 = container.windows[1]
    qtbot.addWidget(win2, before_close_func=lambda w: setattr(w, "_modified", False))
    assert win2 is not win1


def test_cross_window_object_copy_and_paste(qtbot, tmp_path: Path) -> None:
    """验证跨窗口复制对象（Window 1 复制 -> Window 2 粘贴）功能。"""
    container = Application(tmp_path / "config.json", tmp_path / "runs")

    file1 = tmp_path / "source.idf"
    file1.write_text("Material, ShadingFabric, Smooth, 0.002, 0.15, 900, 1500;\n")
    file2 = tmp_path / "target.idf"
    file2.write_text("Zone, LivingRoom, 0;\n")

    win1 = container.create_window(file1)
    win2 = container.create_window(file2)

    qtbot.addWidget(win1, before_close_func=lambda w: setattr(w, "_modified", False))
    qtbot.addWidget(win2, before_close_func=lambda w: setattr(w, "_modified", False))

    # 在 win1 选中 Material 对象并复制
    source_obj = win1._doc.objects[0]
    win1._copy_object(source_obj)

    # 验证剪贴板写入了标准 IDF 代码
    clipboard_text = QApplication.clipboard().text()
    assert "Material" in clipboard_text
    assert "ShadingFabric" in clipboard_text

    # 在 win2 执行粘贴
    win2._paste_object_from_clipboard()

    # 验证 win2 的模型增加了 Material 对象
    assert len(win2._doc.objects) == 2
    types = [obj.type_name for obj in win2._doc.objects]
    names = [obj.name() for obj in win2._doc.objects]
    assert "Zone" in types and "Material" in types
    assert "LivingRoom" in names and "ShadingFabric" in names

    # 验证 win2 的树和属性面板已自动同步更新
    assert win2._selected_object_index == 1
    assert win2._field_panel._type_label.text() == "Material"
    assert win2._field_panel._name_label.text() == "ShadingFabric"


def test_cross_window_parameter_copy_and_paste(qtbot, tmp_path: Path) -> None:
    """验证跨窗口复制参数覆盖（复制参数列表 -> 覆盖粘贴至另一个对象）。"""
    container = Application(tmp_path / "config.json", tmp_path / "runs")

    file1 = tmp_path / "donor.idf"
    file1.write_text("Zone, DonorZone, 45, 1, 2;\n")
    file2 = tmp_path / "recipient.idf"
    file2.write_text("Zone, RecipientZone, 0, 0, 0;\n")

    win1 = container.create_window(file1)
    win2 = container.create_window(file2)

    qtbot.addWidget(win1, before_close_func=lambda w: setattr(w, "_modified", False))
    qtbot.addWidget(win2, before_close_func=lambda w: setattr(w, "_modified", False))

    # 在 win1 点击“复制全部参数”
    win1._field_panel.set_object(win1._doc.objects[0])
    win1._field_panel._btn_copy_params.click()

    assert "DonorZone" in QApplication.clipboard().text()
    assert "45" in QApplication.clipboard().text()

    # 在 win2 选中对象并点击“粘贴覆盖参数”
    win2._field_panel.set_object(win2._doc.objects[0])
    win2._field_panel._btn_paste_params.click()

    # 验证 win2 的对象参数被覆盖更新为 win1 的参数
    updated_obj = win2._doc.objects[0]
    assert updated_obj.fields == ["DonorZone", "45", "1", "2"]


def test_object_tree_duplicate_and_delete(qtbot, tmp_path: Path) -> None:
    """验证对象树的副本创建与删除功能。"""
    container = Application(tmp_path / "config.json", tmp_path / "runs")
    file_path = tmp_path / "model.idf"
    file_path.write_text("Zone, BaseZone, 0;\n")

    window = container.create_window(file_path)
    qtbot.addWidget(window, before_close_func=lambda w: setattr(w, "_modified", False))

    assert len(window._doc.objects) == 1
    # 创建副本
    window._duplicate_object(window._doc.objects[0])
    assert len(window._doc.objects) == 2
    assert window._doc.objects[1].name() == "BaseZone_Copy"

    # 删除对象（直接调用 service 层删除或通过已验证确认的 _delete_object）
    window._idf_service.remove_object(window._doc, 1)
    assert len(window._doc.objects) == 1
    assert window._doc.objects[0].name() == "BaseZone"
