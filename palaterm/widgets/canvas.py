"""Canvas widget: handles mouse events and delegates rendering."""

from __future__ import annotations

import math
import time

from textual.events import MouseDown, MouseMove, MouseUp
from textual.geometry import Region
from textual.message import Message
from textual.strip import Strip
from textual.widget import Widget

from ..canvas import Canvas
from ..geometry import Point, Rect
from ..rendering import FrameRenderer
from ..models import BoxShape, CharSet, LineShape
from ..tools import DrawTool, SelectTool, TextTool
from .modals import TextEditModal


class CanvasWidget(Widget, can_focus=True):
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
        def __init__(self, line, before_joints, before_modified: bool) -> None:
            super().__init__()
            self.line = line
            self.before_joints = before_joints
            self.before_modified = before_modified

    DEFAULT_CSS = """
    CanvasWidget {
        width: 1fr;
        height: 1fr;
        overflow: hidden;
        color: $text;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.canvas = Canvas()
        self.tool: DrawTool | SelectTool = SelectTool()
        self.charset: CharSet = CharSet.UNICODE
        self._scroll_col = 0
        self._scroll_row = 0
        self._mouse_down = False
        self._editing: bool = False
        self._renderer = FrameRenderer(self.canvas)
        self._last_click_time: float = 0
        self._last_click_pos: tuple[int, int] = (0, 0)
        self._move_start: Point | None = None
        self._resize_snapshot: tuple | None = None
        self._edge_drag_snapshot: tuple | None = None  # (line, before_joints, before_modified)

    def _to_canvas_coords(self, x: int, y: int) -> tuple[int, int]:
        return x + self._scroll_col, y + self._scroll_row

    def _to_canvas_coords_f(self, pointer_x: float, pointer_y: float) -> tuple[int, int]:
        """Floor pointer floats to the cell they fall into.

        Must use floor (not round) so that sub-cell offsets — which are derived
        from the same floor — describe a position *inside* the returned cell
        rather than a phantom position in the next cell over.
        """
        return math.floor(pointer_x) + self._scroll_col, math.floor(pointer_y) + self._scroll_row

    def open_text_editor(self, shape: BoxShape) -> None:
        self._editing = True

        def on_dismiss(result: str | None) -> None:
            self._editing = False
            if result is not None and result.strip():
                shape.text = result
                lines = result.split("\n")
                w = max((len(l) for l in lines), default=0) + 2
                h = len(lines) + 2
                r = shape.rect
                shape.rect = Rect(r.left, r.top, max(r.width, w, 3), max(r.height, h, 3))
            else:
                if not shape.text:
                    self.canvas.remove_shape(shape)
            self.refresh()

        self.app.push_screen(TextEditModal(shape.text), on_dismiss)

    def render_line(self, y: int) -> Strip:
        viewport = Rect(self._scroll_col, self._scroll_row, self.size.width, self.size.height)
        return self._renderer.render_line(y, viewport, self.tool, self.rich_style, self.charset)

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
        self._renderer.invalidate()
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
            # The selection highlight + resize handles.
            bounds.extend(s.bound for s in tool.selected)
            if tool._resize_shape is not None:
                bounds.append(tool._resize_shape.bound)
            # The live rectangle-select rubber band.
            if tool.selection_rect is not None:
                bounds.append(tool.selection_rect)
            # Lines connected to a moving/resizing shape track its motion, so
            # they redraw too even though they aren't selected.
            tracked = {s.id for s in tool.selected}
            if tool._resize_shape is not None:
                tracked.add(tool._resize_shape.id)
            bounds.extend(self._connected_line_bounds(tracked))
            # Snap-target highlight when dragging a line endpoint onto a box.
            if tool.snap_target is not None:
                bounds.extend(self._snap_target_bounds(tool.snap_target))
            # Edge-drag in flight: the line's bound shifts mid-drag.
            if tool._edge_drag_line is not None:
                bounds.append(tool._edge_drag_line.bound)
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
                line = next((sh for sh in self.canvas.shapes
                             if sh.id == conn.line_id), None)
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
            if (hit and isinstance(hit, BoxShape) and
                    now - self._last_click_time < 0.4 and
                    self._last_click_pos == (col, row)):
                self.tool.selected = [hit]
                self.open_text_editor(hit)
                self._last_click_time = 0
                return
        self._last_click_time = now
        self._last_click_pos = (col, row)
        self.capture_mouse()
        self._mouse_down = True
        self._move_start = Point(col, row)
        before = self._tool_dirty_bounds()
        if isinstance(self.tool, SelectTool):
            self.tool.on_mouse_down(col, row, self.canvas, ctrl=event.ctrl, alt=event.meta,
                                    pointer_x=px, pointer_y=py)
        else:
            self.tool.on_mouse_down(col, row, self.canvas, pointer_x=px, pointer_y=py)
        if isinstance(self.tool, SelectTool) and self.tool._resizing and self.tool._resize_shape:
            shape = self.tool._resize_shape
            if isinstance(shape, LineShape):
                self._resize_snapshot = (shape, {"start": shape.start, "end": shape.end,
                                                  "_joint_points": list(shape.joint_points),
                                                  "_edges_modified": shape.edges_modified})
            else:
                self._resize_snapshot = (shape, {"rect": shape.rect})
        if isinstance(self.tool, SelectTool) and self.tool._edge_drag_line is not None:
            line = self.tool._edge_drag_line
            self._edge_drag_snapshot = (line, list(line.joint_points), line.edges_modified)
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
            edge_changed = (old_edge_line is not self.tool.hover_edge_line
                            or old_edge_index != self.tool.hover_edge_index
                            or old_edge_whole != self.tool.hover_edge_whole)
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
        elif self.tool.hover_edge_line is not None and self.tool.hover_edge_index is not None:
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
        # Check if select tool was moving before on_mouse_up resets state
        was_moving = (isinstance(self.tool, SelectTool) and
                      self.tool._moving and self.tool.selected and self._move_start)
        was_resizing = (isinstance(self.tool, SelectTool) and self.tool._resizing)
        was_edge_dragging = (isinstance(self.tool, SelectTool)
                             and self.tool._edge_drag_line is not None
                             and self._edge_drag_snapshot is not None)
        before = self._tool_dirty_bounds()
        if isinstance(self.tool, SelectTool):
            result = self.tool.on_mouse_up(col, row, self.canvas, ctrl=event.ctrl, alt=event.meta,
                                           pointer_x=px, pointer_y=py)
        else:
            result = self.tool.on_mouse_up(col, row, self.canvas, pointer_x=px, pointer_y=py)
        if isinstance(self.tool, TextTool) and isinstance(result, BoxShape):
            self.open_text_editor(result)
        elif result and not isinstance(self.tool, SelectTool):
            self.post_message(self.ShapeCreated(result))
        elif was_moving:
            dcol = col - self._move_start.col
            drow = row - self._move_start.row
            if dcol != 0 or drow != 0:
                self.post_message(self.ShapeMoved(list(self.tool.selected), dcol, drow))
        elif was_resizing and self._resize_snapshot:
            shape, old_attrs = self._resize_snapshot
            self.post_message(self.ShapeResized(shape, old_attrs))
        elif was_edge_dragging and self._edge_drag_snapshot:
            line, before_joints, before_modified = self._edge_drag_snapshot
            if list(line.joint_points) != before_joints or line.edges_modified != before_modified:
                self.post_message(self.LineEdgeMoved(line, before_joints, before_modified))
        self._move_start = None
        self._resize_snapshot = None
        self._edge_drag_snapshot = None
        self._refresh_dirty_since(before)
