"""验证运行准备对实际路径的校验、归档与哈希记录。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.core.entities.run_options import RunOptions
from src.persistence.run_repository import RunRepository
from src.services.ep_runner import EPRunner
from src.services.run_manager import RunManager, RunRequest


def test_prepare_archives_effective_inputs(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "runs"
    model = tmp_path / "models" / "model.idf"
    first = model.parent / "dir a" / "data.csv"
    second = tmp_path / "dir b" / "data.csv"
    for file, content in [(first, "1"), (second, "2")]:
        file.parent.mkdir(parents=True)
        file.write_text(content)
    source = (
        "Version, 9.4;\n"
        "Schedule:File, A, , dir a/data.csv, 1, 0;\n"
        "Schedule:File, B, , ../dir b/data.csv, 1, 0;\n"
        "Schedule:File, C, , dir a/data.csv, 1, 0;\n"
    )
    model.write_text(source)
    weather = tmp_path / "actual weather.epw"
    idd = tmp_path / "custom dict.idd"
    weather.write_text("weather")
    idd.write_text("custom idd")
    exe = tmp_path / "energyplus"
    exe.touch()
    runner = EPRunner()
    process = Mock()
    monkeypatch.setattr("src.services.ep_runner.QProcess", Mock(return_value=process))
    monkeypatch.setattr("src.services.run_manager.read_engine_version", lambda _: "EnergyPlus 9.4")
    manager = RunManager(runner, root)
    result = manager.start(
        str(exe),
        RunRequest(
            str(model),
            weather_path=str(tmp_path / "unused weather.epw"),
            extra_args=f'--weather="{weather}" -i "{idd}" -p custom -s C',
        ),
    )
    assert result is not None
    archive = Path(result.run_dir)
    assert archive.parent == root
    assert Path(result.idf_path).read_text().count("dependencies/1.csv") == 2
    assert "dependencies/2.csv" in Path(result.idf_path).read_text()
    assert model.read_text() == source
    assert first.read_text() == "1" and second.read_text() == "2"
    assert Path(result.weather_path).read_text() == "weather"
    assert Path(result.idd_path).read_text() == "custom idd"
    (archive / "customOut.err").write_text("error log")
    # 模拟运行中引擎改写输入，归档仍记录启动前的哈希。
    Path(result.weather_path).write_text("changed")
    runner.finished.emit(result)

    manifest = json.loads((archive / "run.json").read_text())
    assert len(manifest["inputs"]) == 5
    assert manifest["command_args"] == [str(exe), *process.start.call_args.args[1]]
    assert manifest["working_directory"] == str(archive / "inputs")
    assert manifest["weather_sha256"] == hashlib.sha256(b"weather").hexdigest()
    assert manifest["idd_sha256"] == hashlib.sha256(b"custom idd").hexdigest()
    assert manifest["output_files"] == [{"name": "customOut.err", "size": 9}]
    assert manifest["engine_version"] == "EnergyPlus 9.4"
    assert RunRepository(root).get_run_by_id(result.run_id) is not None


@pytest.mark.parametrize(
    ("options", "extra_args", "model_text", "weather", "message"),
    [
        (None, "-w lost.epw", "Version, 9.4;", "", "天气文件"),
        (None, "", "Version, 9.4;", "lost.epw", "天气文件"),
        (None, "-i lost.idd", "Version, 9.4;", "", "IDD 文件"),
        (None, "--output-directory=elsewhere", "Version, 9.4;", "", "输出目录"),
        (RunOptions(output_directory="elsewhere"), "", "Version, 9.4;", "", "输出目录"),
        (RunOptions(extra_args=["-w", "lost.epw"]), "", "Version, 9.4;", "", "不支持"),
        (None, "-p ../outside", "Version, 9.4;", "", "输出文件前缀"),
        (None, "-w -a", "Version, 9.4;", "", "缺少有效值"),
        (None, "", "Schedule:File, A, , missing.csv, 1, 0;", "", "依赖文件"),
        (None, "", "Schedule:File, A, , , 1, 0;", "", "缺少依赖"),
        (None, "-m", "Version, 9.4;", "", "EPMacro"),
        (None, "", "PythonPlugin:Instance, A, No, B, C;", "", "PythonPlugin"),
    ],
)
def test_invalid_input_rejected_before_allocating_directory(
    tmp_path: Path,
    options: RunOptions | None,
    extra_args: str,
    model_text: str,
    weather: str,
    message: str,
) -> None:
    root = tmp_path / "runs"
    model = tmp_path / "model.idf"
    model.write_text(model_text)
    manager = RunManager(EPRunner(), root)
    errors: list[str] = []
    manager.error.connect(errors.append)
    request = RunRequest(str(model), weather, extra_args=extra_args, options=options)
    executable = tmp_path / "energyplus"
    executable.touch()
    (tmp_path / "Energy+.idd").touch()
    assert manager.start(str(executable), request) is None
    assert len(errors) == 1 and message in errors[0]
    assert not root.exists()



def test_readvars_control_file_is_reported_before_launch(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    executable = tmp_path / "energyplus"
    executable.touch()
    model = tmp_path / "model.idf"
    model.write_text("Version, 9.4;")
    model.with_suffix(".rvi").touch()
    manager = RunManager(EPRunner(), root)
    errors: list[str] = []
    manager.error.connect(errors.append)
    assert manager.start(str(executable), RunRequest(str(model), extra_args="-r")) is None
    assert errors and "ReadVarsESO 自定义控制文件" in errors[0]
    assert not root.exists()
