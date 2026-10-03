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
        self._btn_export = QPushButton("导出 PNG...")
        self._btn_export.clicked.connect(self._export_png)
        toolbar.addWidget(QLabel("图表类型:"))
        toolbar.addWidget(self._chart_type)
        toolbar.addWidget(self._btn_export)
        toolbar.addStretch()
        layout.addLayout(toolbar)

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
            label = f"{t.table_name}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, t)
            self._table_list.addItem(item)

    def _on_table_changed(self, current: QListWidgetItem, _: QListWidgetItem) -> None:
        self._refresh_plot()

    def _refresh_plot(self) -> None:
        """绘制选中表格的图表。"""
        self._figure.clear()
        item = self._table_list.currentItem()
        if item is None:
            self._canvas.draw()
            return
        table: ReportTable = item.data(Qt.UserRole)
        if not table.rows or not table.columns:
            self._canvas.draw()
            return

        numeric_data = self._extract_numeric_data(table)
        if not numeric_data:
            self._canvas.draw()
            return

        ax = self._figure.add_subplot(111)
        chart_type = self._chart_type.currentText()

        labels = [d[0] for d in numeric_data]
        values = [d[1] for d in numeric_data]

        if chart_type == "柱状图":
            ax.bar(range(len(labels)), values)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
            ax.set_ylabel("值")
        else:
            positive_vals = [v for v in values if v > 0]
            positive_labels = [labels[i] for i, v in enumerate(values) if v > 0]
            if positive_vals:
                ax.pie(positive_vals, labels=positive_labels, autopct="%1.1f%%", startangle=90)
                ax.axis("equal")

        ax.set_title(table.table_name)
        self._figure.tight_layout()
        self._canvas.draw()

    @staticmethod
    def _extract_numeric_data(table: ReportTable) -> list[tuple[str, float]]:
        """从表格中提取数值数据（行名 + 第一列数值）。"""
        result: list[tuple[str, float]] = []
        for i, row_name in enumerate(table.rows):
            if i >= len(table.cells):
                continue
            for cell in table.cells[i]:
                val_str = cell.strip()
                if "[" in val_str:
                    val_str = val_str.split("[")[0].strip()
                try:
                    val = float(val_str)
                    result.append((row_name, val))
                    break
                except ValueError:
                    continue
        return result

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
