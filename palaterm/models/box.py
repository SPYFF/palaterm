"""Box shape: unified rectangle + text shape."""

from __future__ import annotations

import math

from ..geometry import Rect
from .base import RectShape, render_border
from .charset import CharSet, braille_rect, braille_rect_precise
from .enums import BORDER_CHARS, FILL_CHARS, BorderStyle, FillStyle, HAlign, VAlign

# Half-block edge characters for borderless fills (indexed by FillStyle).
# Order: TL, TR, top, BL, BR, bottom, left, right
_HALF_FILL_EDGES: dict[FillStyle, tuple[str, str, str, str, str, str, str, str]] = {
    FillStyle.FULL: ("▗", "▖", "▄", "▝", "▘", "▀", "▐", "▌"),
}


class BoxShape(RectShape):
    def __init__(
        self,
        rect: Rect,
        text: str = "",
        border: BorderStyle = BorderStyle.LIGHT,
        fill: FillStyle = FillStyle.NONE,
        halign: HAlign = HAlign.LEFT,
        valign: VAlign = VAlign.TOP,
    ):
        super().__init__(rect)
        self.text = text
        self.border = border
        self.fill = fill
        self.halign = halign
        self.valign = valign
        self.rect_f: tuple[float, float, float, float] | None = None

    def hit_test(self, col: int, row: int) -> bool:
        if self.border != BorderStyle.NONE:
            return self.bound.contains(col, row)
        if self.fill != FillStyle.NONE:
            return self.bound.contains(col, row)
        return self.bound.contains(col, row) and bool(self.text)

    @property
    def fill_interior(self) -> Rect | None:
        """Return the filled interior rect for occlusion, or None if transparent."""
        if self.fill == FillStyle.NONE:
            return None
        b = self.bound
        if self.border != BorderStyle.NONE and b.width >= 3 and b.height >= 3:
            return Rect(b.left + 1, b.top + 1, b.width - 2, b.height - 2)
        return b

    def _render_impl(
        self, charset: CharSet = CharSet.UNICODE
    ) -> dict[tuple[int, int], str]:
        cells: dict[tuple[int, int], str] = {}
        r = self.rect
        if r.width < 1 or r.height < 1:
            return cells

        # Fill
        if self.fill != FillStyle.NONE:
            fc = FILL_CHARS[self.fill]
            use_half = (
                self.border == BorderStyle.NONE
                and self.fill == FillStyle.FULL
                and r.width >= 3
                and r.height >= 3
                and charset == CharSet.UNICODE
            )
            if use_half:
                edge = _HALF_FILL_EDGES[self.fill]
                for row in range(r.top, r.bottom + 1):
                    for col in range(r.left, r.right + 1):
                        is_top = row == r.top
                        is_bot = row == r.bottom
                        is_left = col == r.left
                        is_right = col == r.right
                        if is_top:
                            if is_left:
                                cells[(col, row)] = edge[0]
                            elif is_right:
                                cells[(col, row)] = edge[1]
                            else:
                                cells[(col, row)] = edge[2]
                        elif is_bot:
                            if is_left:
                                cells[(col, row)] = edge[3]
                            elif is_right:
                                cells[(col, row)] = edge[4]
                            else:
                                cells[(col, row)] = edge[5]
                        elif is_left:
                            cells[(col, row)] = edge[6]
                        elif is_right:
                            cells[(col, row)] = edge[7]
                        else:
                            cells[(col, row)] = fc
            else:
                for row in range(r.top, r.bottom + 1):
                    for col in range(r.left, r.right + 1):
                        cells[(col, row)] = fc

        # Border (braille precision ignored when text is present)
        if self.border != BorderStyle.NONE:
            if self.border == BorderStyle.BRAILLE:
                if self.rect_f is not None and not self.text:
                    lf, tf, rf, bf = self.rect_f
                    cells.update(braille_rect_precise(lf, tf, rf, bf, charset))
                else:
                    cells.update(
                        braille_rect(r.left, r.top, r.right, r.bottom, charset)
                    )
            else:
                if r.width == 1 and r.height == 1:
                    cells[(r.left, r.top)] = "□"
                elif r.width == 1:
                    _, _, _, _, _, v = BORDER_CHARS[self.border]
                    for row in range(r.top, r.bottom + 1):
                        cells[(r.left, row)] = v
                elif r.height == 1:
                    _, _, _, _, h, _ = BORDER_CHARS[self.border]
                    for col in range(r.left, r.right + 1):
                        cells[(col, r.top)] = h
                else:
                    cells.update(render_border(r, self.border))

        # Text
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
                        cells[
                            (
                                content_left + x_offset + col_idx,
                                content_top + y_offset + row_idx,
                            )
                        ] = ch

        return cells

    def move(self, dcol: int, drow: int) -> None:
        super().move(dcol, drow)
        if self.rect_f is not None:
            lf, tf, rf, bf = self.rect_f
            self.rect_f = (lf + dcol, tf + drow, rf + dcol, bf + drow)

    def resize(self, new_rect: Rect) -> None:
        super().resize(new_rect)
        self.rect_f = None

    def resize_f(
        self, left_f: float, top_f: float, right_f: float, bottom_f: float
    ) -> None:
        """Resize with sub-cell precision; keeps integer rect as bounding box."""
        self.rect_f = (
            min(left_f, right_f),
            min(top_f, bottom_f),
            max(left_f, right_f),
            max(top_f, bottom_f),
        )
        lf, tf, rf, bf = self.rect_f
        left = math.floor(lf)
        top = math.floor(tf)
        right = math.floor(rf)
        bottom = math.floor(bf)
        self.rect = Rect(left, top, right - left + 1, bottom - top + 1)
