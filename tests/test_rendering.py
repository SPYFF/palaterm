"""Tests for FrameRenderer dirty-rect partial invalidation."""

from palaterm.canvas import Canvas
from palaterm.geometry import Rect
from palaterm.models import BorderStyle, BoxShape, CharSet
from palaterm.rendering import FrameRenderer
from rich.style import Style as RichStyle

VIEWPORT = Rect(0, 0, 40, 20)
BASE_STYLE = RichStyle.null()


def _make_canvas_with_two_boxes():
    canvas = Canvas()
    box_a = BoxShape(Rect(0, 0, 5, 3), border=BorderStyle.LIGHT)
    box_b = BoxShape(Rect(20, 10, 5, 3), border=BorderStyle.LIGHT)
    canvas.add_shape(box_a)
    canvas.add_shape(box_b)
    return canvas, box_a, box_b


def test_dirty_rect_updates_moved_shape():
    """After moving a shape and invalidating with dirty rect, new cells appear."""
    canvas, box_a, box_b = _make_canvas_with_two_boxes()
    renderer = FrameRenderer(canvas)

    # Build initial cache.
    cache = renderer._ensure_cache(VIEWPORT, None, BASE_STYLE, CharSet.UNICODE)
    cells = cache[0]
    assert (0, 0) in cells  # box_a top-left corner
    assert (20, 10) in cells  # box_b top-left corner

    # Move box_a to the right by 5.
    old_bound = box_a.bound
    box_a.move(5, 0)
    new_bound = box_a.bound

    # Dirty rect = union of old + new bounds.
    dirty = Rect(
        min(old_bound.left, new_bound.left),
        min(old_bound.top, new_bound.top),
        max(old_bound.right, new_bound.right)
        - min(old_bound.left, new_bound.left)
        + 1,
        max(old_bound.bottom, new_bound.bottom)
        - min(old_bound.top, new_bound.top)
        + 1,
    )
    renderer.invalidate(dirty)
    cache = renderer._ensure_cache(VIEWPORT, None, BASE_STYLE, CharSet.UNICODE)
    cells = cache[0]

    # Old position should be gone.
    assert (0, 0) not in cells
    # New position should be present.
    assert (5, 0) in cells
    # Unaffected shape should still be there.
    assert (20, 10) in cells


def test_dirty_rect_preserves_unaffected_cells():
    """Cells outside the dirty rect are not recomputed."""
    canvas, box_a, box_b = _make_canvas_with_two_boxes()
    renderer = FrameRenderer(canvas)

    # Build initial cache and grab a reference to box_b's cell.
    cache = renderer._ensure_cache(VIEWPORT, None, BASE_STYLE, CharSet.UNICODE)
    cells = cache[0]
    original_b_char = cells[(20, 10)]

    # Invalidate only box_a's region.
    renderer.invalidate(Rect(0, 0, 10, 5))
    cache = renderer._ensure_cache(VIEWPORT, None, BASE_STYLE, CharSet.UNICODE)
    cells = cache[0]

    # box_b's cell is unchanged (same dict, same value).
    assert cells[(20, 10)] == original_b_char


def test_full_invalidate_rebuilds_everything():
    """invalidate() with no args forces a full rebuild."""
    canvas, box_a, box_b = _make_canvas_with_two_boxes()
    renderer = FrameRenderer(canvas)

    cache1 = renderer._ensure_cache(VIEWPORT, None, BASE_STYLE, CharSet.UNICODE)
    renderer.invalidate()
    cache2 = renderer._ensure_cache(VIEWPORT, None, BASE_STYLE, CharSet.UNICODE)

    # Different cache tuple objects (full rebuild).
    assert cache1 is not cache2


def test_dirty_rect_no_op_without_existing_cache():
    """invalidate(rect) is a no-op when there's no existing cache."""
    canvas, box_a, box_b = _make_canvas_with_two_boxes()
    renderer = FrameRenderer(canvas)

    # No cache yet — dirty_rect should not crash or create partial state.
    renderer.invalidate(Rect(0, 0, 5, 3))
    cache = renderer._ensure_cache(VIEWPORT, None, BASE_STYLE, CharSet.UNICODE)
    cells = cache[0]
    # Full build happened — both shapes present.
    assert (0, 0) in cells
    assert (20, 10) in cells
