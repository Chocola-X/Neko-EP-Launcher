"""使用模拟 QProcess 验证运行参数、完成归档与失败路径，不启动模拟器。"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QProcess

from src.core.entities.run_options import RunOptions
from src.services.ep_runner import EPRunner


@pytest.mark.parametrize("code", [0, 1])
def test_process_lifecycle(monkeypatch, tmp_path: Path, code: int) -> None:
    process = MagicMock()
    process.waitForStarted.return_value = True
    factory = MagicMock(return_value=process)
    monkeypatch.setattr("src.services.ep_runner.QProcess", factory)
    runner = EPRunner()
    exe = tmp_path / "energyplus"
    exe.touch()
    (tmp_path / "input.idf").write_text("Version, 9.4;")
    (tmp_path / "eplusout.err").write_text("message")
    assert not runner.is_running
    result = runner.run(
        str(exe), tmp_path, "input.idf", "weather.epw", run_options=RunOptions(readvars=True)
    )
    assert result is not None and runner.is_running
    assert "--readvars" in process.start.call_args.args[1]
    assert "weather.epw" in process.start.call_args.args[1]
    assert runner.run(str(exe), tmp_path, "input.idf") is None
    runner.cancel()
    process.kill.assert_called_once()
    process.readAllStandardOutput.return_value.data.return_value = b"Progress\n"
    runner._read_output()
    runner._on_finished(code, QProcess.NormalExit)
    assert result.success == (code == 0)
    assert "eplusout.err" in result.output_files
    assert "input.idf" not in result.output_files
    assert result.end_time and result.elapsed >= 0
    process.deleteLater.assert_called_once()
    assert not runner.is_running


def test_failed_start(monkeypatch, tmp_path: Path) -> None:
    process = MagicMock()
    process.waitForStarted.return_value = False
    monkeypatch.setattr("src.services.ep_runner.QProcess", MagicMock(return_value=process))
    exe = tmp_path / "energyplus"
    exe.touch()
    runner = EPRunner()
    assert runner.run(str(exe), tmp_path, "input.idf", "weather.epw", "-D") is None
    assert runner.state == EPRunner.STATE_ERROR
    assert runner.run("/absent", tmp_path, "input.idf") is None
    runner._on_error(QProcess.FailedToStart)
    assert runner.state == EPRunner.STATE_ERROR
