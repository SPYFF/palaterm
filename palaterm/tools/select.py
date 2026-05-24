"""Select tool: click, drag-move, resize, and rectangle-select."""

from __future__ import annotations

from enum import Enum, auto

from ..geometry import Point, Rect
from ..models import BorderStyle, BoxShape, LineShape, RectShape, Shape
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
        self._resize_anchor_f: tuple[float, float] | None = None  # for braille rect precise resize
        self._rect_selecting: bool = False
        self.selection_rect: Rect | None = None
        self.selection_rect_f: tuple[float, float, float, float] | None = None  # (left_f, top_f, right_f, bottom_f)
        self.snap_target: object | None = None  # SnapResult during line handle drag
        self._modifier: str = "none"  # "none" | "add" | "remove"
        self._drag_start_f: tuple[float, float] | None = None
        # Edge-drag state (orthogonal multi-segment lines).
        self._edge_drag_line: LineShape | None = None
        self._edge_drag_index: int | None = None
        self._edge_snapshot: tuple[list[Point], bool] | None = None
        # Hover state for edge highlighting (rendering reads these).
        self.hover_edge_line: LineShape | None = None
        self.hover_edge_index: int | None = None
        self.hover_edge_whole: bool = False  # corner hover → highlight whole line
        self.hover_handle = None  # Handle enum value when hovering a handle

    def on_mouse_down(self, col: int, row: int, canvas, *, ctrl: bool = False, alt: bool = False,
                      pointer_x: float | None = None, pointer_y: float | None = None) -> Shape | None:
        from . import handle_at, Handle

        # Check if clicking on a handle of a selected shape
        for shape in self.selected:
            h = handle_at(shape, col, row, pointer_x, pointer_y)
            if h is not None:
                self._start_resize(shape, h, col, row)
                return shape

        # Edge-drag: clicking on the interior of a selected multi-segment
        # orthogonal line's edge starts a perpendicular slide of that segment.
        # Joint cells of selected lines fall through to whole-line move below.
        for shape in self.selected:
            if isinstance(shape, LineShape):
                edge_idx = shape.edge_at(col, row)
                if edge_idx is not None:
                    self._edge_drag_line = shape
                    self._edge_drag_index = edge_idx
                    self._edge_snapshot = (shape.joint_points, shape.edges_modified)
                    self._drag_start = Point(col, row)
                    self._moving = False
                    self._resizing = False
                    self._rect_selecting = False
                    return shape

        hit = canvas.shape_at(col, row)
        if hit and ctrl:
            if hit not in self.selected:
                self.selected.append(hit)
            return hit
        elif hit and alt:
            if hit in self.selected:
                self.selected.remove(hit)
            return None
        elif hit and hit in self.selected:
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
            if not ctrl and not alt:
                self.selected = []
            self._drag_start = Point(col, row)
            self._drag_start_f = (pointer_x, pointer_y) if pointer_x is not None and pointer_y is not None else None
            self._moving = False
            self._resizing = False
            self._rect_selecting = True
            self._modifier = "add" if ctrl else "remove" if alt else "none"
            self.selection_rect = None
            self.selection_rect_f = None
        return self.selected[0] if self.selected else None

    def update_hover(self, col: int, row: int,
                     pointer_x: float | None = None,
                     pointer_y: float | None = None) -> tuple[LineShape | None, int | None, bool]:
        """Recompute edge-hover state for selected lines.

        Returns (line, edge_index, whole_line) tuple matching the new state.
        ``edge_index`` is set when an edge interior is hovered; ``whole_line``
        is True when a corner joint is hovered (whole-line move target).
        """
        from . import handle_at

        new_line: LineShape | None = None
        new_index: int | None = None
        new_whole = False
        new_handle = None
        for shape in self.selected:
            h = handle_at(shape, col, row, pointer_x, pointer_y)
            if h is not None:
                new_handle = h
                break
            if not isinstance(shape, LineShape):
                continue
            edge_idx = shape.edge_at(col, row)
            if edge_idx is not None:
                new_line = shape
                new_index = edge_idx
                break
            joint_idx = shape.joint_at(col, row)
            if joint_idx is not None:
                new_line = shape
                new_whole = True
                break
        self.hover_handle = new_handle
        self.hover_edge_line = new_line
        self.hover_edge_index = new_index
        self.hover_edge_whole = new_whole
        return new_line, new_index, new_whole

    def _start_resize(self, shape: Shape, handle, col: int, row: int) -> None:
        from . import Handle

        self._resizing = True
        self._moving = False
        self._rect_selecting = False
        self._resize_handle = handle
        self._resize_shape = shape
        self._drag_start = Point(col, row)
        self._resize_anchor_f = None

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
            # Precise float anchor for braille rectangles
            if (isinstance(shape, BoxShape) and shape.border == BorderStyle.BRAILLE
                    and shape.rect_f is not None):
                lf, tf, rf, bf = shape.rect_f
                anchor_map = {
                    Handle.TOP_LEFT: (rf, bf), Handle.TOP_MID: (lf, bf), Handle.TOP_RIGHT: (lf, bf),
                    Handle.MID_LEFT: (rf, tf), Handle.MID_RIGHT: (lf, tf),
                    Handle.BOT_LEFT: (rf, tf), Handle.BOT_MID: (lf, tf), Handle.BOT_RIGHT: (lf, tf),
                }
                self._resize_anchor_f = anchor_map.get(handle)

    def on_mouse_drag(self, col: int, row: int, canvas, *, pointer_x: float | None = None, pointer_y: float | None = None) -> None:
        if (self._edge_drag_line is not None and self._edge_drag_index is not None
                and self._edge_snapshot is not None):
            # Restore from the mouse-down snapshot so move_edge operates on a
            # fresh state. Without this, reduce-induced topology changes make
            # the stored edge index refer to a different edge mid-drag, and
            # first/last edges spawn a new joint per mouse event.
            line = self._edge_drag_line
            before_joints, before_modified = self._edge_snapshot
            line._joint_points = [Point(p.col, p.row) for p in before_joints]
            line._edges_modified = before_modified
            if before_joints:
                line.start = before_joints[0]
                line.end = before_joints[-1]
            line.move_edge(self._edge_drag_index, Point(col, row))
            return
        if self._resizing and self._resize_shape and self._resize_handle:
            self._apply_resize(col, row, canvas, pointer_x=pointer_x, pointer_y=pointer_y)
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
                            new_pt = Point(line.start.col + dcol, line.start.row + drow)
                            line.follow_anchor("start", new_pt)
                        else:
                            new_pt = Point(line.end.col + dcol, line.end.row + drow)
                            line.follow_anchor("end", new_pt)
                self._drag_start = Point(col, row)
        elif self._rect_selecting and self._drag_start:
            self.selection_rect = Rect.from_points(self._drag_start, Point(col, row))
            if self._drag_start_f is not None and pointer_x is not None and pointer_y is not None:
                sx, sy = self._drag_start_f
                self.selection_rect_f = (min(sx, pointer_x), min(sy, pointer_y),
                                         max(sx, pointer_x), max(sy, pointer_y))

    def _apply_resize(self, col: int, row: int, canvas=None, *,
                      pointer_x: float | None = None, pointer_y: float | None = None) -> None:
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
                shape.start_side = side_name
                shape.move_anchor("start", pt)
            else:
                shape.end_side = side_name
                shape.move_anchor("end", pt)
        elif (isinstance(shape, BoxShape) and shape.border == BorderStyle.BRAILLE
                and self._resize_anchor_f is not None
                and pointer_x is not None and pointer_y is not None):
            ax, ay = self._resize_anchor_f
            match handle:
                case Handle.TOP_LEFT | Handle.TOP_RIGHT | Handle.BOT_LEFT | Handle.BOT_RIGHT:
                    shape.resize_f(pointer_x, pointer_y, ax, ay)
                case Handle.TOP_MID | Handle.BOT_MID:
                    lf, _, rf, _ = shape.rect_f if shape.rect_f else (shape.bound.left, 0, shape.bound.right, 0)
                    shape.resize_f(lf, pointer_y, rf, ay)
                case Handle.MID_LEFT | Handle.MID_RIGHT:
                    _, tf, _, bf = shape.rect_f if shape.rect_f else (0, shape.bound.top, 0, shape.bound.bottom)
                    shape.resize_f(pointer_x, tf, ax, bf)
                case _:
                    return
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

    def on_mouse_up(self, col: int, row: int, canvas, *, ctrl: bool = False, alt: bool = False,
                    pointer_x: float | None = None, pointer_y: float | None = None) -> Shape | None:
        if self._edge_drag_line is not None:
            line = self._edge_drag_line
            self._edge_drag_line = None
            self._edge_drag_index = None
            # Snapshot is left intact; the widget reads it after on_mouse_up
            # to construct the MoveLineEdge command.
            return line
        if self._resizing:
            self._apply_resize(col, row, canvas, pointer_x=pointer_x, pointer_y=pointer_y)
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
                    shapes = canvas.shapes_fully_in(rect)
                else:
                    shapes = canvas.shapes_partially_in(rect)
                if ctrl:
                    for s in shapes:
                        if s not in self.selected:
                            self.selected.append(s)
                elif alt:
                    for s in shapes:
                        if s in self.selected:
                            self.selected.remove(s)
                else:
                    self.selected = shapes
        self._moving = False
        self._resizing = False
        self._resize_handle = None
        self._resize_shape = None
        self._resize_anchor = None
        self._resize_anchor_f = None
        self._rect_selecting = False
        self._drag_start = None
        self._drag_start_f = None
        self.selection_rect = None
        self.selection_rect_f = None
        self._modifier = "none"
        return self.selected[0] if self.selected else None
