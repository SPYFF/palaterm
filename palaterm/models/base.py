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


# Attributes whose mutation invalidates the render cache.
_TRACKED_ATTRS = frozenset(
    {
        "text",
        "border",
        "fill",
        "halign",
        "valign",
        "line_style",
        "start_ending",
        "end_ending",
        "rect",
        "rect_f",
        "start",
        "end",
        "start_side",
        "end_side",
        "start_sub",
        "end_sub",
    }
)


class Shape(ABC):
    """Base shape class."""

    def __init__(self) -> None:
        self.id: str = _uuid.uuid4().hex[:8]
        self.fg: str | None = None
        self.bg: str | None = None
        self._version: int = 0
        self._render_cache: tuple[int, CharSet, dict[tuple[int, int], str]] | None = (
            None
        )

    def _bump_version(self) -> None:
        self._version += 1

    def __setattr__(self, name: str, value) -> None:
        super().__setattr__(name, value)
        if name in _TRACKED_ATTRS:
            # Bump version — use super().__setattr__ to avoid recursion
            super().__setattr__("_version", getattr(self, "_version", 0) + 1)

    @property
    @abstractmethod
    def bound(self) -> Rect: ...

    @abstractmethod
    def _render_impl(
        self, charset: CharSet = CharSet.UNICODE
    ) -> dict[tuple[int, int], str]: ...

    def render(self, charset: CharSet = CharSet.UNICODE) -> dict[tuple[int, int], str]:
        """Cached render: returns the same dict if shape hasn't mutated."""
        cache = self._render_cache
        if cache is not None and cache[0] == self._version and cache[1] == charset:
            return cache[2]
        result = self._render_impl(charset)
        self._render_cache = (self._version, charset, result)
        return result

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
