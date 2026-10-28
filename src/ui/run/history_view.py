"""运行历史浏览视图。

列出历史运行（时间/IDF/退出码/耗时），双击打开结果视图。
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.persistence.run_repository import RunRecord, RunRepository

logger = logging.getLogger(__name__)


class HistoryView(QWidget):
    """运行历史浏览视图。

    Signals:
        openRunRequested(str): 请求打开某次运行的结果，载荷为 run_dir。
    """

    openRunRequested = Signal(str)

    def __init__(
        self,
        repository: RunRepository,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        self._records: list[RunRecord] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        toolbar = QHBoxLayout()
        self._filter_idf = QLineEdit()
        self._filter_idf.setPlaceholderText("按 IDF 名称过滤...")
        self._filter_idf.textChanged.connect(self._refresh)
        self._check_success = QCheckBox("仅成功")
        self._check_success.toggled.connect(self._refresh)
        self._btn_refresh = QPushButton("刷新")
        self._btn_refresh.clicked.connect(self._refresh)
        toolbar.addWidget(QLabel("过滤:"))
        toolbar.addWidget(self._filter_idf, 1)
        toolbar.addWidget(self._check_success)
        toolbar.addWidget(self._btn_refresh)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["运行 ID", "开始时间", "IDF", "退出码", "耗时(s)"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 180)
        self._table.setColumnWidth(1, 180)
        self._table.setColumnWidth(3, 80)
        self._table.setColumnWidth(4, 80)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.doubleClicked.connect(self._on_double_clicked)
        layout.addWidget(self._table, 1)

    def refresh(self) -> None:
        """刷新历史列表。"""
        self._refresh()

    def _refresh(self) -> None:
        idf_filter = self._filter_idf.text().strip()
        success_only = self._check_success.isChecked()
        self._records = self._repository.filter_runs(
            success_only=success_only, idf_name=idf_filter
        )
        self._table.setRowCount(0)
        for rec in self._records:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(rec.run_id))
            self._table.setItem(row, 1, QTableWidgetItem(rec.start_time))
            self._table.setItem(row, 2, QTableWidgetItem(rec.idf_path))
            exit_item = QTableWidgetItem(str(rec.exit_code))
            if rec.success:
                exit_item.setForeground(Qt.GlobalColor.darkGreen)
            else:
                exit_item.setForeground(Qt.GlobalColor.red)
            self._table.setItem(row, 3, exit_item)
            self._table.setItem(row, 4, QTableWidgetItem(f"{rec.elapsed:.2f}"))

    def _on_double_clicked(self, index: object) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._records):
            return
        rec = self._records[row]
        self.openRunRequested.emit(rec.run_dir)
