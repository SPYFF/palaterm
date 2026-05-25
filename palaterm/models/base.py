"""Base shape classes."""

from __future__ import annotations

import uuid as _uuid
from abc import ABC, abstractmethod

from ..geometry import Rect
from .charset import CharSet
from .enums import BORDER_CHARS, BorderStyle


def render_border(rect: Rect, border: BorderStyle) -> dict[tuple[int, int], str]:
    """Render box-drawing border characters for a rect.

    Requires width >= 2 and height >= 2.
    """
    tl, tr, bl, br, h, v = BORDER_CHARS[border]
    cells: dict[tuple[int, int], str] = {}
    cells[(rect.left, rect.top)] = tl
    cells[(rect.right, rect.top)] = tr
    cells[(rect.left, rect.bottom)] = bl
    cells[(rect.right, rect.bottom)] = br
    for col in range(rect.left + 1, rect.right):
        cells[(col, rect.top)] = h
        cells[(col, rect.bottom)] = h
    for row in range(rect.top + 1, rect.bottom):
        cells[(rect.left, row)] = v
        cells[(rect.right, row)] = v
    return cells


class Shape(ABC):
    """Base shape class."""

    def __init__(self) -> None:
        self.id: str = _uuid.uuid4().hex[:8]
        self.fg: str | None = None
        self.bg: str | None = None

    @property
    @abstractmethod
    def bound(self) -> Rect: ...

    @abstractmethod
    def render(
        self, charset: CharSet = CharSet.UNICODE
    ) -> dict[tuple[int, int], str]: ...

    def hit_test(self, col: int, row: int) -> bool:
        return self.bound.contains(col, row)

    @abstractmethod
    def move(self, dcol: int, drow: int) -> None: ...


class RectShape(Shape):
    """Base for shapes backed by a Rect."""

    def __init__(self, rect: Rect) -> None:
        super().__init__()
        self.rect = rect

    @property
    def bound(self) -> Rect:
        return self.rect

    def move(self, dcol: int, drow: int) -> None:
        self.rect = Rect(
            self.rect.left + dcol,
            self.rect.top + drow,
            self.rect.width,
            self.rect.height,
        )

    def resize(self, new_rect: Rect) -> None:
        self.rect = new_rect
