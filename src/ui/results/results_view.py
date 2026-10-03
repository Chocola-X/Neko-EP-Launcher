"""结果视图：多标签结构化呈现运行结果。

标签包括：错误、汇总报告、时序数据、原始文件。
通过 ``ResultsService`` 加载数据，禁止直接读写文件系统。
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.results.models import ErrorRecord, ReportTable, VariableInfo
from src.services.results_service import ResultsService

logger = logging.getLogger(__name__)

_LARGE_FILE_THRESHOLD = 5 * 1024 * 1024


class ErrorView(QWidget):
    """错误/警告视图。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["级别", "对象类型", "对象名", "描述"])
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 80)
        self._table.setColumnWidth(1, 150)
        self._table.setColumnWidth(2, 150)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self._table)

        self._detail = QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setMaximumHeight(100)
        layout.addWidget(self._detail)

    def set_errors(self, errors: list[ErrorRecord]) -> None:
        """设置错误记录。"""
        self._table.setRowCount(0)
        for err in errors:
            row = self._table.rowCount()
            self._table.insertRow(row)
            sev_item = QTableWidgetItem(err.severity)
            if err.severity == "Severe":
                sev_item.setForeground(QColor("#E06C75"))
            elif err.severity == "Warning":
                sev_item.setForeground(QColor("#E5C07B"))
            elif err.severity == "Fatal":
                sev_item.setForeground(QColor("#FF6B6B"))
            self._table.setItem(row, 0, sev_item)
            self._table.setItem(row, 1, QTableWidgetItem(err.object_type))
            self._table.setItem(row, 2, QTableWidgetItem(err.object_name))
            self._table.setItem(row, 3, QTableWidgetItem(err.message))

    def clear(self) -> None:
        self._table.setRowCount(0)
        self._detail.clear()


class SummaryView(QWidget):
    """汇总报告视图。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        self._report_list = QListWidget()
        self._report_list.currentItemChanged.connect(self._on_report_selected)
        splitter.addWidget(self._report_list)

        self._table_widget = QTableWidget()
        self._table_widget.setAlternatingRowColors(True)
        splitter.addWidget(self._table_widget)
        splitter.setSizes([250, 750])
        layout.addWidget(splitter, 1)

    def set_tables(self, tables: list[ReportTable]) -> None:
        """设置表格数据。"""
        self._report_list.clear()
        self._tables = tables
        for t in tables:
            label = f"{t.table_name} ({t.report_for})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, t)
            self._report_list.addItem(item)
        if tables:
            self._report_list.setCurrentRow(0)

    def _on_report_selected(self, current: QListWidgetItem, _: QListWidgetItem) -> None:
        if current is None:
            return
        table: ReportTable = current.data(Qt.UserRole)
        self._table_widget.setRowCount(0)
        self._table_widget.setColumnCount(0)
        if not table.columns:
            return
        self._table_widget.setColumnCount(len(table.columns))
        self._table_widget.setHorizontalHeaderLabels(table.columns)
        for row_idx, row_name in enumerate(table.rows):
            self._table_widget.insertRow(row_idx)
            self._table_widget.setItem(row_idx, 0, QTableWidgetItem(row_name))
            for col_idx, val in enumerate(table.cells[row_idx]):
                self._table_widget.setItem(row_idx, col_idx, QTableWidgetItem(val))
        self._table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def clear(self) -> None:
        self._report_list.clear()
        self._table_widget.setRowCount(0)
        self._table_widget.setColumnCount(0)


class TimeseriesView(QWidget):
    """时序数据视图（Phase 3 将增加绘图）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        info_label = QLabel("从下方列表选择变量查看时序数据（Phase 3 将增加绘图功能）")
        layout.addWidget(info_label)

        splitter = QSplitter(Qt.Horizontal)

        self._var_list = QListWidget()
        self._var_list.currentItemChanged.connect(self._on_var_selected)
        splitter.addWidget(self._var_list)

        self._data_table = QTableWidget()
        self._data_table.setAlternatingRowColors(True)
        splitter.addWidget(self._data_table)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter, 1)

    def set_variables(self, variables: list[VariableInfo]) -> None:
        """设置可用变量列表。"""
        self._var_list.clear()
        for v in variables:
            label = f"{v.variable_name} [{v.units}]" if v.units else v.variable_name
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, v)
            self._var_list.addItem(item)

    def _on_var_selected(self, current: QListWidgetItem, _: QListWidgetItem) -> None:
        pass

    def clear(self) -> None:
        self._var_list.clear()
        self._data_table.setRowCount(0)
        self._data_table.setColumnCount(0)


class RawFilesView(QWidget):
    """原始文件浏览视图。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderLabels(["文件名", "大小"])
        self._file_tree.setColumnWidth(0, 280)
        self._file_tree.itemClicked.connect(self._on_file_clicked)
        splitter.addWidget(self._file_tree)

        self._file_view = QPlainTextEdit()
        self._file_view.setReadOnly(True)
        font = QFont("Monospace")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self._file_view.setFont(font)
        splitter.addWidget(self._file_view)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter, 1)

    def set_files(self, files: list[tuple[str, int]], run_dir: str) -> None:
        """设置文件列表。

        Args:
            files: (文件名, 大小字节) 列表。
            run_dir: 运行目录路径。
        """
        self._file_tree.clear()
        self._run_dir = run_dir
        for name, size in files:
            size_str = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
            item = QTreeWidgetItem([name, size_str])
            item.setData(0, Qt.UserRole, name)
            if name.endswith(".err"):
                item.setForeground(0, QColor("#E06C75"))
            elif name.endswith(".csv"):
                item.setForeground(0, QColor("#98C379"))
            elif name.endswith(".eso"):
                item.setForeground(0, QColor("#56B6C2"))
            self._file_tree.addTopLevelItem(item)

    def _on_file_clicked(self, item: QTreeWidgetItem, _: object) -> None:
        name = item.data(0, Qt.UserRole)
        if not name:
            return
        path = Path(self._run_dir) / name
        if not path.exists():
            return
        try:
            if path.stat().st_size > _LARGE_FILE_THRESHOLD:
                self._file_view.setPlainText("[文件过大，请使用外部编辑器查看]")
                return
            self._file_view.setPlainText(
                path.read_text(encoding="utf-8", errors="replace")
            )
        except OSError as e:
            self._file_view.setPlainText(f"[读取失败: {e}]")

    def clear(self) -> None:
        self._file_tree.clear()
        self._file_view.clear()


class ResultsView(QWidget):
    """结果视图：多标签结构化呈现。"""

    def __init__(
        self,
        results_service: ResultsService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = results_service
        self._run_dir = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()

        self._error_view = ErrorView()
        self._tabs.addTab(self._error_view, "错误")

        self._summary_view = SummaryView()
        self._tabs.addTab(self._summary_view, "汇总报告")

        self._timeseries_view = TimeseriesView()
        self._tabs.addTab(self._timeseries_view, "时序数据")

        self._raw_view = RawFilesView()
        self._tabs.addTab(self._raw_view, "原始文件")

        layout.addWidget(self._tabs)

    def load_from_run_dir(self, run_dir: str | Path) -> None:
        """从运行目录加载所有结果。"""
        self._run_dir = str(run_dir)
        errors = self._service.load_errors(run_dir)
        self._error_view.set_errors(errors)

        tables = self._service.load_tables(run_dir)
        self._summary_view.set_tables(tables)

        rdd_vars = self._service.load_rdd_variables(run_dir)
        self._timeseries_view.set_variables(rdd_vars)

        files = self._service.list_output_files(run_dir)
        self._raw_view.set_files(files, self._run_dir)

        if errors:
            self._tabs.setCurrentWidget(self._error_view)
        elif tables:
            self._tabs.setCurrentWidget(self._summary_view)

    def clear(self) -> None:
        self._error_view.clear()
        self._summary_view.clear()
        self._timeseries_view.clear()
        self._raw_view.clear()
