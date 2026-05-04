"""Concrete shape commands for undo/redo."""

from __future__ import annotations

from typing import Any

from ..canvas import Canvas
from ..connectors import Anchor, Connector, point_on_edge
from ..models.base import Shape
from ..models.line import LineShape
from ..geometry import Point


class AddShape:
    def __init__(self, canvas: Canvas, shape: Shape) -> None:
        self._canvas = canvas
        self._shape = shape

    def execute(self) -> None:
        if self._shape not in self._canvas.shapes:
            self._canvas.shapes.append(self._shape)

    def undo(self) -> None:
        self._canvas.shapes = [s for s in self._canvas.shapes if s.id != self._shape.id]


class RemoveShapes:
    def __init__(self, canvas: Canvas, shapes: list[Shape]) -> None:
        self._canvas = canvas
        self._shapes = list(shapes)
        self._indices: list[tuple[int, Shape]] = []
        self._removed_connectors: list[Connector] = []

    def execute(self) -> None:
        self._indices = [(self._canvas.shapes.index(s), s) for s in self._shapes if s in self._canvas.shapes]
        self._removed_connectors = []
        for s in self._shapes:
            # Remove connectors targeting this shape
            self._removed_connectors.extend(self._canvas.connector_mgr.remove_by_target(s.id))
            # Remove connectors from this line
            if isinstance(s, LineShape):
                self._removed_connectors.extend(self._canvas.connector_mgr.remove_by_line(s.id))
            self._canvas.shapes = [x for x in self._canvas.shapes if x.id != s.id]

    def undo(self) -> None:
        for idx, shape in sorted(self._indices):
            self._canvas.shapes.insert(idx, shape)
        for c in self._removed_connectors:
            self._canvas.connector_mgr.add(c)


class MoveShapes:
    def __init__(self, shapes: list[Shape], dcol: int, drow: int, canvas: Canvas | None = None) -> None:
        self._shapes = list(shapes)
        self._dcol = dcol
        self._drow = drow
        self._canvas = canvas
        # Store line endpoint moves for undo
        self._line_moves: list[tuple[str, str, Point, Point]] = []  # (line_id, "start"/"end", old_pt, new_pt)
        if canvas:
            self._record_line_moves()

    def _record_line_moves(self) -> None:
        """Record connected line endpoint positions that were moved during the drag."""
        if not self._canvas:
            return
        moved_ids = {s.id for s in self._shapes}
        for shape in self._shapes:
            for conn in self._canvas.connector_mgr.get_by_target(shape.id):
                if conn.line_id in moved_ids:
                    continue  # line is also being moved, no separate propagation
                # Find the line
                line = next((s for s in self._canvas.shapes if s.id == conn.line_id), None)
                if not isinstance(line, LineShape):
                    continue
                if conn.anchor == Anchor.START:
                    old_pt = Point(line.start.col - self._dcol, line.start.row - self._drow)
                    self._line_moves.append((line.id, "start", old_pt, line.start))
                else:
                    old_pt = Point(line.end.col - self._dcol, line.end.row - self._drow)
                    self._line_moves.append((line.id, "end", old_pt, line.end))

    def execute(self) -> None:
        # Shapes already moved by tool; this is for redo
        for s in self._shapes:
            s.move(self._dcol, self._drow)
        if self._canvas:
            self._propagate_connectors(self._dcol, self._drow)

    def undo(self) -> None:
        for s in self._shapes:
            s.move(-self._dcol, -self._drow)
        # Reverse line endpoint moves
        if self._canvas:
            for line_id, endpoint, old_pt, new_pt in self._line_moves:
                line = next((s for s in self._canvas.shapes if s.id == line_id), None)
                if not isinstance(line, LineShape):
                    continue
                if endpoint == "start":
                    line.start = old_pt
                else:
                    line.end = old_pt
                line._recompute()

    def _propagate_connectors(self, dcol: int, drow: int) -> None:
        """Move connected line endpoints by delta."""
        if not self._canvas:
            return
        moved_ids = {s.id for s in self._shapes}
        for shape in self._shapes:
            for conn in self._canvas.connector_mgr.get_by_target(shape.id):
                if conn.line_id in moved_ids:
                    continue
                line = next((s for s in self._canvas.shapes if s.id == conn.line_id), None)
                if not isinstance(line, LineShape):
                    continue
                if conn.anchor == Anchor.START:
                    line.start = Point(line.start.col + dcol, line.start.row + drow)
                else:
                    line.end = Point(line.end.col + dcol, line.end.row + drow)
                line._recompute()


class TransformShapes:
    """Records before/after geometry for any shape transform (resize, etc.)."""

    def __init__(self, snapshots: list[tuple[Shape, dict[str, Any]]]) -> None:
        self._old = snapshots
        self._new: list[tuple[Shape, dict[str, Any]]] = [
            (shape, {attr: getattr(shape, attr) for attr in attrs})
            for shape, attrs in snapshots
        ]

    def execute(self) -> None:
        for (shape, _), (_, new_attrs) in zip(self._old, self._new):
            for attr, val in new_attrs.items():
                setattr(shape, attr, val)
            recompute = getattr(shape, "_recompute", None)
            if recompute:
                recompute()

    def undo(self) -> None:
        for shape, old_attrs in self._old:
            for attr, val in old_attrs.items():
                setattr(shape, attr, val)
            recompute = getattr(shape, "_recompute", None)
            if recompute:
                recompute()
