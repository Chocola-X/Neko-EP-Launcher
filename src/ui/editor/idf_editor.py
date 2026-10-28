"""IDF 文本编辑器组件，带语法高亮与行号。

高亮修复：``_is_object_line`` 改为基于当前块是否为对象首行判断（通过记录
对象起始行集合），使对象类型名高亮生效。
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPalette,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QTextEdit, QWidget


class IDFHighlighter(QSyntaxHighlighter):
    """IDF 语法高亮器。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._formats: dict[str, QTextCharFormat] = {}
        self._object_lines: set[int] = set()

        f = QTextCharFormat()
        f.setForeground(QColor("#56B6C2"))
        f.setFontWeight(QFont.Bold)
        self._formats["object"] = f

        f = QTextCharFormat()
        f.setForeground(QColor("#98C379"))
        self._formats["value"] = f

        f = QTextCharFormat()
        f.setForeground(QColor("#E5C07B"))
        self._formats["number"] = f

        f = QTextCharFormat()
        f.setForeground(QColor("#7F848E"))
        f.setFontItalic(True)
        self._formats["comment"] = f

        f = QTextCharFormat()
        f.setForeground(QColor("#C678DD"))
        self._formats["field_name"] = f

        f = QTextCharFormat()
        f.setForeground(QColor("#E06C75"))
        self._formats["string"] = f

        f = QTextCharFormat()
        f.setForeground(QApplication.palette().color(QPalette.Text))
        f.setFontWeight(QFont.Bold)
        self._formats["terminator"] = f
        self.set_text_color(QApplication.palette().color(QPalette.Text))

    def set_text_color(self, color: QColor) -> None:
        """让分隔符颜色随系统调色板更新。"""
        light = color.lightness() < 128
        colors = {
            "object": "#005a9c" if light else "#56b6c2",
            "value": "#21633e" if light else "#98c379",
            "number": "#8a4b08" if light else "#e5c07b",
            "comment": "#626970" if light else "#9ba4ae",
            "field_name": "#77409a" if light else "#c678dd",
            "string": "#ad2540" if light else "#e06c75",
        }
        for name, value in colors.items():
            self._formats[name].setForeground(QColor(value))
        self._formats["terminator"].setForeground(color)
        self.rehighlight()

    def set_object_lines(self, lines: set[int]) -> None:
        """设置对象起始行号集合（0-based），用于对象类型名高亮。"""
        self._object_lines = lines
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        if not text:
            return
        block_number = self.currentBlock().blockNumber()
        stripped = text.lstrip()
        leading = len(text) - len(stripped)

        if stripped.startswith("!"):
            if "!-" in stripped:
                idx = stripped.index("!-")
                self.setFormat(0, len(text), self._formats["comment"])
                fn_start = leading + idx + 2
                self.setFormat(fn_start, len(text) - fn_start, self._formats["field_name"])
            else:
                self.setFormat(0, len(text), self._formats["comment"])
            return

        comment_pos = self._find_comment_pos(text)
        if comment_pos >= 0:
            code_part = text[:comment_pos]
            comment_part = text[comment_pos:]
        else:
            code_part = text
            comment_part = ""

        self._highlight_code(code_part, 0, block_number)

        if comment_part:
            start = len(code_part)
            if "!-" in comment_part:
                idx = comment_part.index("!-")
                self.setFormat(start, idx, self._formats["comment"])
                self.setFormat(
                    start + idx + 2, len(comment_part) - idx - 2, self._formats["field_name"]
                )
            else:
                self.setFormat(start, len(comment_part), self._formats["comment"])

    def _find_comment_pos(self, text: str) -> int:
        in_squote = False
        in_dquote = False
        for i, ch in enumerate(text):
            if ch == "'" and not in_dquote:
                in_squote = not in_squote
            elif ch == '"' and not in_squote:
                in_dquote = not in_dquote
            elif ch == "!" and not in_squote and not in_dquote:
                return i
        return -1

    def _highlight_code(self, text: str, offset: int, block_number: int) -> None:
        stripped = text.strip()
        if not stripped:
            return
        leading = len(text) - len(stripped)
        content_start = offset + leading

        if "," in text or ";" in text:
            comma_pos = text.find(",")
            semi_pos = text.find(";")
            if semi_pos >= 0 and (comma_pos < 0 or semi_pos < comma_pos):
                term_pos = semi_pos
            elif comma_pos >= 0:
                term_pos = comma_pos
            else:
                term_pos = len(text)

            token = text[:term_pos].strip()
            token_start = content_start

            if block_number == 0 or block_number in self._object_lines:
                self.setFormat(token_start, len(token), self._formats["object"])
            else:
                self._highlight_value(token, token_start)

            if term_pos < len(text):
                self.setFormat(offset + term_pos, 1, self._formats["terminator"])
        else:
            self._highlight_value(stripped, content_start)

    def _highlight_value(self, token: str, start: int) -> None:
        token = token.strip()
        if not token:
            return
        if token.startswith("$"):
            self.setFormat(start, len(token), self._formats["field_name"])
            return
        if token.startswith("'") or token.startswith('"'):
            self.setFormat(start, len(token), self._formats["string"])
            return
        try:
            float(token)
            self.setFormat(start, len(token), self._formats["number"])
            return
        except ValueError:
            pass
        self.setFormat(start, len(token), self._formats["value"])


class LineNumberArea(QWidget):
    """行号区域。"""

    def __init__(self, editor: IDFEditor) -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event) -> None:
        self._editor.paint_line_numbers(event)


class IDFEditor(QPlainTextEdit):
    """IDF 文本编辑器，带行号和语法高亮。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFont("Monospace")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self.setFont(font)

        self._line_area = LineNumberArea(self)
        self._highlighter = IDFHighlighter(self.document())

        self.blockCountChanged.connect(self._update_line_width)
        self.updateRequest.connect(self._update_line_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)

        self._update_line_width(0)
        self._highlight_current_line()

    def set_object_lines(self, lines: set[int]) -> None:
        """设置对象起始行号集合（0-based）。"""
        self._highlighter.set_object_lines(lines)

    def line_number_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return 8 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_width(self, _: int) -> None:
        self.setViewportMargins(self.line_number_width() + 4, 0, 0, 0)
        self._sync_line_area_geometry()

    def _sync_line_area_geometry(self) -> None:
        """行号栏与正文等高，底部独立留给水平滚动条。"""
        viewport = self.viewport().geometry()
        self._line_area.setGeometry(
            QRect(
                self.contentsRect().left(),
                viewport.top(),
                self.line_number_width(),
                viewport.height(),
            )
        )
        self._line_area.update()

    def _update_line_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_width(0)
        else:
            self._sync_line_area_geometry()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_line_area_geometry()

    def paint_line_numbers(self, event) -> None:
        painter = QPainter(self._line_area)
        painter.fillRect(event.rect(), self._line_area.palette().color(QPalette.Window))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        current = self.textCursor().blockNumber()
        font = self.font()
        current_font = QFont(font)
        current_font.setBold(True)

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                if block_number == current:
                    painter.setFont(current_font)
                    painter.setPen(QColor("#E06C75"))
                else:
                    painter.setFont(font)
                    painter.setPen(QColor("#7F848E"))
                painter.drawText(
                    0,
                    top,
                    self._line_area.width() - 2,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self) -> None:
        selections = []
        selection = QTextEdit.ExtraSelection()
        color = self.palette().color(QPalette.Highlight)
        color.setAlpha(35)
        selection.format.setBackground(color)
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        selections.append(selection)
        self.setExtraSelections(selections)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (
            QEvent.FontChange,
            QEvent.StyleChange,
            QEvent.LayoutDirectionChange,
        ) and hasattr(self, "_line_area"):
            self._update_line_width(0)
        if event.type() == QEvent.PaletteChange and hasattr(self, "_highlighter"):
            self._highlighter.set_text_color(self.palette().color(QPalette.Text))
            self._highlight_current_line()

    def jump_to_line(self, line: int) -> None:
        block = self.document().findBlockByNumber(line - 1)
        if block.isValid():
            cursor = self.textCursor()
            cursor.setPosition(block.position())
            self.setTextCursor(cursor)
            self.centerCursor()

    def find_text(self, text: str) -> bool:
        """查找文本，找到返回 True。"""
        cursor = self.textCursor()
        search_cursor = self.document().find(text, cursor)
        if search_cursor.isNull():
            cursor.movePosition(QTextCursor.Start)
            search_cursor = self.document().find(text, cursor)
        if not search_cursor.isNull():
            self.setTextCursor(search_cursor)
            return True
        return False
