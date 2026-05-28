"""Canvas widget: handles mouse events and delegates rendering."""

from __future__ import annotations

import math
import time

from textual.events import MouseDown, MouseMove, MouseUp, Resize
from textual.geometry import Region, Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from ..canvas import Canvas
from ..canvas_geometry import (
    anchor_scroll_after_resize,
    compute_virtual_extent,
    grow_terminal_floor,
)
from ..commands import CommandHistory
from ..geometry import Rect
from ..models import BoxShape, CharSet
from ..rendering import FrameRenderer
from ..tools import DrawTool, SelectTool, TextTool
from ..tools.gestures import (
    EdgeDragCommit,
    GestureCommit,
    MoveCommit,
    ResizeCommit,
)
from .modals import TextEditModal

# Fallback floor used before the first ``Resize`` event lands. Centered on
# origin so the initial scroll position lines up with shape (0, 0).
_FALLBACK_FLOOR = Rect(-40, -12, 80, 25)


class CanvasWidget(ScrollView, can_focus=True):
    """The drawing canvas widget."""

    class ShapeCreated(Message):
        def __init__(self, shape) -> None:
            super().__init__()
            self.shape = shape

    class ShapeMoved(Message):
        def __init__(self, shapes, dcol: int, drow: int) -> None:
            super().__init__()
            self.shapes = shapes
            self.dcol = dcol
            self.drow = drow

    class ShapeResized(Message):
        def __init__(self, shape, old_attrs: dict) -> None:
            super().__init__()
            self.shape = shape
            self.old_attrs = old_attrs

    class LineEdgeMoved(Message):
        def __init__(self, commit: EdgeDragCommit) -> None:
            super().__init__()
            self.commit = commit

    DEFAULT_CSS = """
    CanvasWidget {
        width: 1fr;
        height: 1fr;
        overflow: scroll;
        color: $text;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.canvas = Canvas()
        self.tool: DrawTool | SelectTool = SelectTool()
        self.charset: CharSet = CharSet.UNICODE
        self._mouse_down = False
        self._editing: bool = False
        self._renderer = FrameRenderer(self.canvas)
        self._last_click_time: float = 0
        self._last_click_pos: tuple[int, int] = (0, 0)
        # Terminal floor: high-water-mark of terminal dims this session,
        # centered on origin. Fallback until the first Resize lands.
        self._terminal_floor: Rect = _FALLBACK_FLOOR
        # Current virtual canvas extent (union of floor + padded bbox).
        # Drives scroll-coord conversion; set by _update_virtual_size().
        self._extent: Rect = _FALLBACK_FLOOR
        self._update_virtual_size()

    def on_mount(self) -> None:
        super().on_mount()
        # Center viewport on origin: scroll so shape (0, 0) lands at the
        # top-left + half the viewport. With the fallback floor centered
        # on origin, scrolling to (-extent.left, -extent.top) puts the
        # virtual canvas's top-left at the viewport's top-left, which
        # contains origin near the center because the floor is centered.
        self._scroll_to_shape_center()

    def attach_history(self, history: CommandHistory) -> None:
        """Subscribe to the history's change hook for shape-side recompute.

        The widget also recomputes on terminal resize, but that's driven
        by ``on_resize`` rather than the history.
        """
        history.on_change = self._on_history_change

    def _on_history_change(self) -> None:
        self._update_virtual_size_preserving_anchor()

    @property
    def _scroll_col(self) -> int:
        return int(self.scroll_x) + self._extent.left

    @property
    def _scroll_row(self) -> int:
        return int(self.scroll_y) + self._extent.top

    def _update_virtual_size(self) -> None:
        """Recompute the extent and virtual_size from current state."""
        extent = compute_virtual_extent(self._terminal_floor, self.canvas.shapes).rect
        self._extent = extent
        self.virtual_size = Size(extent.width, extent.height)

    def _update_virtual_size_preserving_anchor(self) -> None:
        """Recompute the extent, then re-anchor scroll to keep
        the top-left shape coord stable."""
        old_extent = self._extent
        old_scroll_x = int(self.scroll_x)
        old_scroll_y = int(self.scroll_y)
        self._update_virtual_size()
        new_x, new_y = anchor_scroll_after_resize(
            old_extent,
            self._extent,
            old_scroll_x,
            old_scroll_y,
        )
        if (new_x, new_y) != (old_scroll_x, old_scroll_y):
            self.scroll_to(new_x, new_y, animate=False)

    def on_resize(self, event: Resize) -> None:
        """Grow the terminal floor when the terminal grows; never shrink."""
        # ``size`` here is the widget's allocated size, which is what
        # determines how much room there is to draw. Treat it as the
        # contributor to the floor.
        new_floor = grow_terminal_floor(
            self._terminal_floor,
            event.size.width,
            event.size.height,
        )
        if new_floor != self._terminal_floor:
            self._terminal_floor = new_floor
            # Floor change keeps origin centered, so the shape coord at
            # top-left changes only when the new floor's left/top edges
            # differ from the prior extent's. anchor_scroll_after_resize
            # handles that.
            self._update_virtual_size_preserving_anchor()

    def _scroll_to_shape_center(self) -> None:
        """Scroll so shape (0, 0) lands at the viewport's center."""
        # scroll position that puts shape (0, 0) at viewport top-left:
        zero_x = -self._extent.left
        zero_y = -self._extent.top
        # offset back by half the viewport to put origin at center
        size = self.scrollable_content_region
        half_w = (size.width or self.size.width) // 2
        half_h = (size.height or self.size.height) // 2
        self.scroll_to(max(0, zero_x - half_w), max(0, zero_y - half_h), animate=False)

    def scroll_to_shape_bbox_center(self) -> None:
        """Scroll the viewport to the center of the shape bounding box.

        Used after file-open. Falls back to scrolling to origin when the
        canvas is empty.
        """
        from ..canvas_geometry import shape_bounding_box

        bbox = shape_bounding_box(self.canvas.shapes)
        if bbox is None:
            self._scroll_to_shape_center()
            return
        cx = bbox.left + bbox.width // 2
        cy = bbox.top + bbox.height // 2
        self.scroll_to_shape(cx, cy, center=True)

    def scroll_to_shape(self, col: int, row: int, *, center: bool = True) -> None:
        """Scroll the viewport so shape ``(col, row)`` is centered (or at top-left)."""
        x = col - self._extent.left
        y = row - self._extent.top
        if center:
            size = self.scrollable_content_region
            half_w = (size.width or self.size.width) // 2
            half_h = (size.height or self.size.height) // 2
            x -= half_w
            y -= half_h
        self.scroll_to(max(0, x), max(0, y), animate=False)

    def _to_canvas_coords(self, x: int, y: int) -> tuple[int, int]:
        return x + self._scroll_col, y + self._scroll_row

    def _to_canvas_coords_f(
        self, pointer_x: float, pointer_y: float
    ) -> tuple[int, int]:
        """Floor pointer floats to the cell they fall into.

        Must use floor (not round) so that sub-cell offsets — which are derived
        from the same floor — describe a position *inside* the returned cell
        rather than a phantom position in the next cell over.
        """
        return math.floor(pointer_x) + self._scroll_col, math.floor(
            pointer_y
        ) + self._scroll_row

    def open_text_editor(self, shape: BoxShape) -> None:
        self._editing = True

        def on_dismiss(result: str | None) -> None:
            self._editing = False
            if result is not None and result.strip():
                shape.text = result
                lines = result.split("\n")
                w = max((len(ln) for ln in lines), default=0) + 2
                h = len(lines) + 2
                r = shape.rect
                shape.rect = Rect(
                    r.left, r.top, max(r.width, w, 3), max(r.height, h, 3)
                )
            else:
                if not shape.text:
                    self.canvas.remove_shape(shape)
            self.refresh()

        self.app.push_screen(TextEditModal(shape.text), on_dismiss)

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        canvas_col = scroll_x + self._extent.left
        canvas_row = scroll_y + self._extent.top
        region = self.scrollable_content_region
        viewport = Rect(
            canvas_col,
            canvas_row,
            region.width or self.size.width,
            region.height or self.size.height,
        )
        return self._renderer.render_line(
            y, viewport, self.tool, self.rich_style, self.charset
        )

    # ---- Refresh API ----------------------------------------------------
    #
    # ``refresh()``                — full repaint (default, used everywhere
    #                                outside the mouse hot path).
    # ``refresh_rect(canvas_rect)``— repaint only screen lines covering
    #                                ``canvas_rect``. Textual's StylesCache
    #                                serves cached strips for every other row.
    #
    # During mouse drags we want the partial path. The trick is computing the
    # rect: a moved shape needs *both* its old and new position repainted.
    # The pattern at the call sites is:
    #
    #     before = self._tool_dirty_bounds()
    #     self.tool.on_mouse_drag(...)            # mutates tool/shape state
    #     self._refresh_dirty_since(before)
    #
    # ``_tool_dirty_bounds()`` collects every rect the active tool is
    # currently touching; the union of before-snapshot and after-snapshot
    # covers every cell that may need a repaint.

    def refresh(self, *args, **kwargs) -> None:
        self._renderer.invalidate()
        super().refresh(*args, **kwargs)

    def refresh_rect(self, canvas_rect: Rect) -> None:
        """Repaint only the screen lines covering ``canvas_rect``."""
        region = self._canvas_to_screen_region(canvas_rect)
        if region is None:
            # Off-screen or zero-sized widget: full refresh is safe and cheap
            # (we already had to invalidate the cache anyway).
            self.refresh()
            return
        self._renderer.invalidate(canvas_rect)
        super().refresh(region)

    def _canvas_to_screen_region(self, canvas_rect: Rect) -> Region | None:
        """Translate a canvas-coords rect to a widget-relative ``Region``.

        Returns ``None`` if the rect lies fully outside the viewport (in which
        case there's nothing to repaint partially).
        """
        size = self.size
        if size.width == 0 or size.height == 0:
            return None
        # Translate canvas → screen coordinates.
        x = canvas_rect.left - self._scroll_col
        y = canvas_rect.top - self._scroll_row
        w, h = canvas_rect.width, canvas_rect.height
        # Clip the left/top edges that fall before the viewport origin.
        if x < 0:
            w += x
            x = 0
        if y < 0:
            h += y
            y = 0
        # Fully off-screen?
        if x >= size.width or y >= size.height or w <= 0 or h <= 0:
            return None
        # Clip the right/bottom edges to the viewport.
        w = min(w, size.width - x)
        h = min(h, size.height - y)
        return Region(x, y, w, h)

    def _refresh_dirty_since(self, before_bounds: list[Rect]) -> None:
        """Repaint the union of ``before_bounds`` and current tool bounds.

        See the section header above for the snapshot-before/snapshot-after
        pattern this completes.
        """
        rect = self._union(before_bounds + self._tool_dirty_bounds())
        if rect is None:
            self.refresh()
        else:
            self.refresh_rect(rect)

    @staticmethod
    def _union(rects: list[Rect]) -> Rect | None:
        if not rects:
            return None
        left = min(r.left for r in rects)
        top = min(r.top for r in rects)
        right = max(r.right for r in rects)
        bottom = max(r.bottom for r in rects)
        return Rect(left, top, right - left + 1, bottom - top + 1)

    def _tool_dirty_bounds(self) -> list[Rect]:
        """Bounds of every region the active tool is currently painting.

        Snapshot this *before* a tool callback (mouse down/drag/up); a second
        snapshot taken after the callback, unioned with the first, covers
        every cell whose appearance may have changed.
        """
        bounds: list[Rect] = []
        tool = self.tool

        # Draw tools paint an in-progress shape (and a snap-target highlight).
        if isinstance(tool, DrawTool) and tool._shape is not None:
            bounds.append(tool._shape.bound)
            snap = getattr(tool, "snap_target", None)
            if snap is not None:
                bounds.extend(self._snap_target_bounds(snap))

        # Select tools paint several overlays at once.
        if isinstance(tool, SelectTool):
            # The selection highlight + handles.
            bounds.extend(s.bound for s in tool.selected)
            # Lines connected to selected shapes follow them, so they redraw
            # too even when not selected themselves.
            bounds.extend(self._connected_line_bounds({s.id for s in tool.selected}))
            # Snap-target highlight when dragging a line endpoint onto a box.
            if tool.snap_target is not None:
                bounds.extend(self._snap_target_bounds(tool.snap_target))
            # Whatever the live gesture is currently painting (resize bounds,
            # edge-drag line bounds, rubber band, …).
            bounds.extend(tool.gesture_dirty_bounds(self.canvas))
            # Edge-hover highlight: the hovered line's bound covers it.
            if tool.hover_edge_line is not None:
                bounds.append(tool.hover_edge_line.bound)

        return bounds

    def _snap_target_bounds(self, snap) -> list[Rect]:
        target = next((s for s in self.canvas.shapes if s.id == snap.target_id), None)
        return [target.bound] if target is not None else []

    def _connected_line_bounds(self, shape_ids: set[str]) -> list[Rect]:
        bounds: list[Rect] = []
        for shape_id in shape_ids:
            for conn in self.canvas.connector_mgr.get_by_target(shape_id):
                line = next(
                    (sh for sh in self.canvas.shapes if sh.id == conn.line_id), None
                )
                if line is not None:
                    bounds.append(line.bound)
        return bounds

    def on_mouse_down(self, event: MouseDown) -> None:
        if self._editing:
            return
        col, row = self._to_canvas_coords_f(event.pointer_x, event.pointer_y)
        px = event.pointer_x + self._scroll_col
        py = event.pointer_y + self._scroll_row
        now = time.monotonic()
        if isinstance(self.tool, SelectTool) and event.button == 1:
            hit = self.canvas.shape_at(col, row)
            if (
                hit
                and isinstance(hit, BoxShape)
                and now - self._last_click_time < 0.4
                and self._last_click_pos == (col, row)
            ):
                self.tool.selected = [hit]
                self.open_text_editor(hit)
                self._last_click_time = 0
                return
        self._last_click_time = now
        self._last_click_pos = (col, row)
        self.capture_mouse()
        self._mouse_down = True
        before = self._tool_dirty_bounds()
        if isinstance(self.tool, SelectTool):
            self.tool.on_mouse_down(
                col,
                row,
                self.canvas,
                ctrl=event.ctrl,
                alt=event.meta,
                pointer_x=px,
                pointer_y=py,
            )
        else:
            self.tool.on_mouse_down(col, row, self.canvas, pointer_x=px, pointer_y=py)
        self._refresh_dirty_since(before)

    def on_mouse_move(self, event: MouseMove) -> None:
        if self._editing:
            return
        col, row = self._to_canvas_coords_f(event.pointer_x, event.pointer_y)
        if self._mouse_down:
            px = event.pointer_x + self._scroll_col
            py = event.pointer_y + self._scroll_row
            before = self._tool_dirty_bounds()
            self.tool.on_mouse_drag(col, row, self.canvas, pointer_x=px, pointer_y=py)
            self._refresh_dirty_since(before)
        elif isinstance(self.tool, SelectTool):
            # Hover swap: only the old + new hovered shapes change appearance.
            old = self.tool.hover_shape
            new = self.canvas.shape_at(col, row)
            old_edge_line = self.tool.hover_edge_line
            old_edge_index = self.tool.hover_edge_index
            old_edge_whole = self.tool.hover_edge_whole
            px = event.pointer_x + self._scroll_col
            py = event.pointer_y + self._scroll_row
            self.tool.hover_shape = new
            self.tool.update_hover(col, row, pointer_x=px, pointer_y=py)
            self._update_pointer_for_hover()
            edge_changed = (
                old_edge_line is not self.tool.hover_edge_line
                or old_edge_index != self.tool.hover_edge_index
                or old_edge_whole != self.tool.hover_edge_whole
            )
            if new != old or edge_changed:
                dirty = [s.bound for s in (old, new) if s is not None]
                if old_edge_line is not None:
                    dirty.append(old_edge_line.bound)
                if self.tool.hover_edge_line is not None:
                    dirty.append(self.tool.hover_edge_line.bound)
                rect = self._union(dirty)
                if rect is None:
                    self.refresh()
                else:
                    self.refresh_rect(rect)

    def _update_pointer_for_hover(self) -> None:
        from ..tools import Handle

        if not isinstance(self.tool, SelectTool):
            self.styles.pointer = "default"
            return

        h = self.tool.hover_handle
        if h is not None:
            _HANDLE_CURSORS = {
                Handle.TOP_LEFT: "nwse-resize",
                Handle.BOT_RIGHT: "nwse-resize",
                Handle.TOP_RIGHT: "nesw-resize",
                Handle.BOT_LEFT: "nesw-resize",
                Handle.TOP_MID: "ns-resize",
                Handle.BOT_MID: "ns-resize",
                Handle.MID_LEFT: "ew-resize",
                Handle.MID_RIGHT: "ew-resize",
                Handle.LINE_START: "move",
                Handle.LINE_END: "move",
            }
            self.styles.pointer = _HANDLE_CURSORS.get(h, "default")
        elif self.tool.hover_edge_whole:
            self.styles.pointer = "move"
        elif (
            self.tool.hover_edge_line is not None
            and self.tool.hover_edge_index is not None
        ):
            line = self.tool.hover_edge_line
            idx = self.tool.hover_edge_index
            if line.edge_is_horizontal(idx):
                self.styles.pointer = "ns-resize"
            else:
                self.styles.pointer = "ew-resize"
        elif self.tool.hover_shape and self.tool.hover_shape in self.tool.selected:
            self.styles.pointer = "move"
        else:
            self.styles.pointer = "default"

    def on_mouse_up(self, event: MouseUp) -> None:
        if self._editing:
            return
        self.release_mouse()
        self._mouse_down = False
        col, row = self._to_canvas_coords_f(event.pointer_x, event.pointer_y)
        px = event.pointer_x + self._scroll_col
        py = event.pointer_y + self._scroll_row
        before = self._tool_dirty_bounds()
        if isinstance(self.tool, SelectTool):
            commit = self.tool.on_mouse_up(
                col,
                row,
                self.canvas,
                ctrl=event.ctrl,
                alt=event.meta,
                pointer_x=px,
                pointer_y=py,
            )
            self._post_gesture_commit(commit)
        else:
            result = self.tool.on_mouse_up(
                col, row, self.canvas, pointer_x=px, pointer_y=py
            )
            if isinstance(self.tool, TextTool) and isinstance(result, BoxShape):
                self.open_text_editor(result)
            elif result is not None:
                self.post_message(self.ShapeCreated(result))
        self._refresh_dirty_since(before)

    def _post_gesture_commit(self, commit: GestureCommit | None) -> None:
        if commit is None:
            return
        if isinstance(commit, MoveCommit):
            if commit.dcol != 0 or commit.drow != 0:
                self.post_message(
                    self.ShapeMoved(commit.shapes, commit.dcol, commit.drow)
                )
        elif isinstance(commit, ResizeCommit):
            self.post_message(self.ShapeResized(commit.shape, commit.old_attrs))
        elif isinstance(commit, EdgeDragCommit):
            self.post_message(self.LineEdgeMoved(commit))
