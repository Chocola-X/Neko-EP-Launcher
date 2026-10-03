"""``RunRepository`` 单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.persistence.run_repository import RunRecord, RunRepository


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    """创建含多个运行记录的临时目录。"""
    for run_id, success, elapsed in [
        ("20260101_120000", True, 1.5),
        ("20260102_130000", False, 2.0),
        ("20260103_140000", True, 0.5),
    ]:
        d = tmp_path / run_id
        d.mkdir()
        (d / "run.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "start_time": f"2026-01-0{run_id[-6]}T{run_id[-6:2]}:{run_id[-4:2]}:{run_id[-2:]}",
                    "end_time": "2026-01-01T12:00:01",
                    "elapsed": elapsed,
                    "exit_code": 0 if success else 1,
                    "success": success,
                    "command": "energyplus test.idf",
                    "idf_path": "test.idf",
                    "weather_path": "weather.epw",
                    "idf_sha256": "abc",
                    "weather_sha256": "def",
                    "output_files": [{"name": "eplusout.err", "size": 100}],
                }
            ),
            encoding="utf-8",
        )
    return tmp_path


class TestRunRepository:
    """RunRepository 测试。"""

    def test_list_runs(self, runs_dir: Path) -> None:
        repo = RunRepository(runs_dir)
        records = repo.list_runs()
        assert len(records) == 3
        assert all(isinstance(r, RunRecord) for r in records)

    def test_list_runs_empty(self, tmp_path: Path) -> None:
        repo = RunRepository(tmp_path / "nonexistent")
        assert repo.list_runs() == []

    def test_load_run(self, runs_dir: Path) -> None:
        repo = RunRepository(runs_dir)
        run_dir = runs_dir / "20260101_120000"
        record = repo.load_run(run_dir)
        assert record is not None
        assert record.run_id == "20260101_120000"
        assert record.success is True
        assert record.elapsed == 1.5

    def test_load_run_no_json(self, tmp_path: Path) -> None:
        repo = RunRepository(tmp_path)
        d = tmp_path / "no_json"
        d.mkdir()
        assert repo.load_run(d) is None

    def test_get_run_by_id(self, runs_dir: Path) -> None:
        repo = RunRepository(runs_dir)
        record = repo.get_run_by_id("20260101_120000")
        assert record is not None
        assert record.run_id == "20260101_120000"

    def test_get_run_by_id_not_found(self, runs_dir: Path) -> None:
        repo = RunRepository(runs_dir)
        assert repo.get_run_by_id("nonexistent") is None

    def test_filter_success_only(self, runs_dir: Path) -> None:
        repo = RunRepository(runs_dir)
        records = repo.filter_runs(success_only=True)
        assert len(records) == 2
        assert all(r.success for r in records)

    def test_filter_by_idf_name(self, runs_dir: Path) -> None:
        repo = RunRepository(runs_dir)
        records = repo.filter_runs(idf_name="test")
        assert len(records) == 3
        records = repo.filter_runs(idf_name="nonexistent")
        assert len(records) == 0

    def test_filter_combined(self, runs_dir: Path) -> None:
        repo = RunRepository(runs_dir)
        records = repo.filter_runs(success_only=True, idf_name="test")
        assert len(records) == 2
