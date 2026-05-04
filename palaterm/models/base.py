"""Base shape classes."""

from __future__ import annotations

import uuid as _uuid

from ..geometry import Rect
from .charset import CharSet


class Shape:
    """Base shape class."""

    def __init__(self) -> None:
        self.id: str = _uuid.uuid4().hex[:8]

    @property
    def bound(self) -> Rect:
        raise NotImplementedError

    def render(self, charset: CharSet = CharSet.UNICODE) -> dict[tuple[int, int], str]:
        raise NotImplementedError

    def hit_test(self, col: int, row: int) -> bool:
        return self.bound.contains(col, row)

    def move(self, dcol: int, drow: int) -> None:
        raise NotImplementedError


class RectShape(Shape):
    """Base for shapes backed by a Rect."""

    def __init__(self, rect: Rect) -> None:
        super().__init__()
        self.rect = rect

    @property
    def bound(self) -> Rect:
        return self.rect

    def move(self, dcol: int, drow: int) -> None:
        self.rect = Rect(self.rect.left + dcol, self.rect.top + drow, self.rect.width, self.rect.height)

    def resize(self, new_rect: Rect) -> None:
        self.rect = new_rect
