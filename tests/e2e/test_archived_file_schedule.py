"""以真实 EnergyPlus 9.4 验收外部文件归档与重跑。"""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from src.services.ep_runner import EPRunner
from src.services.run_manager import RunManager, RunRequest


@pytest.mark.e2e
@pytest.mark.parametrize("extra_args", ["-D", "-D -x -r"])
def test_archive_with_file_schedule(qtbot, tmp_path: Path, extra_args: str) -> None:
    installation = os.environ.get("ENERGYPLUS_HOME")
    if not installation:
        pytest.skip("设置 ENERGYPLUS_HOME 后运行真实模拟")
    root = Path(installation)
    source = tmp_path / "source"
    schedule = source / "schedules" / "occupancy hours.csv"
    schedule.parent.mkdir(parents=True)
    schedule.write_text("1\n" * 8760)
    idf = source / "test model.idf"
    example = root / "ExampleFiles" / "1ZoneUncontrolled_DDChanges.idf"
    idf.write_text(
        example.read_text()
        + "\nSchedule:File, ArchiveSchedule, , schedules/occupancy hours.csv, 1, 0, 8760, Comma;"
        + "\nExterior:Lights, ArchiveLights, ArchiveSchedule, 200, ScheduleNameOnly;\n"
    )
    original = idf.read_bytes()
    manager = RunManager(EPRunner(), tmp_path / "runs")
    with qtbot.waitSignal(manager.runFinished, timeout=120000) as completed:
        assert manager.start(
            str(root / "energyplus"),
            RunRequest(str(idf), extra_args=extra_args, analysis_outputs=True),
        )
    result = completed.args[0]
    run_dir = Path(result.run_dir)
    assert result.success, (run_dir / "eplusout.err").read_text()
    assert idf.read_bytes() == original
    manifest = json.loads((run_dir / "run.json").read_text())
    assert "9.4.0" in manifest["engine_version"]
    assert manifest["command_args"] == list(result.command_args)
    for item in manifest["inputs"]:
        assert hashlib.sha256((run_dir / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    assert {item["kind"] for item in manifest["inputs"]} == {"idf", "idd", "dependency"}
    source.rename(tmp_path / "moved")
    replay = tmp_path / "replay" / "inputs"
    shutil.copytree(result.working_directory, replay)
    process = subprocess.run(result.command_args, cwd=replay, capture_output=True, timeout=120)
    assert process.returncode == 0, (replay.parent / "eplusout.err").read_text()
    assert (replay.parent / "eplusout.sql").is_file()
