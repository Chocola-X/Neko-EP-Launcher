"""IDF 文件编辑器组件，带语法高亮和行号。"""
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import (
    QColor, QTextFormat, QPainter, QFont, QSyntaxHighlighter,
    QTextCharFormat, QKeySequence, QPalette
)
from PySide6.QtWidgets import (
    QPlainTextEdit, QWidget, QTextEdit
)


class IDFHighlighter(QSyntaxHighlighter):
    """IDF 语法高亮器。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._formats = {}

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
        f.setForeground(QColor("#FFFFFF"))
        f.setFontWeight(QFont.Bold)
        self._formats["terminator"] = f

    def highlightBlock(self, text):
        if not text:
            return

        stripped = text.lstrip()
        leading = len(text) - len(stripped)

        if stripped.startswith("!"):
            if "!-" in stripped:
                idx = stripped.index("!-")
                self.setFormat(0, len(text), self._formats["comment"])
                fn_start = leading + idx + 2
                self.setFormat(fn_start, len(text) - fn_start,
                               self._formats["field_name"])
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

        self._highlight_code(code_part, 0)

        if comment_part:
            start = len(code_part)
            if "!-" in comment_part:
                idx = comment_part.index("!-")
                self.setFormat(start, idx, self._formats["comment"])
                self.setFormat(start + idx + 2, len(comment_part) - idx - 2,
                               self._formats["field_name"])
            else:
                self.setFormat(start, len(comment_part),
                               self._formats["comment"])

    def _find_comment_pos(self, text):
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

    def _highlight_code(self, text, offset):
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
            token_end = content_start + len(token)

            if self.currentBlock().blockNumber() == 0 or self._is_object_line():
                self.setFormat(token_start, len(token), self._formats["object"])
            else:
                self._highlight_value(token, token_start)

            if term_pos < len(text):
                self.setFormat(offset + term_pos, 1,
                               self._formats["terminator"])
        else:
            self._highlight_value(stripped, content_start)

    def _is_object_line(self):
        return False

    def _highlight_value(self, token, start):
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

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event):
        self._editor.paint_line_numbers(event)


class IDFEditor(QPlainTextEdit):
    """IDF 文本编辑器，带行号和语法高亮。"""

    def __init__(self, parent=None):
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

    def line_number_width(self):
        digits = max(1, len(str(self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def _update_line_width(self, _):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_line_area(self, rect, dy):
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(),
                                   self._line_area.width(), rect.height())
        if rect.width() > self.viewport().width():
            self._update_line_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(QRect(cr.left(), cr.top(),
                                          self.line_number_width(),
                                          cr.height()))

    def paint_line_numbers(self, event):
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
                painter.drawText(0, top, self._line_area.width() - 2,
                                 self.fontMetrics().height(),
                                 Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self):
        selections = []
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor("#3E4451"))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        selections.append(selection)
        self.setExtraSelections(selections)

    def jump_to_line(self, line):
        block = self.document().findBlockByNumber(line - 1)
        if block.isValid():
            cursor = self.textCursor()
            cursor.setPosition(block.position())
            self.setTextCursor(cursor)
            self.centerCursor()

    def find_text(self, text):
        from PySide6.QtGui import QTextCursor
        cursor = self.textCursor()
        search_cursor = self.document().find(text, cursor)
        if search_cursor.isNull():
            cursor.movePosition(QTextCursor.Start)
            search_cursor = self.document().find(text, cursor)
        if not search_cursor.isNull():
            self.setTextCursor(search_cursor)
            return True
        return False
