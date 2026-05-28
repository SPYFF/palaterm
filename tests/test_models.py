"""Tests for shape models and geometry primitives."""

from __future__ import annotations

import pytest
from palaterm.geometry import Point, Rect
from palaterm.models import (
    BorderStyle,
    BoxShape,
    CharSet,
    FillStyle,
    HAlign,
    LineShape,
    LineStyle,
)

# --- Rect ----------------------------------------------------------------


def test_rect_right_bottom_derived() -> None:
    r = Rect(2, 3, 5, 4)
    assert r.right == 6  # 2 + 5 - 1
    assert r.bottom == 6  # 3 + 4 - 1


def test_rect_from_points_normalizes_orientation() -> None:
    """from_points must produce the same Rect regardless of corner order."""
    p1 = Point(5, 7)
    p2 = Point(2, 3)
    r = Rect.from_points(p1, p2)
    assert r.left == 2
    assert r.top == 3
    assert r.width == 4  # cols 2..5 inclusive
    assert r.height == 5  # rows 3..7 inclusive
    # And the symmetric case yields the same Rect.
    assert Rect.from_points(p2, p1) == r


def test_rect_contains_inside_outside_and_boundary() -> None:
    r = Rect(0, 0, 4, 3)  # cols 0..3, rows 0..2
    assert r.contains(0, 0)  # top-left corner
    assert r.contains(3, 2)  # bottom-right corner
    assert r.contains(2, 1)  # interior
    assert not r.contains(-1, 0)  # left of left
    assert not r.contains(4, 0)  # right of right
    assert not r.contains(0, 3)  # below bottom


# --- BoxShape ------------------------------------------------------------


@pytest.mark.parametrize(
    "border,corner_chars",
    [
        (BorderStyle.LIGHT, ("┌", "┐", "└", "┘")),
        (BorderStyle.HEAVY, ("┏", "┓", "┗", "┛")),
        (BorderStyle.DOUBLE, ("╔", "╗", "╚", "╝")),
        (BorderStyle.ROUNDED, ("╭", "╮", "╰", "╯")),
    ],
)
def test_box_render_corner_chars(
    border: BorderStyle, corner_chars: tuple[str, str, str, str]
) -> None:
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
    box = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.NONE, fill=FillStyle.FULL)
    cells = box.render()
    # With half-block edges: corners are quadrants, edges are half-blocks,
    # interior is full block.
    assert cells[(0, 0)] == "▗"  # top-left corner
    assert cells[(3, 0)] == "▖"  # top-right corner
    assert cells[(1, 0)] == "▄"  # top edge
    assert cells[(0, 2)] == "▝"  # bottom-left corner
    assert cells[(3, 2)] == "▘"  # bottom-right corner
    assert cells[(1, 2)] == "▀"  # bottom edge
    assert cells[(0, 1)] == "▐"  # left edge
    assert cells[(3, 1)] == "▌"  # right edge
    assert cells[(1, 1)] == "█"  # interior
    assert cells[(2, 1)] == "█"  # interior


def test_box_render_fill_full_small_uniform() -> None:
    """A borderless FULL fill box smaller than 3x3 uses uniform fill."""
    box = BoxShape(Rect(0, 0, 2, 2), border=BorderStyle.NONE, fill=FillStyle.FULL)
    cells = box.render()
    for col in range(2):
        for row in range(2):
            assert cells[(col, row)] == "█"


def test_box_render_fill_medium_uniform() -> None:
    """A borderless MEDIUM fill box uses uniform fill (no half-block edges)."""
    box = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.NONE, fill=FillStyle.MEDIUM)
    cells = box.render()
    for col in range(4):
        for row in range(3):
            assert cells[(col, row)] == "▒"


def test_box_render_fill_bordered_stays_uniform() -> None:
    """A bordered box with FULL fill uses uniform fill inside the border."""
    box = BoxShape(Rect(0, 0, 5, 4), border=BorderStyle.LIGHT, fill=FillStyle.FULL)
    cells = box.render()
    # Interior cells should be uniform full block
    assert cells[(1, 1)] == "█"
    assert cells[(2, 1)] == "█"
    assert cells[(3, 1)] == "█"


def test_box_hit_test_with_border() -> None:
    box = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.LIGHT)
    assert box.hit_test(0, 0)  # corner
    assert box.hit_test(2, 1)  # interior (border-bounded → treated as inside)
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


def test_box_hit_test_borderless_with_fill_is_clickable() -> None:
    """Fill makes a borderless, textless box clickable across its bound."""
    occluder = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.NONE, fill=FillStyle.SPACE)
    assert occluder.hit_test(2, 1)
    pattern = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.NONE, fill=FillStyle.FULL)
    assert pattern.hit_test(0, 0)
    assert pattern.hit_test(3, 2)
    assert not pattern.hit_test(4, 0)


def test_box_resize_f_syncs_rect() -> None:
    """resize_f sets rect_f (sub-cell precision) and a synced integer rect."""
    box = BoxShape(Rect(0, 0, 1, 1), border=BorderStyle.BRAILLE)
    box.resize_f(2.5, 3.0, 8.75, 6.25)
    assert box.rect_f == (2.5, 3.0, 8.75, 6.25)
    # Integer rect derives from the floor of left/top.
    assert box.rect.left == 2
    assert box.rect.top == 3
    # Width/height span the floors inclusively.
    assert box.rect.right == 8  # floor(8.75)
    assert box.rect.bottom == 6  # floor(6.25)


def test_box_resize_f_normalizes_inverted_args() -> None:
    """resize_f must work regardless of which corner is passed first."""
    box = BoxShape(Rect(0, 0, 1, 1), border=BorderStyle.BRAILLE)
    box.resize_f(8.0, 6.0, 2.0, 3.0)  # right/bottom first
    assert box.rect_f == (2.0, 3.0, 8.0, 6.0)


@pytest.mark.parametrize(
    "halign,expected_x",
    [
        # Box is rect(0, 0, 12, 3) with a 1-cell border inset, so content is
        # cols 1..10 (10 wide). For text "hi" (len 2):
        #   LEFT   → starts at col 1
        #   CENTER → (10 - 2) // 2 + 1 = 5
        #   RIGHT  → 10 - 2 + 1 = 9
        (HAlign.LEFT, 1),
        (HAlign.CENTER, 5),
        (HAlign.RIGHT, 9),
    ],
)
def test_box_text_halign(halign: HAlign, expected_x: int) -> None:
    box = BoxShape(
        Rect(0, 0, 12, 3), border=BorderStyle.LIGHT, text="hi", halign=halign
    )
    cells = box.render()
    positions = [pos for pos, ch in cells.items() if ch == "h"]
    assert len(positions) == 1
    assert positions[0][0] == expected_x


# --- LineShape -----------------------------------------------------------


def test_line_recompute_straight_two_points() -> None:
    """Straight line between two collinear points has just start + end."""
    ln = LineShape(Point(0, 0), Point(5, 0), line_style=LineStyle.ORTHOGONAL)
    assert ln._joint_points == [Point(0, 0), Point(5, 0)]


def test_line_recompute_orthogonal_l_shape() -> None:
    """Orthogonal line with no side hints defaults to horizontal-then-vertical."""
    ln = LineShape(Point(0, 0), Point(5, 3), line_style=LineStyle.ORTHOGONAL)
    assert ln._joint_points == [Point(0, 0), Point(5, 0), Point(5, 3)]


def test_line_recompute_z_shape_when_both_sides_horizontal() -> None:
    """Two horizontal endpoints produce a Z-shape via two midpoint joints."""
    ln = LineShape(Point(0, 0), Point(10, 4), line_style=LineStyle.ORTHOGONAL)
    ln.start_side = "right"
    ln.end_side = "left"
    ln._recompute()
    # Z-shape: 4 points (start, mid-top, mid-bottom, end).
    assert len(ln._joint_points) == 4


def test_line_bound_covers_all_joints() -> None:
    ln = LineShape(Point(2, 1), Point(8, 5), line_style=LineStyle.ORTHOGONAL)
    b = ln.bound
    assert b.left == 2
    assert b.top == 1
    assert b.right == 8
    assert b.bottom == 5


def test_line_render_orthogonal_corners_present() -> None:
    """The L-bend at (5, 0) → (5, 3) needs a corner glyph."""
    ln = LineShape(
        Point(0, 0),
        Point(5, 3),
        line_style=LineStyle.ORTHOGONAL,
        border=BorderStyle.LIGHT,
    )
    cells = ln.render()
    # The corner at (5, 0) must be a recognized box-drawing corner.
    assert (5, 0) in cells
    assert cells[(5, 0)] in {"┐", "┌", "┘", "└"}


def test_line_render_straight_ascii_uses_slope_chars() -> None:
    """ASCII straight line uses '-', '|', '/', '\\' for direction."""
    ln = LineShape(Point(0, 0), Point(5, 0), line_style=LineStyle.STRAIGHT)
    cells = ln.render(charset=CharSet.ASCII)
    # All horizontal: only `-` chars.
    assert set(cells.values()) == {"-"}


def test_line_render_braille_produces_braille_chars() -> None:
    ln = LineShape(
        Point(0, 0),
        Point(5, 5),
        line_style=LineStyle.STRAIGHT,
        border=BorderStyle.BRAILLE,
    )
    cells = ln.render()
    for ch in cells.values():
        assert "⠀" <= ch <= "⣿"


def test_line_move_translates_endpoints() -> None:
    ln = LineShape(Point(2, 3), Point(8, 7))
    ln.move(3, -1)
    assert ln.start == Point(5, 2)
    assert ln.end == Point(11, 6)


def test_line_hit_test_orthogonal_path() -> None:
    """hit_test must match every cell along the orthogonal path."""
    ln = LineShape(Point(0, 0), Point(5, 3), line_style=LineStyle.ORTHOGONAL)
    # Horizontal segment from (0,0) to (5,0).
    for col in range(0, 6):
        assert ln.hit_test(col, 0), f"miss at ({col}, 0)"
    # Vertical segment from (5,0) to (5,3).
    for row in range(0, 4):
        assert ln.hit_test(5, row), f"miss at (5, {row})"
    # Off the path.
    assert not ln.hit_test(2, 2)


# --- Line edge-drag (joint state, edge_at, move_edge, move_anchor) ---


def test_line_edge_at_returns_index_for_interior_cells() -> None:
    """L-shape line: each segment's interior cells map to its edge index."""
    ln = LineShape(Point(0, 0), Point(5, 3), line_style=LineStyle.ORTHOGONAL)
    # Joints: (0,0) -> (5,0) -> (5,3)
    # Edge 0 interior: (1..4, 0). Edge 1 interior: (5, 1..2).
    assert ln.edge_at(2, 0) == 0
    assert ln.edge_at(5, 2) == 1
    # Joint (corner) returns None.
    assert ln.edge_at(5, 0) is None
    # Endpoints return None.
    assert ln.edge_at(0, 0) is None
    assert ln.edge_at(5, 3) is None
    # Off the path.
    assert ln.edge_at(2, 2) is None


def test_line_joint_at_excludes_endpoints() -> None:
    ln = LineShape(Point(0, 0), Point(5, 3), line_style=LineStyle.ORTHOGONAL)
    assert ln.joint_at(5, 0) == 1
    assert ln.joint_at(0, 0) is None
    assert ln.joint_at(5, 3) is None


def test_line_edge_at_returns_none_for_single_segment() -> None:
    ln = LineShape(Point(0, 0), Point(5, 0), line_style=LineStyle.ORTHOGONAL)
    assert ln.edge_at(2, 0) is None


def test_line_move_edge_middle_segment_translates_perpendicular() -> None:
    """Z-shape: dragging middle vertical edge horizontally slides it."""
    ln = LineShape(Point(0, 0), Point(10, 4), line_style=LineStyle.ORTHOGONAL)
    ln.start_side = "left"
    ln.end_side = "left"
    ln._recompute()
    # Z: (0,0) -> (5,0) -> (5,4) -> (10,4); middle edge index 1 is vertical.
    assert ln.joint_points == [Point(0, 0), Point(5, 0), Point(5, 4), Point(10, 4)]
    ln.move_edge(1, Point(7, 2))
    assert ln.routing.edges_modified
    assert ln.joint_points == [Point(0, 0), Point(7, 0), Point(7, 4), Point(10, 4)]


def test_line_move_edge_first_edge_inserts_corner_joint() -> None:
    """First edge drag introduces a new joint at the anchored endpoint."""
    ln = LineShape(Point(0, 0), Point(5, 3), line_style=LineStyle.ORTHOGONAL)
    # L: (0,0) -> (5,0) -> (5,3). Edge 0 horizontal.
    ln.move_edge(0, Point(0, 2))
    assert ln.routing.edges_modified
    # Anchor (0,0) stays, new corner at (0,2), far end of edge 0 slides to (5,2).
    assert ln.joint_points[0] == Point(0, 0)
    assert ln.joint_points[-1] == Point(5, 3)
    assert len(ln.joint_points) >= 3


def test_line_move_anchor_unedited_rederives_path() -> None:
    """An unedited line still recomputes from start/end on anchor move."""
    ln = LineShape(Point(0, 0), Point(5, 3), line_style=LineStyle.ORTHOGONAL)
    ln.move_anchor("end", Point(8, 5))
    assert ln.end == Point(8, 5)
    assert not ln.routing.edges_modified


def test_line_move_anchor_edited_keeps_custom_routing() -> None:
    """Once edited, anchor move slides endpoint without resetting the path."""
    ln = LineShape(Point(0, 0), Point(10, 4), line_style=LineStyle.ORTHOGONAL)
    ln.start_side = "left"
    ln.end_side = "left"
    ln._recompute()
    ln.move_edge(1, Point(7, 2))
    custom_joint_count = len(ln.joint_points)
    ln.move_anchor("end", Point(11, 4))
    assert ln.end == Point(11, 4)
    assert len(ln.joint_points) == custom_joint_count
    assert ln.routing.edges_modified


def test_line_clear_custom_routing_resets_state() -> None:
    ln = LineShape(Point(0, 0), Point(5, 3), line_style=LineStyle.ORTHOGONAL)
    ln.move_edge(0, Point(0, 2))
    assert ln.routing.edges_modified
    ln.clear_custom_routing()
    assert not ln.routing.edges_modified
    assert ln.joint_points == [Point(0, 0), Point(5, 0), Point(5, 3)]


def test_line_move_edge_collapses_joints_aligned_with_endpoint() -> None:
    """Dragging the middle edge to align with an endpoint reduces to L-shape."""
    ln = LineShape(Point(0, 0), Point(10, 4), line_style=LineStyle.ORTHOGONAL)
    ln.start_side = "top"
    ln.end_side = "bottom"
    ln._recompute()
    # Z: (0,0) -> (0,2) -> (10,2) -> (10,4); middle horizontal edge index 1.
    assert len(ln.joint_points) == 4
    # Drag middle edge up to the start's row.
    ln.move_edge(1, Point(5, 0))
    # Should collapse to L-shape: (0,0) -> (10,0) -> (10,4).
    assert ln.joint_points == [Point(0, 0), Point(10, 0), Point(10, 4)]


def test_line_follow_anchor_drops_user_edge_edits() -> None:
    """follow_anchor wipes edge customizations and re-derives from sides."""
    ln = LineShape(Point(0, 0), Point(10, 4), line_style=LineStyle.ORTHOGONAL)
    ln.start_side = "left"
    ln.end_side = "left"
    ln._recompute()
    ln.move_edge(1, Point(7, 2))
    assert ln.routing.edges_modified
    edited_joints = list(ln.joint_points)
    ln.follow_anchor("end", Point(11, 4))
    assert not ln.routing.edges_modified
    assert ln.end == Point(11, 4)
    # Joints come from _recompute using the kept side hints — Z-shape, not the
    # user's tweaked routing.
    assert ln.joint_points != edited_joints
    mid_col = (0 + 11) // 2
    assert ln.joint_points == [
        Point(0, 0),
        Point(mid_col, 0),
        Point(mid_col, 4),
        Point(11, 4),
    ]


def test_line_follow_anchor_unedited_just_recomputes() -> None:
    """No-op on edges_modified when there were no user edits to drop."""
    ln = LineShape(Point(0, 0), Point(5, 3), line_style=LineStyle.ORTHOGONAL)
    ln.follow_anchor("end", Point(7, 2))
    assert ln.end == Point(7, 2)
    assert not ln.routing.edges_modified


def test_line_move_translates_authoritative_joints() -> None:
    """Move on an edge-edited line shifts every stored joint by the delta."""
    ln = LineShape(Point(0, 0), Point(10, 4), line_style=LineStyle.ORTHOGONAL)
    ln.start_side = "left"
    ln.end_side = "left"
    ln._recompute()
    ln.move_edge(1, Point(7, 2))
    before = list(ln.joint_points)
    ln.move(3, 1)
    after = list(ln.joint_points)
    assert all(b.col + 3 == a.col and b.row + 1 == a.row for b, a in zip(before, after))


# --- Render cache tests ---


def test_render_cache_returns_same_object_on_repeated_call() -> None:
    """Calling render() twice without mutation returns the same dict object."""
    box = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.LIGHT)
    r1 = box.render(CharSet.UNICODE)
    r2 = box.render(CharSet.UNICODE)
    assert r1 is r2


def test_render_cache_invalidated_by_move() -> None:
    """After move(), render() returns a fresh dict."""
    box = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.LIGHT)
    r1 = box.render(CharSet.UNICODE)
    box.move(1, 0)
    r2 = box.render(CharSet.UNICODE)
    assert r1 is not r2


def test_render_cache_invalidated_by_charset_change() -> None:
    """Calling render() with a different charset returns a fresh dict."""
    box = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.LIGHT)
    r1 = box.render(CharSet.UNICODE)
    r2 = box.render(CharSet.ASCII)
    assert r1 is not r2


def test_render_cache_invalidated_by_attribute_change() -> None:
    """Setting a tracked attribute invalidates the cache."""
    box = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.LIGHT)
    r1 = box.render(CharSet.UNICODE)
    box.border = BorderStyle.HEAVY
    r2 = box.render(CharSet.UNICODE)
    assert r1 is not r2


def test_line_render_cache() -> None:
    """LineShape render cache works the same way."""
    ln = LineShape(Point(0, 0), Point(5, 0), line_style=LineStyle.ORTHOGONAL)
    r1 = ln.render(CharSet.UNICODE)
    r2 = ln.render(CharSet.UNICODE)
    assert r1 is r2
    ln.move(1, 0)
    r3 = ln.render(CharSet.UNICODE)
    assert r1 is not r3
