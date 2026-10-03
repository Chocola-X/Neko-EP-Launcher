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
    d = run_manager._make_unique_dir("run1")
    assert d.name == "run1"


def test_make_unique_dir_collision(run_manager: RunManager, tmp_path: Path) -> None:
    (tmp_path / "runs" / "run1").mkdir(parents=True)
    d = run_manager._make_unique_dir("run1")
    assert d.name == "run1_1"
    d.mkdir()
    d2 = run_manager._make_unique_dir("run1")
    assert d2.name == "run1_2"


def test_file_sha256(run_manager: RunManager, tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("hello", encoding="utf-8")
    h = run_manager._file_sha256(str(p))
    assert len(h) == 64
    assert run_manager._file_sha256(str(tmp_path / "nope")) == ""


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
