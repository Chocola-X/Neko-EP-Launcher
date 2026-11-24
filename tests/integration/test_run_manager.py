"""RunManager 纯逻辑集成测试（不启动 QProcess）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.ep_runner import EPRunner
from src.services.run_manager import RunManager


@pytest.fixture
def run_manager(tmp_path: Path) -> RunManager:
    runner = EPRunner()
    return RunManager(runner, tmp_path / "runs")


def test_make_unique_dir_new(run_manager: RunManager) -> None:
    d = run_manager._create_run_dir("run1")
    assert d.name == "run1"


def test_make_unique_dir_collision(run_manager: RunManager, tmp_path: Path) -> None:
    (tmp_path / "runs" / "run1").mkdir(parents=True)
    d = run_manager._create_run_dir("run1")
    assert d.name == "run1_1"
    d2 = run_manager._create_run_dir("run1")
    assert d2.name == "run1_2"


def test_list_output_files(run_manager: RunManager, tmp_path: Path) -> None:
    d = tmp_path / "run"
    d.mkdir()
    (d / "eplusout.err").write_text("err")
    (d / "eplusout.sql").write_text("sql")
    files = run_manager._list_output_files(d)
    names = [f["name"] for f in files]
    assert "eplusout.err" in names
    assert "eplusout.sql" in names


def test_start_invalid_idf(run_manager: RunManager) -> None:
    from src.services.run_manager import RunRequest

    result = run_manager.start("/usr/bin/true", RunRequest(idf_path="/nonexistent.idf"))
    assert result is None


@pytest.mark.parametrize("run_id", ["../outside", "/absolute", "sub/dir", "sub\\dir", ".", ".."])
def test_invalid_run_id_does_not_create_any_directory(tmp_path: Path, run_id: str) -> None:
    from src.services.run_manager import RunRequest

    root = tmp_path / "runs"
    manager = RunManager(EPRunner(), root)
    model = tmp_path / "model.idf"
    model.write_text("Version, 9.4;")
    errors: list[str] = []
    manager.error.connect(errors.append)
    assert manager.start("/usr/bin/true", RunRequest(str(model), run_id=run_id)) is None
    assert errors and "运行 ID" in errors[0]
    assert not root.exists()


def test_archive_directory_skips_existing_and_dangling_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "run").symlink_to(outside, target_is_directory=True)
    (root / "run_1").symlink_to(outside / "absent", target_is_directory=True)
    manager = RunManager(EPRunner(), root)
    assert manager._create_run_dir("run") == root / "run_2"
    assert manager._create_run_dir("run") == root / "run_3"
    assert not list(outside.iterdir())
