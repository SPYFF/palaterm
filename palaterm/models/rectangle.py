"""Rectangle shape."""

from __future__ import annotations

import math

from ..geometry import Rect
from .base import RectShape, render_border
from .charset import CharSet, braille_rect, braille_rect_precise
from .enums import BORDER_CHARS, BorderStyle, FILL_CHARS, FillStyle


class RectangleShape(RectShape):
    def __init__(self, rect: Rect, border: BorderStyle = BorderStyle.LIGHT, fill: FillStyle = FillStyle.NONE):
        super().__init__(rect)
        self.border = border
        self.fill = fill
        # Sub-cell-precise edges for braille borders; (left_f, top_f, right_f, bottom_f).
        # When set together with BRAILLE border, drives the border render path.
        self.rect_f: tuple[float, float, float, float] | None = None

    def render(self, charset: CharSet = CharSet.UNICODE) -> dict[tuple[int, int], str]:
        cells: dict[tuple[int, int], str] = {}
        r = self.rect
        if r.width < 1 or r.height < 1:
            return cells

        if self.fill != FillStyle.NONE:
            fc = FILL_CHARS[self.fill]
            for row in range(r.top, r.bottom + 1):
                for col in range(r.left, r.right + 1):
                    cells[(col, row)] = fc

        if self.border == BorderStyle.BRAILLE:
            if self.rect_f is not None:
                lf, tf, rf, bf = self.rect_f
                cells.update(braille_rect_precise(lf, tf, rf, bf, charset))
            else:
                cells.update(braille_rect(r.left, r.top, r.right, r.bottom, charset))
            return cells

        tl, tr, bl, br, h, v = BORDER_CHARS[self.border]

        if r.width == 1 and r.height == 1:
            cells[(r.left, r.top)] = "□"
        elif r.width == 1:
            for row in range(r.top, r.bottom + 1):
                cells[(r.left, row)] = v
        elif r.height == 1:
            for col in range(r.left, r.right + 1):
                cells[(col, r.top)] = h
        else:
            cells.update(render_border(r, self.border))

        return cells

    def move(self, dcol: int, drow: int) -> None:
        super().move(dcol, drow)
        if self.rect_f is not None:
            lf, tf, rf, bf = self.rect_f
            self.rect_f = (lf + dcol, tf + drow, rf + dcol, bf + drow)

    def resize(self, new_rect: Rect) -> None:
        super().resize(new_rect)
        # Integer resize path: drop sub-cell precision.
        self.rect_f = None

    def resize_f(self, left_f: float, top_f: float, right_f: float, bottom_f: float) -> None:
        """Resize with sub-cell precision; keeps integer rect as bounding box."""
        self.rect_f = (min(left_f, right_f), min(top_f, bottom_f),
                       max(left_f, right_f), max(top_f, bottom_f))
        lf, tf, rf, bf = self.rect_f
        left = math.floor(lf)
        top = math.floor(tf)
        right = math.floor(rf)
        bottom = math.floor(bf)
        self.rect = Rect(left, top, right - left + 1, bottom - top + 1)
