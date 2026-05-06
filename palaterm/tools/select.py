"""Select tool: click, drag-move, resize, and rectangle-select."""

from __future__ import annotations

from enum import Enum, auto

from ..geometry import Point, Rect
from ..models import LineShape, RectShape, Shape
from ..connectors import Anchor, Connector, find_snap


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
        self.snap_target: object | None = None  # SnapResult during line handle drag

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
            self._apply_resize(col, row, canvas)
        elif self._moving and self.selected and self._drag_start:
            dcol = col - self._drag_start.col
            drow = row - self._drag_start.row
            if dcol != 0 or drow != 0:
                moved_ids = {s.id for s in self.selected}
                for shape in self.selected:
                    shape.move(dcol, drow)
                # Propagate to connected lines not in selection
                for shape in self.selected:
                    for conn in canvas.connector_mgr.get_by_target(shape.id):
                        if conn.line_id in moved_ids:
                            continue
                        line = next((s for s in canvas.shapes if s.id == conn.line_id), None)
                        if not isinstance(line, LineShape):
                            continue
                        if conn.anchor == Anchor.START:
                            line.start = Point(line.start.col + dcol, line.start.row + drow)
                        else:
                            line.end = Point(line.end.col + dcol, line.end.row + drow)
                        line._recompute()
                self._drag_start = Point(col, row)
        elif self._rect_selecting and self._drag_start:
            self.selection_rect = Rect.from_points(self._drag_start, Point(col, row))

    def _apply_resize(self, col: int, row: int, canvas=None) -> None:
        from . import Handle

        shape = self._resize_shape
        handle = self._resize_handle
        if isinstance(shape, LineShape):
            snap = None
            if canvas:
                snap = find_snap(col, row, canvas.shapes, exclude_id=shape.id)
            self.snap_target = snap
            if snap:
                pt = snap.point
                side_name = snap.side.name.lower()
            else:
                pt = Point(col, row)
                side_name = None

            if handle == Handle.LINE_START:
                shape.start = pt
                shape.start_side = side_name
            else:
                shape.end = pt
                shape.end_side = side_name
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
            self._apply_resize(col, row, canvas)
            # Commit connector for line handle
            from . import Handle
            if isinstance(self._resize_shape, LineShape) and self._resize_handle in (Handle.LINE_START, Handle.LINE_END):
                line = self._resize_shape
                anchor = Anchor.START if self._resize_handle == Handle.LINE_START else Anchor.END
                snap = find_snap(col, row, canvas.shapes, exclude_id=line.id)
                if snap:
                    connector = Connector(line.id, anchor, snap.target_id, snap.side, snap.ratio)
                    canvas.connector_mgr.add(connector)
                else:
                    canvas.connector_mgr.remove_by_line_anchor(line.id, anchor)
            self.snap_target = None
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
