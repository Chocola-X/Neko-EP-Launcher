"""多窗口支持与跨窗口参数/对象复制集成测试。"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QMessageBox

from src.app import Application
from src.services.ep_runner import EPRunner
from src.services.run_manager import RunRequest


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


def test_object_tree_duplicate_and_delete(qtbot, tmp_path: Path, monkeypatch) -> None:
    """删除更新源码、选择、属性和落盘，运行准备使用同一个已保存模型。"""
    container = Application(tmp_path / "config.json", tmp_path / "runs")
    file_path = tmp_path / "model.idf"
    original = "! 原有注释\nZone, BaseZone, 0;\n"
    file_path.write_text(original)
    window = container.create_window(file_path)
    qtbot.addWidget(window, before_close_func=lambda w: setattr(w, "_modified", False))

    window._duplicate_object(window._doc.objects[0])
    assert window._doc.objects[1].name() == "BaseZone_Copy"
    before_delete = window._editor.toPlainText()
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.No)
    window._delete_object(window._doc.objects[1])
    assert window._editor.toPlainText() == before_delete

    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    original_serialize = window._idf_service.serialize
    with monkeypatch.context() as failure:
        failure.setattr(QMessageBox, "warning", Mock())
        failure.setattr(window._idf_service, "serialize", Mock(return_value="incomplete"))
        window._delete_object(window._doc.objects[1])
        assert window._editor.toPlainText() == before_delete
        assert len(window._doc.objects) == 2
    assert window._idf_service.serialize == original_serialize

    window._delete_object(window._doc.objects[1])
    assert window._editor.toPlainText().strip() == original.strip()
    assert window._sync_baseline == window._editor.toPlainText()
    assert window._tree.get_selected_object() is window._doc.objects[0]
    window._save_file()
    assert "BaseZone_Copy" not in file_path.read_text()
    window._open_file(str(file_path))
    assert [obj.name() for obj in window._doc.objects] == ["BaseZone"]

    launch = Mock(return_value=None)
    monkeypatch.setattr(EPRunner, "run", launch)
    (tmp_path / "Energy+.idd").touch()
    executable = tmp_path / "energyplus"
    executable.touch()
    monkeypatch.setattr("src.services.run_manager.read_engine_version", lambda _: "EnergyPlus 9.4")
    window._run_manager.start(str(executable), RunRequest(str(file_path)))
    work_dir = launch.call_args.kwargs["working_directory"]
    assert (work_dir / file_path.name).read_text().strip() == original.strip()

    window._delete_object(window._doc.objects[0])
    assert not window._doc.objects
    assert window._selected_object_index is None
    assert window._tree.get_selected_object() is None
    assert window._field_panel._obj is None
    assert window._editor.toPlainText().strip() == "! 原有注释"


@pytest.mark.parametrize("outcome", ["success", "failure", "close", "exit"])
def test_runs_are_isolated_by_window(qtbot, tmp_path: Path, monkeypatch, outcome: str) -> None:
    """进程、日志、取消与结果和报告只进入归属窗口。"""
    processes = []
    runners = []

    def make_process(_parent):
        process = MagicMock()
        process.readAllStandardOutput.return_value.data.return_value = b"Window A\n"
        processes.append(process)
        return process

    def make_runner():
        runner = EPRunner()
        runners.append(runner)
        return runner

    factory = Mock(
        side_effect=make_process, ProcessChannelMode=QProcess.ProcessChannelMode,
        ExitStatus=QProcess.ExitStatus, ProcessError=QProcess.ProcessError,
    )
    monkeypatch.setattr("src.services.ep_runner.QProcess", factory)
    monkeypatch.setattr("src.app.EPRunner", make_runner)
    monkeypatch.setattr("src.services.run_manager.read_engine_version", lambda _: "EnergyPlus 9.4")
    monkeypatch.setattr(QMessageBox, "question", Mock(return_value=QMessageBox.Yes))
    info = Mock()
    warn = Mock()
    monkeypatch.setattr(QMessageBox, "information", info)
    monkeypatch.setattr(QMessageBox, "warning", warn)
    root = tmp_path / "ep"
    root.mkdir()
    (root / "energyplus").touch()
    (root / "Energy+.idd").touch()
    container = Application(tmp_path / "config.json", tmp_path / "runs")
    container.config_service.config.energyplus_path = str(root)
    models = [tmp_path / name for name in ("A.idf", "B.idf")]
    for model in models:
        model.write_text(f"Version, 9.4;\nZone, {model.stem};\n")
    a, b = (container.create_window(model) for model in models)
    qtbot.addWidget(a)
    qtbot.addWidget(b)
    load_a, load_b, report_a, report_b = (Mock() for _ in range(4))
    monkeypatch.setattr(a, "_load_results", load_a)
    monkeypatch.setattr(b, "_load_results", load_b)
    a._run_panel.reportRequested.connect(report_a)
    b._run_panel.reportRequested.connect(report_b)
    a._run_panel._enhanced_report.setChecked(True)
    assert a._run_panel.start_run()
    result = runners[0]._current_result
    assert result is not None
    callback = processes[0].readyReadStandardOutput.connect.call_args.args[0]
    callback()
    assert "Window A" in a._run_panel._log.toPlainText()
    assert b._run_panel._log.toPlainText() == ""
    assert a._run_panel._btn_cancel.isEnabled()
    assert not b._run_panel._btn_cancel.isEnabled()
    b._run_manager.cancel()
    processes[0].kill.assert_not_called()
    if outcome == "exit":
        assert b._run_panel.start_run()
        other_result = runners[1]._current_result
        assert other_result is not None and other_result.task_id != result.task_id
        a._act_quit.trigger()
        assert a in container.windows and b in container.windows
        processes[1].kill.assert_called_once()
        other_complete = processes[1].finished.connect.call_args.args[0]
        other_complete(-1, QProcess.ExitStatus.CrashExit)
        qtbot.waitUntil(lambda: b not in container.windows)
        other_archive = json.loads((Path(other_result.run_dir) / "run.json").read_text())
        assert other_archive["cancelled"]
    elif outcome == "close":
        assert b.close()
        processes[0].kill.assert_not_called()
        assert not a.close()
    if outcome in {"close", "exit"}:
        processes[0].kill.assert_called_once()
        assert a._run_manager.is_running
    complete = processes[0].finished.connect.call_args.args[0]
    complete(0 if outcome == "success" else 1, QProcess.ExitStatus.NormalExit)
    archive = json.loads((Path(result.run_dir) / "run.json").read_text())
    assert archive["task_id"] == result.task_id
    load_b.assert_not_called()
    report_b.assert_not_called()
    if outcome in {"close", "exit"}:
        qtbot.waitUntil(lambda: a not in container.windows)
        assert archive["cancelled"]
        load_a.assert_not_called()
        info.assert_not_called()
        warn.assert_not_called()
    elif outcome == "success":
        info.assert_called_once()
        load_a.assert_called_once_with(result.run_dir)
        report_a.assert_called_once_with(result.run_dir)
    else:
        warn.assert_called_once()
        load_a.assert_called_once_with(result.run_dir)
    if outcome != "success":
        report_a.assert_not_called()
