"""Pure tests for the union-rule virtual canvas helpers.

These cover the rules pinned in
``docs/adr/0002-signed-coordinates-and-union-rule-canvas.md``: the
terminal floor grows-only, the virtual canvas is the union of floor
and padded shape bbox, and scroll re-anchoring across recomputes
preserves the shape coord at top-left.
"""

from __future__ import annotations

from palaterm.canvas_geometry import (
    SHAPE_PADDING,
    anchor_scroll_after_resize,
    compute_virtual_extent,
    grow_terminal_floor,
    shape_bounding_box,
)
from palaterm.geometry import Rect
from palaterm.models import BoxShape


def _box(left: int, top: int, w: int = 4, h: int = 3) -> BoxShape:
    return BoxShape(Rect(left, top, w, h))


# --- terminal floor ---------------------------------------------------


def test_terminal_floor_initial_is_centered_on_origin():
    floor = grow_terminal_floor(None, 80, 24)
    assert floor.width == 80
    assert floor.height == 24
    assert floor.left == -40
    assert floor.top == -12
    # right/bottom edge straddles origin
    assert floor.right == 39
    assert floor.bottom == 11


def test_terminal_floor_grows_when_terminal_grows():
    f1 = grow_terminal_floor(None, 80, 24)
    f2 = grow_terminal_floor(f1, 120, 30)
    assert f2.width == 120
    assert f2.height == 30
    assert f2.left == -60
    assert f2.top == -15


def test_terminal_floor_does_not_shrink_on_terminal_shrink():
    f1 = grow_terminal_floor(None, 120, 40)
    f2 = grow_terminal_floor(f1, 80, 25)
    # Floor stays at 120x40 — the shrink is a no-op.
    assert f2 == f1


def test_terminal_floor_grows_per_axis_independently():
    f1 = grow_terminal_floor(None, 80, 24)
    f2 = grow_terminal_floor(f1, 120, 20)  # wider but shorter
    assert f2.width == 120
    assert f2.height == 24  # height clamped at HWM


# --- shape bbox + virtual extent --------------------------------------


def test_extent_with_no_shapes_is_just_the_floor():
    floor = grow_terminal_floor(None, 80, 24)
    extent = compute_virtual_extent(floor, []).rect
    assert extent == floor


def test_extent_with_shape_inside_floor_unchanged():
    floor = grow_terminal_floor(None, 80, 24)
    # Shape sits well inside the floor and far enough from edges that
    # padding doesn't push past the floor either.
    shapes = [_box(0, 0, 4, 3)]
    extent = compute_virtual_extent(floor, shapes).rect
    assert extent == floor


def test_extent_with_shape_far_from_origin_extends_in_that_direction():
    floor = grow_terminal_floor(None, 80, 24)
    shapes = [_box(200, 0)]
    extent = compute_virtual_extent(floor, shapes).rect
    # Right edge moves out to enclose the shape + padding.
    assert extent.right >= 200 + 4 - 1 + SHAPE_PADDING
    # Left edge unchanged (still the floor's left).
    assert extent.left == floor.left


def test_extent_grows_in_all_four_directions():
    floor = grow_terminal_floor(None, 60, 20)
    shapes = [_box(-200, -100), _box(200, 100)]
    extent = compute_virtual_extent(floor, shapes).rect
    # Each direction extends past the floor.
    assert extent.left <= -200 - SHAPE_PADDING
    assert extent.top <= -100 - SHAPE_PADDING
    assert extent.right >= 200 + 4 - 1 + SHAPE_PADDING
    assert extent.bottom >= 100 + 3 - 1 + SHAPE_PADDING


def test_extent_shrinks_back_toward_floor_when_shapes_move_in():
    floor = grow_terminal_floor(None, 60, 20)
    shapes_far = [_box(200, 100)]
    extent_far = compute_virtual_extent(floor, shapes_far).rect
    shapes_in = [_box(0, 0)]
    extent_in = compute_virtual_extent(floor, shapes_in).rect
    assert extent_in.right < extent_far.right
    assert extent_in == floor  # back to just the floor


def test_extent_collapses_to_floor_when_all_shapes_deleted():
    floor = grow_terminal_floor(None, 60, 20)
    extent = compute_virtual_extent(floor, []).rect
    assert extent == floor


# --- scroll anchor translation ----------------------------------------


def test_anchor_unchanged_when_extent_unchanged():
    e = Rect(-40, -12, 80, 25)
    new_x, new_y = anchor_scroll_after_resize(e, e, 30, 5)
    assert (new_x, new_y) == (30, 5)


def test_anchor_shifts_when_extent_left_edge_moves():
    # Old extent: left = -40. New extent: left = -60. Same shape coord
    # at top-left means scroll_x must increase by 20 (the new extent
    # has more virtual columns to its left).
    old = Rect(-40, -12, 80, 25)
    new = Rect(-60, -12, 100, 25)
    new_x, new_y = anchor_scroll_after_resize(old, new, 30, 5)
    # shape_col = 30 + (-40) = -10. new_x = -10 - (-60) = 50.
    assert new_x == 50
    assert new_y == 5  # top edge unchanged


def test_anchor_shifts_when_extent_top_edge_moves():
    old = Rect(-40, -12, 80, 25)
    new = Rect(-40, -20, 80, 33)
    new_x, new_y = anchor_scroll_after_resize(old, new, 30, 5)
    assert new_x == 30
    # shape_row = 5 + (-12) = -7. new_y = -7 - (-20) = 13.
    assert new_y == 13


def test_anchor_clamps_negative_to_zero():
    # If shape coord at top-left is no longer within the new extent
    # (e.g., extent shrank from underneath us), clamp at 0 so Textual
    # doesn't reject the scroll.
    old = Rect(-100, -100, 200, 200)
    new = Rect(-40, -12, 80, 25)
    # shape_col = 5 + (-100) = -95. new_x = -95 - (-40) = -55. Clamp 0.
    new_x, new_y = anchor_scroll_after_resize(old, new, 5, 5)
    assert new_x == 0
    assert new_y == 0


# --- bbox helper ------------------------------------------------------


def test_bbox_returns_none_for_empty_list():
    assert shape_bounding_box([]) is None


def test_bbox_tightly_encloses_multiple_shapes():
    shapes = [_box(0, 0, 4, 3), _box(10, 5, 4, 3)]
    bbox = shape_bounding_box(shapes)
    assert bbox is not None
    assert bbox.left == 0
    assert bbox.top == 0
    assert bbox.right == 13
    assert bbox.bottom == 7


def test_bbox_handles_negative_coordinates():
    shapes = [_box(-10, -5, 4, 3), _box(2, 4, 4, 3)]
    bbox = shape_bounding_box(shapes)
    assert bbox is not None
    assert bbox.left == -10
    assert bbox.top == -5
    assert bbox.right == 5
    assert bbox.bottom == 6
