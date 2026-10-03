"""``ResultsService`` 集成测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.results_service import ResultsService

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "test_run_001"


@pytest.fixture
def service() -> ResultsService:
    return ResultsService()


class TestResultsService:
    """ResultsService 测试。"""

    def test_load_errors(self, service: ResultsService) -> None:
        errors = service.load_errors(FIXTURES)
        assert isinstance(errors, list)

    def test_load_errors_no_file(self, service: ResultsService) -> None:
        errors = service.load_errors("/nonexistent/dir")
        assert errors == []

    def test_load_run_status(self, service: ResultsService) -> None:
        status = service.load_run_status(FIXTURES)
        assert status is not None
        assert status.success is True

    def test_load_run_status_no_file(self, service: ResultsService) -> None:
        status = service.load_run_status("/nonexistent/dir")
        assert status is None

    def test_load_tables(self, service: ResultsService) -> None:
        tables = service.load_tables(FIXTURES)
        assert len(tables) > 0

    def test_load_tables_no_file(self, service: ResultsService) -> None:
        tables = service.load_tables("/nonexistent/dir")
        assert tables == []

    def test_load_rdd_variables(self, service: ResultsService) -> None:
        variables = service.load_rdd_variables(FIXTURES)
        assert len(variables) > 0

    def test_load_mdd_variables(self, service: ResultsService) -> None:
        variables = service.load_mdd_variables(FIXTURES)
        assert len(variables) > 0

    def test_open_sql_reader(self, service: ResultsService) -> None:
        reader = service.open_sql_reader(FIXTURES)
        assert reader is not None
        variables = reader.list_variables()
        assert len(variables) > 0
        reader.close()

    def test_open_sql_reader_no_file(self, service: ResultsService) -> None:
        reader = service.open_sql_reader("/nonexistent/dir")
        assert reader is None

    def test_list_output_files(self, service: ResultsService) -> None:
        files = service.list_output_files(FIXTURES)
        assert len(files) > 0
        assert all(isinstance(f, tuple) and len(f) == 2 for f in files)
        names = [f[0] for f in files]
        assert "eplusout.err" in names
