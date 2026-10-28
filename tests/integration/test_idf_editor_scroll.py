"""源码编辑器行号栏与水平滚动交互回归。"""

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont, QTextCursor

from src.ui.editor.idf_editor import IDFEditor


@pytest.fixture
def editor(qtbot):
    widget = IDFEditor()
    widget.resize(480, 260)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


def assert_separate_gutter(editor: IDFEditor) -> None:
    """验证行号栏不会占据正文和水平滚动条。"""
    gutter = editor._line_area.geometry()
    viewport = editor.viewport().geometry()
    scrollbar = editor.horizontalScrollBar()
    bar_top = scrollbar.mapTo(editor, QPoint(0, 0)).y()
    assert gutter.right() < viewport.left()
    assert gutter.top() == viewport.top()
    assert gutter.bottom() == viewport.bottom()
    if scrollbar.isVisible():
        assert gutter.bottom() < bar_top
    assert gutter.width() == editor.line_number_width()


def test_long_line_scroll_reaches_both_ends(editor, qtbot) -> None:
    editor.setPlainText("Material, " + "Long Field " * 150 + ";")
    scrollbar = editor.horizontalScrollBar()
    qtbot.waitUntil(lambda: scrollbar.maximum() > 0)
    qtbot.waitUntil(lambda: scrollbar.isVisible())
    assert editor.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert_separate_gutter(editor)
    first = editor.document().findBlockByNumber(0)
    cursor = QTextCursor(first)
    start_x = editor.cursorRect(cursor).x()
    scrollbar.setValue(scrollbar.maximum())
    qtbot.waitUntil(lambda: editor.cursorRect(cursor).x() < start_x)
    cursor.movePosition(QTextCursor.EndOfBlock)
    assert editor.cursorRect(cursor).right() <= editor.viewport().width()
    scrollbar.setValue(0)
    cursor.movePosition(QTextCursor.StartOfBlock)
    qtbot.waitUntil(lambda: editor.cursorRect(cursor).x() == start_x)
    assert editor.cursorRect(cursor).left() >= 0
    assert_separate_gutter(editor)


def test_short_line_does_not_force_horizontal_scrollbar(editor, qtbot) -> None:
    editor.setPlainText("Zone, A;")
    qtbot.waitUntil(lambda: not editor.horizontalScrollBar().isVisible())
    assert editor.horizontalScrollBar().maximum() == 0
    assert_separate_gutter(editor)


def test_gutter_tracks_font_line_count_and_resize(editor, qtbot) -> None:
    editor.setPlainText("\n".join("Zone, A;" for _ in range(1000)))
    qtbot.waitUntil(lambda: editor.blockCount() == 1000)
    for point_size in (24, 8):
        font = QFont(editor.font())
        font.setPointSize(point_size)
        editor.setFont(font)
        qtbot.waitUntil(lambda: editor._line_area.width() == editor.line_number_width())
        assert_separate_gutter(editor)
    editor.setPlainText("Zone, A;")
    editor.resize(640, 320)
    qtbot.waitUntil(lambda: editor._line_area.height() == editor.viewport().height())
    assert_separate_gutter(editor)
