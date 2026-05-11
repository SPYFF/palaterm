"""Tests for shape models and geometry primitives."""

from __future__ import annotations

import pytest

from palaterm.geometry import Point, Rect
from palaterm.models import (
    BorderStyle, BoxShape, CharSet, FillStyle, HAlign, LineShape, LineStyle,
)


# --- Rect ----------------------------------------------------------------

def test_rect_right_bottom_derived() -> None:
    r = Rect(2, 3, 5, 4)
    assert r.right == 6   # 2 + 5 - 1
    assert r.bottom == 6  # 3 + 4 - 1


def test_rect_from_points_normalizes_orientation() -> None:
    """from_points must produce the same Rect regardless of corner order."""
    p1 = Point(5, 7)
    p2 = Point(2, 3)
    r = Rect.from_points(p1, p2)
    assert r.left == 2
    assert r.top == 3
    assert r.width == 4   # cols 2..5 inclusive
    assert r.height == 5  # rows 3..7 inclusive
    # And the symmetric case yields the same Rect.
    assert Rect.from_points(p2, p1) == r


def test_rect_contains_inside_outside_and_boundary() -> None:
    r = Rect(0, 0, 4, 3)  # cols 0..3, rows 0..2
    assert r.contains(0, 0)        # top-left corner
    assert r.contains(3, 2)        # bottom-right corner
    assert r.contains(2, 1)        # interior
    assert not r.contains(-1, 0)   # left of left
    assert not r.contains(4, 0)    # right of right
    assert not r.contains(0, 3)    # below bottom


# --- BoxShape ------------------------------------------------------------

@pytest.mark.parametrize("border,corner_chars", [
    (BorderStyle.LIGHT,   ("┌", "┐", "└", "┘")),
    (BorderStyle.HEAVY,   ("┏", "┓", "┗", "┛")),
    (BorderStyle.DOUBLE,  ("╔", "╗", "╚", "╝")),
    (BorderStyle.ROUNDED, ("╭", "╮", "╰", "╯")),
])
def test_box_render_corner_chars(border: BorderStyle, corner_chars: tuple[str, str, str, str]) -> None:
    """Each border style emits its specific four corner glyphs."""
    box = BoxShape(Rect(0, 0, 4, 3), border=border)
    cells = box.render()
    tl, tr, bl, br = corner_chars
    assert cells[(0, 0)] == tl
    assert cells[(3, 0)] == tr
    assert cells[(0, 2)] == bl
    assert cells[(3, 2)] == br


def test_box_render_no_border_only_text() -> None:
    box = BoxShape(Rect(0, 0, 5, 3), border=BorderStyle.NONE, text="hi")
    cells = box.render()
    # No border chars, just the text inset by 1.
    assert "│" not in cells.values()
    assert "─" not in cells.values()
    assert (1, 1) in cells  # text starts inside the inset
    assert cells[(1, 1)] == "h"
    assert cells[(2, 1)] == "i"


def test_box_render_braille_border_uses_braille_block() -> None:
    box = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.BRAILLE)
    cells = box.render()
    # Every emitted char must be in the braille range U+2800..U+28FF.
    assert cells, "braille border must produce cells"
    for ch in cells.values():
        assert "⠀" <= ch <= "⣿"


def test_box_render_fill_paints_interior() -> None:
    box = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.NONE,
                   fill=FillStyle.FULL)
    cells = box.render()
    # Every cell in the rect should be `█`.
    for col in range(4):
        for row in range(3):
            assert cells[(col, row)] == "█"


def test_box_hit_test_with_border() -> None:
    box = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.LIGHT)
    assert box.hit_test(0, 0)         # corner
    assert box.hit_test(2, 1)         # interior (border-bounded → treated as inside)
    assert not box.hit_test(-1, 0)
    assert not box.hit_test(4, 0)
    assert not box.hit_test(0, 3)


def test_box_hit_test_borderless_requires_text() -> None:
    """A borderless empty box has no clickable region."""
    empty = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.NONE)
    assert not empty.hit_test(2, 1)
    # ...but with text, the bound becomes clickable.
    with_text = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.NONE, text="x")
    assert with_text.hit_test(2, 1)


def test_box_resize_f_syncs_rect() -> None:
    """resize_f sets rect_f (sub-cell precision) and a synced integer rect."""
    box = BoxShape(Rect(0, 0, 1, 1), border=BorderStyle.BRAILLE)
    box.resize_f(2.5, 3.0, 8.75, 6.25)
    assert box.rect_f == (2.5, 3.0, 8.75, 6.25)
    # Integer rect derives from the floor of left/top.
    assert box.rect.left == 2
    assert box.rect.top == 3
    # Width/height span the floors inclusively.
    assert box.rect.right == 8   # floor(8.75)
    assert box.rect.bottom == 6  # floor(6.25)


def test_box_resize_f_normalizes_inverted_args() -> None:
    """resize_f must work regardless of which corner is passed first."""
    box = BoxShape(Rect(0, 0, 1, 1), border=BorderStyle.BRAILLE)
    box.resize_f(8.0, 6.0, 2.0, 3.0)  # right/bottom first
    assert box.rect_f == (2.0, 3.0, 8.0, 6.0)


@pytest.mark.parametrize("halign,expected_x", [
    # Box is rect(0, 0, 12, 3) with a 1-cell border inset, so content is
    # cols 1..10 (10 wide). For text "hi" (len 2):
    #   LEFT   → starts at col 1
    #   CENTER → (10 - 2) // 2 + 1 = 5
    #   RIGHT  → 10 - 2 + 1 = 9
    (HAlign.LEFT, 1),
    (HAlign.CENTER, 5),
    (HAlign.RIGHT, 9),
])
def test_box_text_halign(halign: HAlign, expected_x: int) -> None:
    box = BoxShape(Rect(0, 0, 12, 3), border=BorderStyle.LIGHT,
                   text="hi", halign=halign)
    cells = box.render()
    positions = [pos for pos, ch in cells.items() if ch == "h"]
    assert len(positions) == 1
    assert positions[0][0] == expected_x


# --- LineShape -----------------------------------------------------------

def test_line_recompute_straight_two_points() -> None:
    """Straight line between two collinear points has just start + end."""
    l = LineShape(Point(0, 0), Point(5, 0), line_style=LineStyle.ORTHOGONAL)
    assert l._joint_points == [Point(0, 0), Point(5, 0)]


def test_line_recompute_orthogonal_l_shape() -> None:
    """Orthogonal line with no side hints defaults to horizontal-then-vertical."""
    l = LineShape(Point(0, 0), Point(5, 3), line_style=LineStyle.ORTHOGONAL)
    assert l._joint_points == [Point(0, 0), Point(5, 0), Point(5, 3)]


def test_line_recompute_z_shape_when_both_sides_horizontal() -> None:
    """Two horizontal endpoints produce a Z-shape via two midpoint joints."""
    l = LineShape(Point(0, 0), Point(10, 4), line_style=LineStyle.ORTHOGONAL)
    l.start_side = "right"
    l.end_side = "left"
    l._recompute()
    # Z-shape: 4 points (start, mid-top, mid-bottom, end).
    assert len(l._joint_points) == 4


def test_line_bound_covers_all_joints() -> None:
    l = LineShape(Point(2, 1), Point(8, 5), line_style=LineStyle.ORTHOGONAL)
    b = l.bound
    assert b.left == 2
    assert b.top == 1
    assert b.right == 8
    assert b.bottom == 5


def test_line_render_orthogonal_corners_present() -> None:
    """The L-bend at (5, 0) → (5, 3) needs a corner glyph."""
    l = LineShape(Point(0, 0), Point(5, 3), line_style=LineStyle.ORTHOGONAL,
                  border=BorderStyle.LIGHT)
    cells = l.render()
    # The corner at (5, 0) must be a recognized box-drawing corner.
    assert (5, 0) in cells
    assert cells[(5, 0)] in {"┐", "┌", "┘", "└"}


def test_line_render_straight_ascii_uses_slope_chars() -> None:
    """ASCII straight line uses '-', '|', '/', '\\' for direction."""
    l = LineShape(Point(0, 0), Point(5, 0), line_style=LineStyle.STRAIGHT)
    cells = l.render(charset=CharSet.ASCII)
    # All horizontal: only `-` chars.
    assert set(cells.values()) == {"-"}


def test_line_render_braille_produces_braille_chars() -> None:
    l = LineShape(Point(0, 0), Point(5, 5), line_style=LineStyle.STRAIGHT,
                  border=BorderStyle.BRAILLE)
    cells = l.render()
    for ch in cells.values():
        assert "⠀" <= ch <= "⣿"


def test_line_move_translates_endpoints() -> None:
    l = LineShape(Point(2, 3), Point(8, 7))
    l.move(3, -1)
    assert l.start == Point(5, 2)
    assert l.end == Point(11, 6)


def test_line_hit_test_orthogonal_path() -> None:
    """hit_test must match every cell along the orthogonal path."""
    l = LineShape(Point(0, 0), Point(5, 3), line_style=LineStyle.ORTHOGONAL)
    # Horizontal segment from (0,0) to (5,0).
    for col in range(0, 6):
        assert l.hit_test(col, 0), f"miss at ({col}, 0)"
    # Vertical segment from (5,0) to (5,3).
    for row in range(0, 4):
        assert l.hit_test(5, row), f"miss at (5, {row})"
    # Off the path.
    assert not l.hit_test(2, 2)
