"""结果视图 UI 烟测。"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")

from src.services.results_service import ResultsService
from src.ui.results.results_view import ResultsView

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "test_run_001"


@pytest.fixture
def service() -> ResultsService:
    return ResultsService()


class TestResultsView:
    """ResultsView 烟测。"""

    def test_construct(self, qtbot) -> None:
        svc = ResultsService()
        view = ResultsView(svc)
        qtbot.addWidget(view)
        assert view._tabs.count() == 6

    def test_load_from_run_dir(self, qtbot, service: ResultsService) -> None:
        view = ResultsView(service)
        qtbot.addWidget(view)
        view.load_from_run_dir(FIXTURES)
        assert view._run_dir != ""

    def test_clear(self, qtbot, service: ResultsService) -> None:
        view = ResultsView(service)
        qtbot.addWidget(view)
        view.load_from_run_dir(FIXTURES)
        view.clear()
