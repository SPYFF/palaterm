"""Concrete shape commands for undo/redo."""

from __future__ import annotations

from ..canvas import Canvas
from ..models.base import Shape
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

    def execute(self) -> None:
        self._indices = [(self._canvas.shapes.index(s), s) for s in self._shapes if s in self._canvas.shapes]
        for s in self._shapes:
            self._canvas.shapes = [x for x in self._canvas.shapes if x.id != s.id]

    def undo(self) -> None:
        for idx, shape in sorted(self._indices):
            self._canvas.shapes.insert(idx, shape)


class MoveShapes:
    def __init__(self, shapes: list[Shape], dcol: int, drow: int) -> None:
        self._shapes = list(shapes)
        self._dcol = dcol
        self._drow = drow

    def execute(self) -> None:
        for s in self._shapes:
            s.move(self._dcol, self._drow)

    def undo(self) -> None:
        for s in self._shapes:
            s.move(-self._dcol, -self._drow)
