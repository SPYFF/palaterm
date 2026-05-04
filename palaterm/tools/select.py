"""Select tool: click, drag-move, resize, and rectangle-select."""

from __future__ import annotations

from enum import Enum, auto

from ..geometry import Point, Rect
from ..shapes import LineShape, RectShape, Shape


class SelectMode(Enum):
    FULL = auto()
    PARTIAL = auto()


class SelectTool:
    """Select, move, and resize shapes."""

    def __init__(self) -> None:
        self.selected: list[Shape] = []
        self.hover_shape: Shape | None = None
        self.mode: SelectMode = SelectMode.FULL
        self._drag_start: Point | None = None
        self._moving: bool = False
        self._resizing: bool = False
        self._resize_handle = None
        self._resize_shape: Shape | None = None
        self._resize_anchor: Point | None = None
        self._rect_selecting: bool = False
        self.selection_rect: Rect | None = None

    def on_mouse_down(self, col: int, row: int, canvas) -> Shape | None:
        from . import handle_at, Handle

        # Check if clicking on a handle of a selected shape
        for shape in self.selected:
            h = handle_at(shape, col, row)
            if h is not None:
                self._start_resize(shape, h, col, row)
                return shape

        hit = canvas.shape_at(col, row)
        if hit and hit in self.selected:
            self._drag_start = Point(col, row)
            self._moving = True
            self._rect_selecting = False
            self._resizing = False
        elif hit:
            self.selected = [hit]
            self._drag_start = Point(col, row)
            self._moving = True
            self._rect_selecting = False
            self._resizing = False
        else:
            self.selected = []
            self._drag_start = Point(col, row)
            self._moving = False
            self._resizing = False
            self._rect_selecting = True
            self.selection_rect = None
        return self.selected[0] if self.selected else None

    def _start_resize(self, shape: Shape, handle, col: int, row: int) -> None:
        from . import Handle

        self._resizing = True
        self._moving = False
        self._rect_selecting = False
        self._resize_handle = handle
        self._resize_shape = shape
        self._drag_start = Point(col, row)

        if isinstance(shape, LineShape):
            self._resize_anchor = None
        else:
            b = shape.bound
            match handle:
                case Handle.TOP_LEFT:
                    self._resize_anchor = Point(b.right, b.bottom)
                case Handle.TOP_MID:
                    self._resize_anchor = Point(b.left, b.bottom)
                case Handle.TOP_RIGHT:
                    self._resize_anchor = Point(b.left, b.bottom)
                case Handle.MID_LEFT:
                    self._resize_anchor = Point(b.right, b.top)
                case Handle.MID_RIGHT:
                    self._resize_anchor = Point(b.left, b.top)
                case Handle.BOT_LEFT:
                    self._resize_anchor = Point(b.right, b.top)
                case Handle.BOT_MID:
                    self._resize_anchor = Point(b.left, b.top)
                case Handle.BOT_RIGHT:
                    self._resize_anchor = Point(b.left, b.top)

    def on_mouse_drag(self, col: int, row: int, canvas) -> None:
        if self._resizing and self._resize_shape and self._resize_handle:
            self._apply_resize(col, row)
        elif self._moving and self.selected and self._drag_start:
            dcol = col - self._drag_start.col
            drow = row - self._drag_start.row
            if dcol != 0 or drow != 0:
                for shape in self.selected:
                    shape.move(dcol, drow)
                self._drag_start = Point(col, row)
        elif self._rect_selecting and self._drag_start:
            self.selection_rect = Rect.from_points(self._drag_start, Point(col, row))

    def _apply_resize(self, col: int, row: int) -> None:
        from . import Handle

        shape = self._resize_shape
        handle = self._resize_handle
        if isinstance(shape, LineShape):
            if handle == Handle.LINE_START:
                shape.start = Point(col, row)
            else:
                shape.end = Point(col, row)
            shape._recompute()
        elif isinstance(shape, RectShape) and self._resize_anchor:
            anchor = self._resize_anchor
            b = shape.bound
            match handle:
                case Handle.TOP_LEFT | Handle.TOP_RIGHT | Handle.BOT_LEFT | Handle.BOT_RIGHT:
                    new_rect = Rect.from_points(Point(col, row), anchor)
                case Handle.TOP_MID | Handle.BOT_MID:
                    new_rect = Rect.from_points(Point(b.left, row), Point(b.right, anchor.row))
                case Handle.MID_LEFT | Handle.MID_RIGHT:
                    new_rect = Rect.from_points(Point(col, b.top), Point(anchor.col, b.bottom))
                case _:
                    return
            shape.resize(new_rect)

    def on_mouse_up(self, col: int, row: int, canvas) -> Shape | None:
        if self._resizing:
            self._apply_resize(col, row)
        elif self._rect_selecting and self._drag_start:
            rect = Rect.from_points(self._drag_start, Point(col, row))
            if rect.width > 1 or rect.height > 1:
                if self.mode == SelectMode.FULL:
                    self.selected = canvas.shapes_fully_in(rect)
                else:
                    self.selected = canvas.shapes_partially_in(rect)
        self._moving = False
        self._resizing = False
        self._resize_handle = None
        self._resize_shape = None
        self._resize_anchor = None
        self._rect_selecting = False
        self._drag_start = None
        self.selection_rect = None
        return self.selected[0] if self.selected else None
