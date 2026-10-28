"""在线程池执行结果查询，以信号返回数据。"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Signal

logger = logging.getLogger(__name__)


class TaskSignals(QObject):
    """查询完成和失败通知；编号用于丢弃过期查询。"""

    finished = Signal(int, object)
    failed = Signal(int, str)


class BackgroundTask(QRunnable):
    """执行无界面操作的后台任务。"""

    def __init__(self, number: int, work: Callable[[], object]) -> None:
        super().__init__()
        self.signals = TaskSignals()
        self._number = number
        self._work = work

    def run(self) -> None:
        """执行任务并报告异常，禁止操作窗口。"""
        try:
            self.signals.finished.emit(self._number, self._work())
        except Exception as exc:
            logger.exception("后台查询失败")
            self.signals.failed.emit(self._number, str(exc))
