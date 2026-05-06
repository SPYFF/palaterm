"""Canvas widget: handles mouse events and delegates rendering."""

from __future__ import annotations

import time

from textual.events import MouseDown, MouseMove, MouseUp
from textual.message import Message
from textual.strip import Strip
from textual.widget import Widget

from ..canvas import Canvas
from ..geometry import Point, Rect
from ..rendering import FrameRenderer
from ..models import CharSet, LineShape, TextShape
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

    def _to_canvas_coords(self, x: int, y: int) -> tuple[int, int]:
        return x + self._scroll_col, y + self._scroll_row

    def open_text_editor(self, shape: TextShape) -> None:
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

    def refresh(self, *args, **kwargs) -> None:
        self._renderer.invalidate()
        super().refresh(*args, **kwargs)

    def on_mouse_down(self, event: MouseDown) -> None:
        if self._editing:
            return
        col, row = self._to_canvas_coords(event.x, event.y)
        now = time.monotonic()
        if isinstance(self.tool, SelectTool) and event.button == 1:
            hit = self.canvas.shape_at(col, row)
            if (hit and isinstance(hit, TextShape) and
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
        if isinstance(self.tool, SelectTool):
            self.tool.on_mouse_down(col, row, self.canvas, ctrl=event.ctrl, alt=event.meta)
        else:
            self.tool.on_mouse_down(col, row, self.canvas)
        if isinstance(self.tool, SelectTool) and self.tool._resizing and self.tool._resize_shape:
            shape = self.tool._resize_shape
            if isinstance(shape, LineShape):
                self._resize_snapshot = (shape, {"start": shape.start, "end": shape.end})
            else:
                self._resize_snapshot = (shape, {"rect": shape.rect})
        self.refresh()

    def on_mouse_move(self, event: MouseMove) -> None:
        if self._editing:
            return
        col, row = self._to_canvas_coords(event.x, event.y)
        if self._mouse_down:
            self.tool.on_mouse_drag(col, row, self.canvas)
            self.refresh()
        elif isinstance(self.tool, SelectTool):
            old = self.tool.hover_shape
            self.tool.hover_shape = self.canvas.shape_at(col, row)
            if self.tool.hover_shape != old:
                self.refresh()

    def on_mouse_up(self, event: MouseUp) -> None:
        if self._editing:
            return
        self.release_mouse()
        self._mouse_down = False
        col, row = self._to_canvas_coords(event.x, event.y)
        # Check if select tool was moving before on_mouse_up resets state
        was_moving = (isinstance(self.tool, SelectTool) and
                      self.tool._moving and self.tool.selected and self._move_start)
        was_resizing = (isinstance(self.tool, SelectTool) and self.tool._resizing)
        if isinstance(self.tool, SelectTool):
            result = self.tool.on_mouse_up(col, row, self.canvas, ctrl=event.ctrl, alt=event.meta)
        else:
            result = self.tool.on_mouse_up(col, row, self.canvas)
        if isinstance(self.tool, TextTool) and isinstance(result, TextShape):
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
        self._move_start = None
        self._resize_snapshot = None
        self.refresh()
