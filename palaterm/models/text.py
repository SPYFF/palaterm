"""Text shape."""

from __future__ import annotations

from ..geometry import Rect
from .base import RectShape
from .charset import CharSet
from .enums import BORDER_CHARS, BorderStyle, HAlign, VAlign


class TextShape(RectShape):
    def __init__(self, rect: Rect, text: str = "", border: BorderStyle = BorderStyle.LIGHT, has_border: bool = False,
                 halign: HAlign = HAlign.LEFT, valign: VAlign = VAlign.TOP):
        super().__init__(rect)
        self.text = text
        self.border = border
        self.has_border = has_border
        self.halign = halign
        self.valign = valign

    def hit_test(self, col: int, row: int) -> bool:
        if self.has_border:
            return self.bound.contains(col, row)
        return self.bound.contains(col, row) and bool(self.text)

    def render(self, charset: CharSet = CharSet.UNICODE) -> dict[tuple[int, int], str]:
        cells: dict[tuple[int, int], str] = {}
        r = self.rect

        if self.has_border and r.width >= 2 and r.height >= 2:
            tl, tr, bl, br, h, v = BORDER_CHARS[self.border]
            cells[(r.left, r.top)] = tl
            cells[(r.right, r.top)] = tr
            cells[(r.left, r.bottom)] = bl
            cells[(r.right, r.bottom)] = br
            for col in range(r.left + 1, r.right):
                cells[(col, r.top)] = h
                cells[(col, r.bottom)] = h
            for row in range(r.top + 1, r.bottom):
                cells[(r.left, row)] = v
                cells[(r.right, row)] = v

        if self.text:
            inset = 1
            content_left = r.left + inset
            content_top = r.top + inset
            content_width = r.width - 2 * inset
            content_height = r.height - 2 * inset
            lines = self.text.split("\n")[:content_height]

            if self.valign == VAlign.MIDDLE:
                y_offset = (content_height - len(lines)) // 2
            elif self.valign == VAlign.BOTTOM:
                y_offset = content_height - len(lines)
            else:
                y_offset = 0

            for row_idx, line in enumerate(lines):
                visible = line[:content_width]
                if self.halign == HAlign.CENTER:
                    x_offset = (content_width - len(visible)) // 2
                elif self.halign == HAlign.RIGHT:
                    x_offset = content_width - len(visible)
                else:
                    x_offset = 0
                for col_idx, ch in enumerate(visible):
                    if ch != " ":
                        cells[(content_left + x_offset + col_idx, content_top + y_offset + row_idx)] = ch

        return cells
