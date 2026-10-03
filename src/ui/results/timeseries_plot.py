"""时序数据绘图视图。

使用 matplotlib ``FigureCanvasQTAgg`` 嵌入 Qt，从 ``SQLReader`` 取变量时序绘制折线图。
"""

from __future__ import annotations

import logging

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from src.core.results.models import ReportVariable
from src.core.results.sql_reader import SQLReader

logger = logging.getLogger(__name__)


class TimeseriesPlotView(QWidget):
    """时序曲线绘图视图。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reader: SQLReader | None = None
        self._variables: list[ReportVariable] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self._btn_refresh = QPushButton("刷新")
        self._btn_refresh.clicked.connect(self._refresh_plot)
        self._btn_export = QPushButton("导出 PNG...")
        self._btn_export.clicked.connect(self._export_png)
        self._btn_clear = QPushButton("清除")
        self._btn_clear.clicked.connect(self._clear_plot)
        toolbar.addWidget(self._btn_refresh)
        toolbar.addWidget(self._btn_export)
        toolbar.addWidget(self._btn_clear)
        toolbar.addStretch()
        self._info_label = QLabel("")
        toolbar.addWidget(self._info_label)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)

        self._var_list = QListWidget()
        self._var_list.setSelectionMode(QListWidget.ExtendedSelection)
        self._var_list.currentItemChanged.connect(self._on_var_changed)
        splitter.addWidget(self._var_list)

        self._figure = Figure(figsize=(8, 4))
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setParent(self)
        splitter.addWidget(self._canvas)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter, 1)

    def set_reader(self, reader: SQLReader | None) -> None:
        """设置 SQL 读取器并加载变量列表。"""
        self._reader = reader
        self._var_list.clear()
        self._variables = []
        if reader is None:
            self._info_label.setText("无 SQL 数据")
            return
        try:
            self._variables = reader.list_variables()
        except Exception as e:
            logger.warning("加载变量列表失败: %s", e)
            self._info_label.setText(f"加载失败: {e}")
            return
        for v in self._variables:
            label = f"{v.name} [{v.units}]" if v.units else v.name
            if v.key_value and v.key_value != "Environment":
                label += f" ({v.key_value})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, v)
            self._var_list.addItem(item)
        self._info_label.setText(f"{len(self._variables)} 个变量")

    def _on_var_changed(self, current: QListWidgetItem, _: QListWidgetItem) -> None:
        self._refresh_plot()

    def _refresh_plot(self) -> None:
        """绘制选中变量的时序曲线。"""
        self._figure.clear()
        if self._reader is None:
            self._canvas.draw()
            return

        selected = self._var_list.selectedItems()
        if not selected:
            self._canvas.draw()
            return

        ax = self._figure.add_subplot(111)
        for item in selected:
            var: ReportVariable = item.data(Qt.UserRole)
            try:
                points = self._reader.get_timeseries(var.index)
            except Exception as e:
                logger.warning("取时序数据失败: %s", e)
                continue
            if not points:
                continue
            x = list(range(len(points)))
            y = [p.value for p in points]
            label = var.name
            if var.key_value and var.key_value != "Environment":
                label += f" ({var.key_value})"
            ax.plot(x, y, label=label, linewidth=0.8)

        ax.set_xlabel("时间步")
        ax.set_ylabel("值")
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.3)
        self._figure.tight_layout()
        self._canvas.draw()

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

    def _clear_plot(self) -> None:
        self._figure.clear()
        self._canvas.draw()

    def clear(self) -> None:
        self._var_list.clear()
        self._variables = []
        self._figure.clear()
        self._canvas.draw()
        self._info_label.setText("")
