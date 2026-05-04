"""Geometric primitives used throughout Palaterm."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Point:
    col: int
    row: int


@dataclass
class Rect:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width - 1

    @property
    def bottom(self) -> int:
        return self.top + self.height - 1

    @classmethod
    def from_points(cls, p1: Point, p2: Point) -> Rect:
        left = min(p1.col, p2.col)
        top = min(p1.row, p2.row)
        return cls(left, top, abs(p2.col - p1.col) + 1, abs(p2.row - p1.row) + 1)

    def contains(self, col: int, row: int) -> bool:
        return self.left <= col <= self.right and self.top <= row <= self.bottom
