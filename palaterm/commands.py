"""Command pattern for undoable operations."""

from __future__ import annotations

from typing import Any, Callable, Protocol

from .canvas import Canvas
from .connectors import Anchor, Connector
from .geometry import Point
from .models.base import Shape
from .models.line import LineRouting, LineShape


class Command(Protocol):
    def execute(self) -> None: ...
    def undo(self) -> None: ...


class CommandHistory:
    """Manages undo/redo stacks.

    Exposes a single ``on_change`` callback that fires after every
    push/execute/undo/redo. The widget subscribes to recompute the
    virtual canvas; this is the canonical seam, so callers no longer
    need to invoke ``_update_virtual_size()`` manually.
    """

    def __init__(self) -> None:
        self._undo: list[Command] = []
        self._redo: list[Command] = []
        self._save_point: int = 0
        self.on_change: Callable[[], None] | None = None

    def mark_saved(self) -> None:
        self._save_point = len(self._undo)

    @property
    def is_dirty(self) -> bool:
        return len(self._undo) != self._save_point

    def _notify(self) -> None:
        if self.on_change is not None:
            self.on_change()

    def push(self, cmd: Command) -> None:
        """Record a command that was already executed."""
        self._undo.append(cmd)
        self._redo.clear()
        self._notify()

    def execute(self, cmd: Command) -> None:
        cmd.execute()
        self._undo.append(cmd)
        self._redo.clear()
        self._notify()

    def undo(self) -> bool:
        if not self._undo:
            return False
        cmd = self._undo.pop()
        cmd.undo()
        self._redo.append(cmd)
        self._notify()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        cmd = self._redo.pop()
        cmd.execute()
        self._undo.append(cmd)
        self._notify()
        return True

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)


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
            self._removed_connectors.extend(self._canvas.connector_mgr.remove_by_target(s.id))
            if isinstance(s, LineShape):
                self._removed_connectors.extend(self._canvas.connector_mgr.remove_by_line(s.id))
            self._canvas.shapes = [x for x in self._canvas.shapes if x.id != s.id]

    def undo(self) -> None:
        for idx, shape in sorted(self._indices):
            self._canvas.shapes.insert(idx, shape)
        for c in self._removed_connectors:
            self._canvas.connector_mgr.add(c)


class MoveShapes:
    def __init__(self, shapes: list[Shape], dcol: int, drow: int,
                 canvas: Canvas | None = None) -> None:
        self._shapes = list(shapes)
        self._dcol = dcol
        self._drow = drow
        self._canvas = canvas

    def execute(self) -> None:
        for s in self._shapes:
            s.move(self._dcol, self._drow)
        self._propagate_connectors(self._dcol, self._drow)

    def undo(self) -> None:
        for s in self._shapes:
            s.move(-self._dcol, -self._drow)
        self._propagate_connectors(-self._dcol, -self._drow)

    def _propagate_connectors(self, dcol: int, drow: int) -> None:
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
                    line.follow_anchor("start", Point(line.start.col + dcol, line.start.row + drow))
                else:
                    line.follow_anchor("end", Point(line.end.col + dcol, line.end.row + drow))


class AddShapes:
    """Add multiple shapes (and optionally connectors) in one undoable operation."""

    def __init__(self, canvas: Canvas, shapes: list[Shape], connectors: list[Connector] | None = None) -> None:
        self._canvas = canvas
        self._shapes = list(shapes)
        self._connectors = list(connectors) if connectors else []

    def execute(self) -> None:
        for s in self._shapes:
            if s not in self._canvas.shapes:
                self._canvas.shapes.append(s)
        for c in self._connectors:
            self._canvas.connector_mgr.add(c)

    def undo(self) -> None:
        ids = {s.id for s in self._shapes}
        for c in self._connectors:
            self._canvas.connector_mgr.remove_by_line_anchor(c.line_id, c.anchor)
        self._canvas.shapes = [s for s in self._canvas.shapes if s.id not in ids]


class MoveLineEdge:
    """Snapshot the routing of a line before/after an edge-drag."""

    def __init__(self, line: LineShape, before: LineRouting) -> None:
        self._line = line
        self._before = before
        self._after = line.routing

    def execute(self) -> None:
        self._line.routing = self._after

    def undo(self) -> None:
        self._line.routing = self._before


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
