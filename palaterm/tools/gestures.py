"""Drag gestures for the select tool.

A ``Gesture`` is a single in-flight drag (move, resize, edge-drag, rect-select).
Each one owns its own before-snapshot and updates the canvas/shape on every
mouse tick. On mouse-up the gesture commits and returns a typed result
describing what changed; the widget translates that into an undoable command.

Gestures replace the flag-mush that used to live on ``SelectTool``
(``_moving``, ``_resizing``, ``_resize_anchor``, ``_edge_drag_line``,
``_edge_snapshot``, …). One gesture is active at a time; ``SelectTool.gesture``
is the seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..connectors import Anchor, Connector, find_snap
from ..geometry import Point, Rect
from ..models import BorderStyle, BoxShape, LineShape, RectShape, Shape
from ..models.line import LineRouting

# ---- Commit results --------------------------------------------------------


@dataclass
class GestureCommit:
    """Marker for a gesture's mouse-up result."""


@dataclass
class MoveCommit(GestureCommit):
    """Selection moved by ``(dcol, drow)``."""

    shapes: list[Shape]
    dcol: int
    drow: int


@dataclass
class ResizeCommit(GestureCommit):
    """Shape resized; ``old_attrs`` is the pre-drag attribute snapshot."""

    shape: Shape
    old_attrs: dict[str, Any]


@dataclass
class EdgeDragCommit(GestureCommit):
    """Orthogonal line edge slid; ``before`` is the pre-drag routing."""

    line: LineShape
    before: LineRouting


@dataclass
class RectSelectCommit(GestureCommit):
    """Rectangle-select rubber band committed; ``rect`` is its final extent."""

    rect: Rect | None
    modifier: str  # "none" | "add" | "remove"


# ---- Gesture protocol ------------------------------------------------------


class Gesture(Protocol):
    def update(
        self,
        col: int,
        row: int,
        canvas: Any,
        *,
        pointer_x: float | None = None,
        pointer_y: float | None = None,
    ) -> None: ...

    def commit(
        self,
        col: int,
        row: int,
        canvas: Any,
        *,
        pointer_x: float | None = None,
        pointer_y: float | None = None,
    ) -> GestureCommit | None: ...

    def dirty_bounds(self, canvas: Any) -> list[Rect]: ...


# ---- Concrete gestures -----------------------------------------------------


class MoveGesture:
    """Drag the selection. Connected lines follow via ``LineShape.follow_anchor``."""

    def __init__(self, selected: list[Shape], start: Point) -> None:
        self._selected = selected
        self._start = start
        self._origin = start
        self._last = start

    def update(
        self,
        col: int,
        row: int,
        canvas: Any,
        *,
        pointer_x: float | None = None,
        pointer_y: float | None = None,
    ) -> None:
        dcol = col - self._last.col
        drow = row - self._last.row
        if dcol == 0 and drow == 0:
            return
        moved_ids = {s.id for s in self._selected}
        for shape in self._selected:
            shape.move(dcol, drow)
        for shape in self._selected:
            for conn in canvas.connector_mgr.get_by_target(shape.id):
                if conn.line_id in moved_ids:
                    continue
                line = next((s for s in canvas.shapes if s.id == conn.line_id), None)
                if not isinstance(line, LineShape):
                    continue
                if conn.anchor == Anchor.START:
                    line.follow_anchor(
                        "start", Point(line.start.col + dcol, line.start.row + drow)
                    )
                else:
                    line.follow_anchor(
                        "end", Point(line.end.col + dcol, line.end.row + drow)
                    )
        self._last = Point(col, row)

    def commit(
        self,
        col: int,
        row: int,
        canvas: Any,
        *,
        pointer_x: float | None = None,
        pointer_y: float | None = None,
    ) -> GestureCommit | None:
        # ``update`` already drove the last tick; the total delta is from the
        # original mouse-down to the current tracked position.
        dcol = self._last.col - self._origin.col
        drow = self._last.row - self._origin.row
        return MoveCommit(list(self._selected), dcol, drow)

    def dirty_bounds(self, canvas: Any) -> list[Rect]:
        bounds = [s.bound for s in self._selected]
        tracked = {s.id for s in self._selected}
        for shape_id in tracked:
            for conn in canvas.connector_mgr.get_by_target(shape_id):
                line = next((sh for sh in canvas.shapes if sh.id == conn.line_id), None)
                if line is not None:
                    bounds.append(line.bound)
        return bounds


class ResizeGesture:
    """Drag a non-line resize handle (Box corner/edge)."""

    def __init__(
        self,
        shape: Shape,
        handle: Any,
        anchor: Point | None,
        anchor_f: tuple[float, float] | None,
        old_attrs: dict[str, Any],
    ) -> None:
        self._shape = shape
        self._handle = handle
        self._anchor = anchor
        self._anchor_f = anchor_f
        self._old_attrs = old_attrs

    @property
    def shape(self) -> Shape:
        return self._shape

    def update(
        self,
        col: int,
        row: int,
        canvas: Any,
        *,
        pointer_x: float | None = None,
        pointer_y: float | None = None,
    ) -> None:
        from . import Handle

        shape = self._shape
        handle = self._handle
        if (
            isinstance(shape, BoxShape)
            and shape.border == BorderStyle.BRAILLE
            and self._anchor_f is not None
            and pointer_x is not None
            and pointer_y is not None
        ):
            ax, ay = self._anchor_f
            match handle:
                case (
                    Handle.TOP_LEFT
                    | Handle.TOP_RIGHT
                    | Handle.BOT_LEFT
                    | Handle.BOT_RIGHT
                ):
                    shape.resize_f(pointer_x, pointer_y, ax, ay)
                case Handle.TOP_MID | Handle.BOT_MID:
                    lf, _, rf, _ = (
                        shape.rect_f
                        if shape.rect_f
                        else (shape.bound.left, 0, shape.bound.right, 0)
                    )
                    shape.resize_f(lf, pointer_y, rf, ay)
                case Handle.MID_LEFT | Handle.MID_RIGHT:
                    _, tf, _, bf = (
                        shape.rect_f
                        if shape.rect_f
                        else (0, shape.bound.top, 0, shape.bound.bottom)
                    )
                    shape.resize_f(pointer_x, tf, ax, bf)
                case _:
                    return
        elif isinstance(shape, RectShape) and self._anchor is not None:
            anchor = self._anchor
            b = shape.bound
            match handle:
                case (
                    Handle.TOP_LEFT
                    | Handle.TOP_RIGHT
                    | Handle.BOT_LEFT
                    | Handle.BOT_RIGHT
                ):
                    new_rect = Rect.from_points(Point(col, row), anchor)
                case Handle.TOP_MID | Handle.BOT_MID:
                    new_rect = Rect.from_points(
                        Point(b.left, row), Point(b.right, anchor.row)
                    )
                case Handle.MID_LEFT | Handle.MID_RIGHT:
                    new_rect = Rect.from_points(
                        Point(col, b.top), Point(anchor.col, b.bottom)
                    )
                case _:
                    return
            shape.resize(new_rect)

    def commit(
        self,
        col: int,
        row: int,
        canvas: Any,
        *,
        pointer_x: float | None = None,
        pointer_y: float | None = None,
    ) -> GestureCommit | None:
        self.update(col, row, canvas, pointer_x=pointer_x, pointer_y=pointer_y)
        return ResizeCommit(self._shape, self._old_attrs)

    def dirty_bounds(self, canvas: Any) -> list[Rect]:
        bounds: list[Rect] = [self._shape.bound]
        for conn in canvas.connector_mgr.get_by_target(self._shape.id):
            line = next((sh for sh in canvas.shapes if sh.id == conn.line_id), None)
            if line is not None:
                bounds.append(line.bound)
        return bounds


class LineHandleGesture:
    """Drag a line endpoint handle (LINE_START / LINE_END).

    Owns ``snap_target`` so the renderer can highlight the target edge while
    the user is hovering it.
    """

    def __init__(self, line: LineShape, handle: Any, old_attrs: dict[str, Any]) -> None:
        self._line = line
        self._handle = handle
        self._old_attrs = old_attrs
        self.snap_target: Any = None

    @property
    def shape(self) -> Shape:
        return self._line

    def update(
        self,
        col: int,
        row: int,
        canvas: Any,
        *,
        pointer_x: float | None = None,
        pointer_y: float | None = None,
    ) -> None:
        from . import Handle

        line = self._line
        snap = find_snap(col, row, canvas.shapes, exclude_id=line.id)
        self.snap_target = snap
        if snap:
            pt = snap.point
            side_name = snap.side.name.lower()
        else:
            pt = Point(col, row)
            side_name = None
        if self._handle == Handle.LINE_START:
            line.start_side = side_name
            line.move_anchor("start", pt)
        else:
            line.end_side = side_name
            line.move_anchor("end", pt)

    def commit(
        self,
        col: int,
        row: int,
        canvas: Any,
        *,
        pointer_x: float | None = None,
        pointer_y: float | None = None,
    ) -> GestureCommit | None:
        from . import Handle

        self.update(col, row, canvas, pointer_x=pointer_x, pointer_y=pointer_y)
        line = self._line
        anchor = Anchor.START if self._handle == Handle.LINE_START else Anchor.END
        snap = find_snap(col, row, canvas.shapes, exclude_id=line.id)
        if snap:
            canvas.connector_mgr.add(
                Connector(line.id, anchor, snap.target_id, snap.side, snap.ratio)
            )
        else:
            canvas.connector_mgr.remove_by_line_anchor(line.id, anchor)
        self.snap_target = None
        return ResizeCommit(line, self._old_attrs)

    def dirty_bounds(self, canvas: Any) -> list[Rect]:
        bounds: list[Rect] = [self._line.bound]
        if self.snap_target is not None:
            target = next(
                (s for s in canvas.shapes if s.id == self.snap_target.target_id), None
            )
            if target is not None:
                bounds.append(target.bound)
        return bounds


class EdgeDragGesture:
    """Slide an interior segment of an orthogonal multi-segment line."""

    def __init__(self, line: LineShape, edge_index: int, before: LineRouting) -> None:
        self._line = line
        self._edge_index = edge_index
        self._before = before

    @property
    def line(self) -> LineShape:
        return self._line

    def update(
        self,
        col: int,
        row: int,
        canvas: Any,
        *,
        pointer_x: float | None = None,
        pointer_y: float | None = None,
    ) -> None:
        # Restore the mouse-down snapshot first so move_edge operates on the
        # original topology — without this, reduce-induced collapses drift the
        # edge index between ticks.
        line = self._line
        line.routing = self._before
        line.move_edge(self._edge_index, Point(col, row))

    def commit(
        self,
        col: int,
        row: int,
        canvas: Any,
        *,
        pointer_x: float | None = None,
        pointer_y: float | None = None,
    ) -> GestureCommit | None:
        if self._line.routing == self._before:
            return None
        return EdgeDragCommit(self._line, self._before)

    def dirty_bounds(self, canvas: Any) -> list[Rect]:
        return [self._line.bound]


class RectSelectGesture:
    """Rubber-band rectangle selection.

    Writes ``selection_rect`` / ``selection_rect_f`` on the host tool every
    tick so the renderer can paint the band; commit applies the selection
    based on ``mode`` (full / partial containment).
    """

    def __init__(
        self,
        host: Any,
        start: Point,
        start_f: tuple[float, float] | None,
        modifier: str,
    ) -> None:
        self._host = host
        self._start = start
        self._start_f = start_f
        self._modifier = modifier

    def update(
        self,
        col: int,
        row: int,
        canvas: Any,
        *,
        pointer_x: float | None = None,
        pointer_y: float | None = None,
    ) -> None:
        self._host.selection_rect = Rect.from_points(self._start, Point(col, row))
        if (
            self._start_f is not None
            and pointer_x is not None
            and pointer_y is not None
        ):
            sx, sy = self._start_f
            self._host.selection_rect_f = (
                min(sx, pointer_x),
                min(sy, pointer_y),
                max(sx, pointer_x),
                max(sy, pointer_y),
            )

    def commit(
        self,
        col: int,
        row: int,
        canvas: Any,
        *,
        pointer_x: float | None = None,
        pointer_y: float | None = None,
    ) -> GestureCommit | None:
        rect = Rect.from_points(self._start, Point(col, row))
        return RectSelectCommit(
            rect if (rect.width > 1 or rect.height > 1) else None, self._modifier
        )

    def dirty_bounds(self, canvas: Any) -> list[Rect]:
        rect = self._host.selection_rect
        return [rect] if rect is not None else []
