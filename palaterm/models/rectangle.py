"""Rectangle shape."""

from __future__ import annotations

from ..geometry import Rect
from .base import RectShape, render_border
from .charset import CharSet, braille_rect
from .enums import BORDER_CHARS, BorderStyle, FILL_CHARS, FillStyle


class RectangleShape(RectShape):
    def __init__(self, rect: Rect, border: BorderStyle = BorderStyle.LIGHT, fill: FillStyle = FillStyle.NONE):
        super().__init__(rect)
        self.border = border
        self.fill = fill

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
