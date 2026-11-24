"""能耗汇总图视图。

基于 ``table_parser`` 解析的 ``ReportTable`` 数据绘制柱状图/饼图。
"""

from __future__ import annotations

import logging

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.core.results.models import ReportTable
from src.core.results.summary_chart import prepare_summary_chart

logger = logging.getLogger(__name__)


class SummaryPlotView(QWidget):
    """能耗汇总图视图。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tables: list[ReportTable] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self._chart_type = QComboBox()
        self._chart_type.addItems(["柱状图", "饼图"])
        self._chart_type.currentTextChanged.connect(self._refresh_plot)
        self._column = QComboBox()
        self._column.currentIndexChanged.connect(self._refresh_plot)
        toolbar.addWidget(QLabel("数据列:"))
        toolbar.addWidget(self._column)
        self._btn_export = QPushButton("导出 PNG...")
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self._export_png)
        toolbar.addWidget(QLabel("图表类型:"))
        toolbar.addWidget(self._chart_type)
        toolbar.addWidget(self._btn_export)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._notice = QLabel()
        self._notice.setWordWrap(True)
        layout.addWidget(self._notice)

        splitter = QSplitter(Qt.Horizontal)

        self._table_list = QListWidget()
        self._table_list.currentItemChanged.connect(self._on_table_changed)
        splitter.addWidget(self._table_list)

        self._figure = Figure(figsize=(8, 4))
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setParent(self)
        splitter.addWidget(self._canvas)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter, 1)

    def set_tables(self, tables: list[ReportTable]) -> None:
        """设置表格数据。"""
        self._tables = tables
        self._table_list.clear()
        for t in tables:
            if not t.columns or not t.rows:
                continue
            label = f"{t.report_name} / {t.table_name} ({t.report_for})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, t)
            self._table_list.addItem(item)

    def _on_table_changed(self, current: QListWidgetItem, _: QListWidgetItem) -> None:
        self._column.blockSignals(True)
        self._column.clear()
        if current is not None:
            self._column.addItems(current.data(Qt.UserRole).columns)
        self._column.blockSignals(False)
        self._refresh_plot()

    def _refresh_plot(self) -> None:
        """绘制选中表格的图表。"""
        self._figure.clear()
        self._notice.clear()
        self._btn_export.setEnabled(False)
        item = self._table_list.currentItem()
        if item is None:
            self._canvas.draw()
            return
        table: ReportTable = item.data(Qt.UserRole)
        pie = self._chart_type.currentText() == "饼图"
        try:
            data = prepare_summary_chart(table, self._column.currentIndex(), pie=pie)
        except ValueError as exc:
            self._notice.setText(str(exc))
            self._canvas.draw()
            return

        ax = self._figure.add_subplot(111)
        if pie:
            ax.pie(data.values, labels=data.labels, autopct="%1.1f%%", startangle=90)
            ax.set_title(f"{table.table_name} · {data.axis_label}")
        else:
            ax.bar(range(len(data.labels)), data.values)
            ax.set_xticks(range(len(data.labels)))
            ax.set_xticklabels(data.labels, rotation=45, ha="right", fontsize=8)
            ax.set_ylabel(data.axis_label)
            ax.set_title(table.table_name)

        self._figure.tight_layout()
        self._canvas.draw()
        self._btn_export.setEnabled(True)

    def _export_png(self) -> None:
        """导出当前图表为 PNG。"""
        if not self._figure.get_axes():
            QMessageBox.information(self, "提示", "没有可导出的图表")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 PNG", "", "PNG 图片 (*.png);;所有文件 (*)"
        )
        if path:
            try:
                self._figure.savefig(path, dpi=150, bbox_inches="tight")
                QMessageBox.information(self, "成功", f"已导出到 {path}")
            except OSError as e:
                QMessageBox.warning(self, "失败", f"导出失败: {e}")

    def clear(self) -> None:
        self._table_list.clear()
        self._tables = []
        self._figure.clear()
        self._canvas.draw()
