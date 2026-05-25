"""Tests for the pure ``compute_sidebar_state`` function.

These cross the new seam between Sidebar logic and Sidebar rendering: the
state dataclass. They exercise the visibility/active-value rules without
spinning up Textual.
"""

from __future__ import annotations

from palaterm.controllers import ToolController
from palaterm.geometry import Point, Rect
from palaterm.models import (
    BorderStyle,
    BoxShape,
    EndingStyle,
    FillStyle,
    HAlign,
    LineShape,
    LineStyle,
    VAlign,
)
from palaterm.sidebar_state import compute_sidebar_state
from palaterm.tools import (
    LineTool,
    RectangleTool,
    SelectMode,
    SelectTool,
    TextTool,
    ToolType,
)


def _box(text: str = "", **kw) -> BoxShape:
    return BoxShape(rect=Rect(0, 0, 5, 3), text=text, **kw)


def _line() -> LineShape:
    return LineShape(start=Point(0, 0), end=Point(10, 0))


def test_select_no_selection_hides_style_panels() -> None:
    state = compute_sidebar_state(SelectTool(), ToolController())
    assert state.select_mode.visible is True
    assert state.border.visible is False
    assert state.fill.visible is False
    assert state.line_style.visible is False
    assert state.line_endings.visible is False
    assert state.text_align.visible is False
    assert state.shape_align.visible is False
    assert state.layer.visible is False


def test_rectangle_tool_shows_border_and_fill_with_persistent_style() -> None:
    tc = ToolController()
    tc.border_style = BorderStyle.HEAVY
    tc.fill = FillStyle.MEDIUM
    tool = RectangleTool(tc.border_style, tc.fill)

    state = compute_sidebar_state(tool, tc)

    assert state.border.visible is True
    assert state.border.active is BorderStyle.HEAVY
    assert state.fill.visible is True
    assert state.fill.active is FillStyle.MEDIUM
    assert state.line_style.visible is False
    assert state.select_mode.visible is False


def test_line_tool_shows_line_style_and_endings() -> None:
    tc = ToolController()
    tc.line_style = LineStyle.STRAIGHT
    tc.start_ending = EndingStyle.ARROW
    tc.end_ending = EndingStyle.CIRCLE
    tool = LineTool(tc.border_style, tc.line_style, tc.start_ending, tc.end_ending)

    state = compute_sidebar_state(tool, tc)

    assert state.line_style.visible is True
    assert state.line_style.active is LineStyle.STRAIGHT
    assert state.line_endings.visible is True
    assert state.line_endings.start is EndingStyle.ARROW
    assert state.line_endings.end is EndingStyle.CIRCLE
    assert state.fill.visible is False


def test_select_with_box_shows_border_fill_and_layer() -> None:
    tool = SelectTool()
    box = _box(border=BorderStyle.DOUBLE, fill=FillStyle.LIGHT)
    tool.selected = [box]

    state = compute_sidebar_state(tool, ToolController())

    assert state.border.visible is True
    assert state.border.active is BorderStyle.DOUBLE
    assert state.fill.visible is True
    assert state.fill.active is FillStyle.LIGHT
    assert state.layer.visible is True
    assert state.shape_align.visible is False


def test_select_with_mixed_borders_clears_active() -> None:
    tool = SelectTool()
    tool.selected = [
        _box(border=BorderStyle.LIGHT),
        _box(border=BorderStyle.HEAVY),
    ]

    state = compute_sidebar_state(tool, ToolController())

    assert state.border.visible is True
    assert state.border.active is None


def test_select_with_two_shapes_shows_shape_align() -> None:
    tool = SelectTool()
    tool.selected = [_box(), _box()]

    state = compute_sidebar_state(tool, ToolController())

    assert state.shape_align.visible is True
    assert state.layer.visible is True


def test_select_with_text_box_shows_text_align() -> None:
    tool = SelectTool()
    box = _box(text="hi")
    box.halign = HAlign.RIGHT
    box.valign = VAlign.BOTTOM
    tool.selected = [box]

    state = compute_sidebar_state(tool, ToolController())

    assert state.text_align.visible is True
    assert state.text_align.halign is HAlign.RIGHT
    assert state.text_align.valign is VAlign.BOTTOM


def test_select_with_line_shows_line_style_from_shape() -> None:
    tool = SelectTool()
    line = _line()
    line.line_style = LineStyle.STRAIGHT
    line.start_ending = EndingStyle.SQUARE
    line.end_ending = EndingStyle.STAR
    tool.selected = [line]

    state = compute_sidebar_state(tool, ToolController())

    assert state.line_style.visible is True
    assert state.line_style.active is LineStyle.STRAIGHT
    assert state.line_endings.start is EndingStyle.SQUARE
    assert state.line_endings.end is EndingStyle.STAR


def test_select_mode_active_value_is_select_tool_mode() -> None:
    tool = SelectTool()
    tool.mode = SelectMode.PARTIAL

    state = compute_sidebar_state(tool, ToolController())

    assert state.select_mode.active is SelectMode.PARTIAL


def test_tool_picker_active_reflects_tool_controller() -> None:
    tc = ToolController()
    tc.active_tool_type = ToolType.LINE

    state = compute_sidebar_state(SelectTool(), tc)

    assert state.tool_picker_active is ToolType.LINE


def test_text_tool_shows_border_and_fill() -> None:
    tc = ToolController()
    tool = TextTool(tc.border_style, tc.fill)

    state = compute_sidebar_state(tool, tc)

    assert state.border.visible is True
    assert state.fill.visible is True
    assert state.line_style.visible is False
