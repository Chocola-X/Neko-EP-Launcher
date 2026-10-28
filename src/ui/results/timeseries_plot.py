"""可按周期与日期筛选的时序分析视图。依据 R-4b。"""

from __future__ import annotations

from datetime import datetime

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from matplotlib.figure import Figure
from PySide6.QtCore import QDate, Qt, QThreadPool
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.results.models import ReportVariable
from src.core.results.sql_reader import SQLReader
from src.services.background_task import BackgroundTask
from src.services.results_service import ResultsService


class TimeseriesPlotView(QWidget):
    """变量搜索、多选、真实时间轴、单位分图、数据预览及导出。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reader: SQLReader | None = None
        self._request = 0
        self._jobs: dict[int, BackgroundTask] = {}
        self._rows: list[list[str]] = []
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索变量、区域、单位或报告频率")
        self._search.textChanged.connect(self._filter)
        self._period = QComboBox()
        self._period.currentIndexChanged.connect(self._refresh_plot)
        self._start = QDateEdit(QDate(2000, 1, 1))
        self._end = QDateEdit(QDate(2100, 12, 31))
        for widget in (self._start, self._end):
            widget.setCalendarPopup(True)
            widget.setDisplayFormat("yyyy-MM-dd")
            widget.dateChanged.connect(self._refresh_plot)
        for widget in (
            self._search,
            self._period,
            QLabel("起"),
            self._start,
            QLabel("止"),
            self._end,
        ):
            toolbar.addWidget(widget)
        layout.addLayout(toolbar)
        buttons = QHBoxLayout()
        for label, callback in [
            ("绘图 / 刷新", self._refresh_plot),
            ("导出 PNG", self._export_png),
            ("导出 CSV", self._export_csv),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        self._info_label = QLabel("打开结果目录以加载 SQL 数据")
        buttons.addWidget(self._info_label, 1)
        layout.addLayout(buttons)
        splitter = QSplitter(Qt.Horizontal)
        self._var_list = QListWidget()
        self._var_list.setSelectionMode(QListWidget.ExtendedSelection)
        self._var_list.itemSelectionChanged.connect(self._refresh_plot)
        splitter.addWidget(self._var_list)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self._figure = Figure(figsize=(8, 4))
        self._canvas = FigureCanvasQTAgg(self._figure)
        right_layout.addWidget(NavigationToolbar2QT(self._canvas, self))
        right_layout.addWidget(self._canvas, 3)
        self._data_table = QTableWidget(0, 3)
        self._data_table.setHorizontalHeaderLabels(["时间", "变量（单位）", "值"])
        self._data_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        right_layout.addWidget(self._data_table, 1)
        splitter.addWidget(right)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter, 1)

    def set_reader(self, reader: SQLReader | None) -> None:
        """接管读取器；切换目录时关闭上次连接并清除旧图。"""
        self.clear()
        self._reader = reader
        if reader is None:
            self._info_label.setText("无 SQL：请在模型中配置可视化输出，添加输出变量后重新运行。")
            return
        try:
            self._period.blockSignals(True)
            for index, name in reader.list_environment_periods():
                self._period.addItem(name, index)
            self._period.blockSignals(False)
            for var in reader.list_variables():
                label = f"{var.name} [{var.units}] / {var.key_value} / {var.reporting_frequency}"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, var)
                self._var_list.addItem(item)
            self._filter(self._search.text())
            self._info_label.setText(f"{self._var_list.count()} 个变量；Ctrl / Shift 多选")
        except Exception as exc:
            self._period.blockSignals(False)
            self._info_label.setText(f"SQL 加载失败: {exc}")

    def _filter(self, text: str) -> None:
        for i in range(self._var_list.count()):
            item = self._var_list.item(i)
            item.setHidden(text.casefold() not in item.text().casefold())

    def _refresh_plot(self) -> None:
        self._request += 1
        self._rows = []
        self._data_table.setRowCount(0)
        self._figure.clear()
        self._canvas.draw_idle()
        if self._reader is None:
            return
        selected = [
            item.data(Qt.UserRole) for item in self._var_list.selectedItems() if not item.isHidden()
        ]
        if not selected:
            return
        if self._start.date() > self._end.date():
            self._info_label.setText("开始日期必须早于结束日期")
            return
        path = self._reader.path
        period = self._period.currentData()
        first, last = self._start.date().toPython(), self._end.date().toPython()

        def query() -> object:
            data = []
            with SQLReader(path) as reader:
                for var in selected:
                    values = [
                        (reader.timestamp(p), p.value)
                        for p in reader.get_timeseries(var.index, period)
                    ]
                    data.append((var, [(t, v) for t, v in values if first <= t.date() <= last]))
            return data

        job = BackgroundTask(self._request, query)
        job.signals.finished.connect(self._show_series)
        job.signals.failed.connect(self._query_failed)
        self._jobs[self._request] = job
        self._info_label.setText("正在读取数据…")
        QThreadPool.globalInstance().start(job)

    def _query_failed(self, number: int, message: str) -> None:
        self._jobs.pop(number, None)
        if number == self._request:
            self._info_label.setText(f"查询失败: {message}")

    def _show_series(
        self, number: int, data: list[tuple[ReportVariable, list[tuple[datetime, float]]]]
    ) -> None:
        self._jobs.pop(number, None)
        if number != self._request:
            return
        self._figure.clear()
        units = list(dict.fromkeys(var.units for var, points in data if points))
        for i, unit in enumerate(units):
            ax = self._figure.add_subplot(len(units), 1, i + 1)
            for var, points in data:
                if var.units != unit or not points:
                    continue
                label = f"{var.name} ({var.key_value}, {var.reporting_frequency})"
                stride = max(1, len(points) // 5000)
                # 图形限制点数，CSV 仍保留完整数据。
                visible = points[::stride]
                ax.plot(
                    [t for t, _ in visible], [v for _, v in visible], label=label, linewidth=0.8
                )
                self._rows.extend(
                    [[t.isoformat(sep=" "), f"{label} [{unit}]", str(v)] for t, v in points]
                )
            locator = AutoDateLocator()
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))
            ax.set_ylabel(unit or "Value")
            ax.grid(alpha=0.25)
            ax.legend(fontsize=7)
        self._figure.tight_layout()
        self._canvas.draw_idle()
        preview = self._rows[:1000]
        self._data_table.setRowCount(len(preview))
        for i, row in enumerate(preview):
            for j, value in enumerate(row):
                self._data_table.setItem(i, j, QTableWidgetItem(value))
        self._info_label.setText(
            f"{len(self._rows)} 条数据；预览前 1000 条"
            if self._rows
            else "当前周期与日期范围内没有数据"
        )

    def _export_csv(self) -> None:
        if not self._rows:
            self._info_label.setText("请先选择变量并等待查询完成")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出时序数据", "", "CSV (*.csv)")
        if path:
            try:
                ResultsService.export_csv(path, ["时间", "变量（单位）", "值"], self._rows)
            except Exception as exc:
                QMessageBox.warning(self, "导出失败", str(exc))

    def _export_png(self) -> None:
        if not self._figure.axes:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出图表", "", "PNG (*.png)")
        if path:
            try:
                self._figure.savefig(path, dpi=150, bbox_inches="tight")
            except Exception as exc:
                QMessageBox.warning(self, "导出失败", str(exc))

    def clear(self) -> None:
        """关闭数据库、使在途查询失效并清空图表。"""
        self._request += 1
        if self._reader is not None:
            self._reader.close()
        self._reader = None
        self._var_list.clear()
        self._period.clear()
        self._rows = []
        self._data_table.setRowCount(0)
        self._figure.clear()
        self._canvas.draw_idle()
