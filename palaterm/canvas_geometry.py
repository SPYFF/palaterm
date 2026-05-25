"""Pure functions for the union-rule virtual canvas.

The virtual canvas the widget exposes for scrolling is computed from two
independent contributors:

  * **Terminal floor**: a Rect centered on the origin sized to the
    high-water-mark of terminal dimensions this session. It only ever
    grows (a shrunk terminal is a no-op for the floor) and stays
    centered on `(0, 0)` for the lifetime of the session.

  * **Padded shape bounding box**: the tight bbox around every shape on
    the canvas, extended by `SHAPE_PADDING` cells on every side so the
    user has breathing room past the rightmost/bottommost shape.

The virtual canvas is the union of those two rectangles. It grows in any
of the four directions when shapes are placed past its edge and shrinks
back toward the floor when shapes move toward the origin.

Everything in this module is pure: no Textual imports, no hidden state.
The widget owns the terminal floor (session state) and calls these
helpers to compute extents and reanchor the scroll position across
recomputes.

See `docs/adr/0002-signed-coordinates-and-union-rule-canvas.md` for the
design rationale.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .geometry import Rect
from .models.base import Shape


SHAPE_PADDING = 5
"""Cells of breathing room around the shape bbox before it joins the union."""


@dataclass(frozen=True)
class CanvasExtent:
    """The Rect the user can pan into. ``rect`` is in shape coordinates."""

    rect: Rect


def grow_terminal_floor(prev: Rect | None, terminal_width: int, terminal_height: int) -> Rect:
    """Return the new terminal floor after a terminal-size observation.

    The floor is always centered on the origin and only ever grows: each
    dimension takes the max of the previous floor and the new terminal
    extent. When the terminal grows by an odd number of cells, the extra
    cell goes to the right/bottom side (convention; doesn't affect
    correctness).
    """
    new_w = max(terminal_width, prev.width if prev else 0)
    new_h = max(terminal_height, prev.height if prev else 0)
    # Center on origin: left = -floor(w/2), top = -floor(h/2). Odd cells
    # spill onto the right/bottom because Rect width = right - left + 1.
    left = -(new_w // 2)
    top = -(new_h // 2)
    return Rect(left, top, new_w, new_h)


def shape_bounding_box(shapes: Sequence[Shape]) -> Rect | None:
    """Tight bbox enclosing all shapes, or ``None`` if the list is empty."""
    if not shapes:
        return None
    bounds = [s.bound for s in shapes]
    left = min(b.left for b in bounds)
    top = min(b.top for b in bounds)
    right = max(b.right for b in bounds)
    bottom = max(b.bottom for b in bounds)
    return Rect(left, top, right - left + 1, bottom - top + 1)


def _pad(r: Rect, pad: int) -> Rect:
    return Rect(r.left - pad, r.top - pad, r.width + 2 * pad, r.height + 2 * pad)


def _union(a: Rect, b: Rect) -> Rect:
    left = min(a.left, b.left)
    top = min(a.top, b.top)
    right = max(a.right, b.right)
    bottom = max(a.bottom, b.bottom)
    return Rect(left, top, right - left + 1, bottom - top + 1)


def compute_virtual_extent(
    terminal_floor: Rect,
    shapes: Sequence[Shape],
    padding: int = SHAPE_PADDING,
) -> CanvasExtent:
    """Union the terminal floor with the padded shape bbox."""
    bbox = shape_bounding_box(shapes)
    if bbox is None:
        return CanvasExtent(terminal_floor)
    return CanvasExtent(_union(terminal_floor, _pad(bbox, padding)))


def anchor_scroll_after_resize(
    old_extent: Rect,
    new_extent: Rect,
    old_scroll_col: int,
    old_scroll_row: int,
) -> tuple[int, int]:
    """Translate a scroll offset across an extent change.

    Scroll offsets are widget-local (``0`` = the leftmost cell of the
    virtual canvas). When the extent's left/top edges shift between
    recomputes, the same shape coord under the viewport's top-left
    corresponds to a different scroll offset in the new extent. This
    function preserves the shape coord at the top-left.

    Returns the new ``(scroll_col, scroll_row)`` clamped to ``>= 0``;
    Textual clamps the upper bound itself when it sees the new
    virtual_size.
    """
    shape_col = old_scroll_col + old_extent.left
    shape_row = old_scroll_row + old_extent.top
    new_col = shape_col - new_extent.left
    new_row = shape_row - new_extent.top
    return max(0, new_col), max(0, new_row)


