"""Compositing tests for Canvas — pin fill/line z-order behavior."""

from __future__ import annotations

from palaterm.canvas import Canvas
from palaterm.geometry import Point, Rect
from palaterm.models import (
    BorderStyle,
    BoxShape,
    FillStyle,
    LineShape,
    LineStyle,
)


def _viewport() -> Rect:
    return Rect(0, 0, 20, 10)


def _make_horizontal_line(col_a: int, col_b: int, row: int) -> LineShape:
    return LineShape(
        Point(col_a, row),
        Point(col_b, row),
        border=BorderStyle.LIGHT,
        line_style=LineStyle.ORTHOGONAL,
    )


def test_occlusion_fill_above_line_hides_line() -> None:
    """A box drawn after (above) a line, with SPACE fill,
    occludes the line's interior crossing."""
    line = _make_horizontal_line(0, 10, 5)
    box = BoxShape(Rect(3, 4, 5, 3), border=BorderStyle.NONE, fill=FillStyle.SPACE)
    canvas = Canvas()
    canvas.shapes = [line, box]  # line below, box on top
    cells = canvas.composite(_viewport())
    # Line cells inside the box bound must be replaced by the fill space.
    assert cells.get((4, 5))[0] == " "
    assert cells.get((5, 5))[0] == " "
    # Line cells outside the box stay visible.
    assert cells.get((1, 5))[0] == "─"
    assert cells.get((9, 5))[0] == "─"


def test_occlusion_fill_below_line_keeps_line_visible() -> None:
    """A box drawn before (below) a line, with SPACE fill, does not hide the line."""
    box = BoxShape(Rect(3, 4, 5, 3), border=BorderStyle.NONE, fill=FillStyle.SPACE)
    line = _make_horizontal_line(0, 10, 5)
    canvas = Canvas()
    canvas.shapes = [box, line]  # box below, line on top
    cells = canvas.composite(_viewport())
    # Line wins through the box's interior.
    assert cells.get((4, 5))[0] == "─"
    assert cells.get((5, 5))[0] == "─"


def test_pattern_fill_above_line_hides_line() -> None:
    """A box drawn after (above) a line, with FULL pattern,
    occludes the line's interior."""
    line = _make_horizontal_line(0, 10, 5)
    box = BoxShape(Rect(3, 4, 5, 3), border=BorderStyle.NONE, fill=FillStyle.FULL)
    canvas = Canvas()
    canvas.shapes = [line, box]
    cells = canvas.composite(_viewport())
    assert cells.get((4, 5))[0] == "█"
    assert cells.get((5, 5))[0] == "█"
    assert cells.get((1, 5))[0] == "─"


def test_pattern_fill_below_line_lets_line_through() -> None:
    """A box drawn before (below) a line, with FULL pattern,
    lets the line draw over it."""
    box = BoxShape(Rect(3, 4, 5, 3), border=BorderStyle.NONE, fill=FillStyle.FULL)
    line = _make_horizontal_line(0, 10, 5)
    canvas = Canvas()
    canvas.shapes = [box, line]
    cells = canvas.composite(_viewport())
    # Line replaces the pattern fill where they overlap.
    assert cells.get((4, 5))[0] == "─"
    assert cells.get((5, 5))[0] == "─"
    # Pattern fill remains visible where the line doesn't run.
    assert cells.get((4, 4))[0] == "▄"  # top edge of borderless fill
    assert cells.get((4, 6))[0] == "▀"  # bottom edge of borderless fill


# --- Canvas.composite tests -----------------------------------------------


def test_composite_t_junction_filled_box_above() -> None:
    """Two overlapping bordered boxes: top has fill=SPACE.

    At border intersections, the bottom box's vertical arm going INTO
    the top box's interior is blocked → T-junctions.
    """
    box_a = BoxShape(Rect(0, 0, 10, 5), border=BorderStyle.LIGHT, fill=FillStyle.NONE)
    box_b = BoxShape(Rect(5, 1, 8, 3), border=BorderStyle.LIGHT, fill=FillStyle.SPACE)
    canvas = Canvas()
    canvas.shapes = [box_a, box_b]
    cells = canvas.composite(_viewport())

    # Box A's right border (col=9) meets Box B's top border (row=1).
    # The arm going DOWN into Box B's interior is blocked → ┴
    assert cells[(9, 1)][0] == "┴"
    # Box A's right border (col=9) meets Box B's bottom border (row=3).
    # The arm going UP into Box B's interior is blocked → ┬
    assert cells[(9, 3)][0] == "┬"
    # Box A's right border at row=2 is inside Box B's fill → occluded by space
    assert cells[(9, 2)][0] == " "


def test_composite_no_fill_produces_full_crossing() -> None:
    """Two overlapping bordered boxes: top has fill=NONE (transparent).

    Full crossing resolution applies — ┼ at intersections.
    """
    box_a = BoxShape(Rect(0, 0, 10, 5), border=BorderStyle.LIGHT, fill=FillStyle.NONE)
    box_b = BoxShape(Rect(5, 1, 8, 3), border=BorderStyle.LIGHT, fill=FillStyle.NONE)
    canvas = Canvas()
    canvas.shapes = [box_a, box_b]
    cells = canvas.composite(_viewport())

    # No fill → normal crossing
    assert cells[(9, 1)][0] == "┼"
    assert cells[(9, 3)][0] == "┼"
    # Box A's vertical is visible through Box B's transparent interior
    assert cells[(9, 2)][0] == "│"


def test_composite_color_top_shape_owns_cell() -> None:
    """Top shape with no color clears color from below (no bleed)."""
    box_a = BoxShape(Rect(0, 0, 5, 3), border=BorderStyle.LIGHT, fill=FillStyle.NONE)
    box_a.fg = "red"
    box_b = BoxShape(Rect(0, 0, 5, 3), border=BorderStyle.LIGHT, fill=FillStyle.NONE)
    # box_b has no color (fg=None, bg=None)
    canvas = Canvas()
    canvas.shapes = [box_a, box_b]
    cells = canvas.composite(_viewport())

    # Top shape owns the cell — no color bleed from below
    assert cells[(0, 0)][1] is None
    assert cells[(0, 0)][2] is None


def test_composite_color_crossing_top_wins() -> None:
    """When borders cross, the higher-z shape's color wins."""
    box = BoxShape(Rect(0, 0, 5, 5), border=BorderStyle.LIGHT, fill=FillStyle.NONE)
    box.fg = "red"
    line = LineShape(
        Point(0, 2),
        Point(4, 2),
        border=BorderStyle.LIGHT,
        line_style=LineStyle.ORTHOGONAL,
    )
    line.fg = "blue"
    canvas = Canvas()
    canvas.shapes = [box, line]  # line is on top
    cells = canvas.composite(_viewport())

    # At the crossing point (col=0, row=2) — line is on top, gets blue
    assert cells[(0, 2)][1] == "blue"
    # The crossing char should be a merge (├ since box's left border + line's ─)
    assert cells[(0, 2)][0] == "├"


def test_composite_line_occluded_by_fill() -> None:
    """A line below a filled box is hidden inside the fill area."""
    line = _make_horizontal_line(0, 10, 2)
    box = BoxShape(Rect(3, 1, 5, 3), border=BorderStyle.LIGHT, fill=FillStyle.SPACE)
    canvas = Canvas()
    canvas.shapes = [line, box]
    cells = canvas.composite(_viewport())

    # Line inside box's fill interior (inset by 1 from border) is hidden
    assert cells[(4, 2)][0] == " "
    assert cells[(5, 2)][0] == " "
    # Line outside box is visible
    assert cells[(1, 2)][0] == "─"
    assert cells[(9, 2)][0] == "─"


def test_composite_t_junction_heavy_border() -> None:
    """Heavy-bordered boxes produce heavy T-junctions when occluding."""
    box_a = BoxShape(Rect(0, 0, 10, 5), border=BorderStyle.HEAVY, fill=FillStyle.NONE)
    box_b = BoxShape(Rect(5, 1, 8, 3), border=BorderStyle.HEAVY, fill=FillStyle.SPACE)
    canvas = Canvas()
    canvas.shapes = [box_a, box_b]
    cells = canvas.composite(_viewport())

    # Box A's right border (col=9) meets Box B's top border (row=1).
    # The arm going DOWN into Box B's interior is blocked → ┻
    assert cells[(9, 1)][0] == "┻"
    # Box A's right border (col=9) meets Box B's bottom border (row=3).
    # The arm going UP into Box B's interior is blocked → ┳
    assert cells[(9, 3)][0] == "┳"
    # Box A's right border at row=2 is inside Box B's fill → occluded
    assert cells[(9, 2)][0] == " "


def test_composite_t_junction_double_border() -> None:
    """Double-bordered boxes produce double T-junctions when occluding."""
    box_a = BoxShape(Rect(0, 0, 10, 5), border=BorderStyle.DOUBLE, fill=FillStyle.NONE)
    box_b = BoxShape(Rect(5, 1, 8, 3), border=BorderStyle.DOUBLE, fill=FillStyle.SPACE)
    canvas = Canvas()
    canvas.shapes = [box_a, box_b]
    cells = canvas.composite(_viewport())

    # Box A's right border (col=9) meets Box B's top border (row=1).
    # The arm going DOWN into Box B's interior is blocked → ╩
    assert cells[(9, 1)][0] == "╩"
    # Box A's right border (col=9) meets Box B's bottom border (row=3).
    # The arm going UP into Box B's interior is blocked → ╦
    assert cells[(9, 3)][0] == "╦"


def test_composite_block_elements_merge() -> None:
    """Overlapping borderless filled boxes merge their quadrant characters."""
    # Two boxes whose corners overlap at a single cell.
    # Box A's bottom-right corner (▘) meets Box B's top-left corner (▗) → ▚
    box_a = BoxShape(Rect(0, 0, 4, 4), border=BorderStyle.NONE, fill=FillStyle.FULL)
    box_b = BoxShape(Rect(3, 3, 4, 4), border=BorderStyle.NONE, fill=FillStyle.FULL)
    canvas = Canvas()
    canvas.shapes = [box_a, box_b]
    cells = canvas.composite(Rect(0, 0, 7, 7))

    # At (3,3): box_a renders ▘ (bottom-right corner), box_b renders ▗ (top-left corner)
    # OR: 0b0001 | 0b1000 = 0b1001 = ▚
    assert cells[(3, 3)][0] == "▚"
