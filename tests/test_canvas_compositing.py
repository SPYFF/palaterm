"""Compositing tests for Canvas.render_region — pin fill/line z-order behavior."""

from __future__ import annotations

from palaterm.canvas import Canvas
from palaterm.geometry import Point, Rect
from palaterm.models import (
    BorderStyle, BoxShape, FillStyle, LineShape, LineStyle,
)


def _viewport() -> Rect:
    return Rect(0, 0, 20, 10)


def _make_horizontal_line(col_a: int, col_b: int, row: int) -> LineShape:
    return LineShape(
        Point(col_a, row), Point(col_b, row),
        border=BorderStyle.LIGHT, line_style=LineStyle.ORTHOGONAL,
    )


def test_occlusion_fill_above_line_hides_line() -> None:
    """A box drawn after (above) a line, with SPACE fill, occludes the line's interior crossing."""
    line = _make_horizontal_line(0, 10, 5)
    box = BoxShape(Rect(3, 4, 5, 3), border=BorderStyle.NONE,
                   fill=FillStyle.SPACE)
    canvas = Canvas()
    canvas.shapes = [line, box]  # line below, box on top
    cells = canvas.render_region(_viewport())
    # Line cells inside the box bound must be replaced by the fill space.
    assert cells.get((4, 5)) == " "
    assert cells.get((5, 5)) == " "
    # Line cells outside the box stay visible.
    assert cells.get((1, 5)) == "─"
    assert cells.get((9, 5)) == "─"


def test_occlusion_fill_below_line_keeps_line_visible() -> None:
    """A box drawn before (below) a line, with SPACE fill, does not hide the line."""
    box = BoxShape(Rect(3, 4, 5, 3), border=BorderStyle.NONE,
                   fill=FillStyle.SPACE)
    line = _make_horizontal_line(0, 10, 5)
    canvas = Canvas()
    canvas.shapes = [box, line]  # box below, line on top
    cells = canvas.render_region(_viewport())
    # Line wins through the box's interior.
    assert cells.get((4, 5)) == "─"
    assert cells.get((5, 5)) == "─"


def test_pattern_fill_above_line_hides_line() -> None:
    """A box drawn after (above) a line, with FULL pattern, occludes the line's interior."""
    line = _make_horizontal_line(0, 10, 5)
    box = BoxShape(Rect(3, 4, 5, 3), border=BorderStyle.NONE,
                   fill=FillStyle.FULL)
    canvas = Canvas()
    canvas.shapes = [line, box]
    cells = canvas.render_region(_viewport())
    assert cells.get((4, 5)) == "█"
    assert cells.get((5, 5)) == "█"
    assert cells.get((1, 5)) == "─"


def test_pattern_fill_below_line_lets_line_through() -> None:
    """A box drawn before (below) a line, with FULL pattern, lets the line draw over it."""
    box = BoxShape(Rect(3, 4, 5, 3), border=BorderStyle.NONE,
                   fill=FillStyle.FULL)
    line = _make_horizontal_line(0, 10, 5)
    canvas = Canvas()
    canvas.shapes = [box, line]
    cells = canvas.render_region(_viewport())
    # Line replaces the pattern fill where they overlap.
    assert cells.get((4, 5)) == "─"
    assert cells.get((5, 5)) == "─"
    # Pattern fill remains visible where the line doesn't run.
    assert cells.get((4, 4)) == "█"
    assert cells.get((4, 6)) == "█"
