"""Unified compositor: merges shapes into a styled character grid."""

from __future__ import annotations

from .crossings import (
    _DB,
    _DL,
    _DR,
    _DT,
    _HB,
    _HL,
    _HR,
    _HT,
    _SB,
    _SL,
    _SR,
    _ST,
    is_connectable,
    resolve_crossing,
    resolve_crossing_masked,
)
from .geometry import Rect
from .models import CharSet, Shape, to_ascii

# Blocked-direction masks covering all weight tiers for a given direction.
_BLOCK_T = _ST | _HT | _DT
_BLOCK_B = _SB | _HB | _DB
_BLOCK_L = _SL | _HL | _DL
_BLOCK_R = _SR | _HR | _DR

# Block element 2x2 sub-pixel merging (quadrant characters).
# Each cell is divided into 4 quadrants: TL=1, BL=2, TR=4, BR=8.
_BLOCK_CHAR_TO_MASK: dict[str, int] = {
    " ": 0b0000,
    "▘": 0b0001,
    "▖": 0b0010,
    "▌": 0b0011,
    "▝": 0b0100,
    "▀": 0b0101,
    "▞": 0b0110,
    "▛": 0b0111,
    "▗": 0b1000,
    "▚": 0b1001,
    "▄": 0b1010,
    "▙": 0b1011,
    "▐": 0b1100,
    "▜": 0b1101,
    "▟": 0b1110,
    "█": 0b1111,
}
_BLOCK_MASK_TO_CHAR: dict[int, str] = {v: k for k, v in _BLOCK_CHAR_TO_MASK.items()}


def _is_block_element(ch: str) -> bool:
    return ch in _BLOCK_CHAR_TO_MASK and ch != " "


def _merge_blocks(existing: str, new: str) -> str:
    mask = _BLOCK_CHAR_TO_MASK.get(existing, 0) | _BLOCK_CHAR_TO_MASK.get(new, 0)
    return _BLOCK_MASK_TO_CHAR.get(mask, new)


def composite(
    shapes: list[Shape],
    region: Rect,
    charset: CharSet = CharSet.UNICODE,
) -> dict[tuple[int, int], tuple[str, str | None, str | None]]:
    """Composite *shapes* within *region* into ``{(col, row): (char, fg, bg)}``.

    Implements painter's algorithm (bottom-to-top z-order) with:
    - Occlusion: shapes with fill != NONE hide shapes below in their interior
    - T-junction awareness: border intersections with occluding fills produce
      T-junctions instead of full crosses
    - Block-element merging: overlapping quadrant characters OR their bits
    - Cell ownership: the topmost shape writing a cell owns its style entirely
    """
    cells: dict[tuple[int, int], tuple[str, str | None, str | None]] = {}
    r_left, r_top, r_right, r_bottom = (
        region.left,
        region.top,
        region.right,
        region.bottom,
    )

    for shape in shapes:
        b = shape.bound
        if b.right < r_left or b.left > r_right or b.bottom < r_top or b.top > r_bottom:
            continue

        # Determine occlusion via the shape's fill_interior property.
        fill_rect = shape.fill_interior

        # Compute fill interior bounds for T-junction checks
        fill_left = fill_top = fill_right = fill_bottom = 0
        if fill_rect is not None:
            fill_left = fill_rect.left
            fill_top = fill_rect.top
            fill_right = fill_rect.right
            fill_bottom = fill_rect.bottom

        fg, bg = shape.fg, shape.bg

        for (col, row), ch in shape.render(charset).items():
            if not (r_left <= col <= r_right and r_top <= row <= r_bottom):
                continue
            pos = (col, row)
            existing = cells.get(pos)
            if existing and is_connectable(existing[0]) and is_connectable(ch):
                if fill_rect is not None:
                    blocked = 0
                    if fill_left <= col <= fill_right:
                        if fill_top <= row - 1 <= fill_bottom:
                            blocked |= _BLOCK_T
                        if fill_top <= row + 1 <= fill_bottom:
                            blocked |= _BLOCK_B
                    if fill_top <= row <= fill_bottom:
                        if fill_left <= col - 1 <= fill_right:
                            blocked |= _BLOCK_L
                        if fill_left <= col + 1 <= fill_right:
                            blocked |= _BLOCK_R
                    ch = resolve_crossing_masked(existing[0], ch, blocked)
                else:
                    ch = resolve_crossing(existing[0], ch)
            elif existing and _is_block_element(existing[0]) and _is_block_element(ch):
                ch = _merge_blocks(existing[0], ch)
            cells[pos] = (ch, fg, bg)

    if charset == CharSet.ASCII:
        cells = {pos: (to_ascii(ch), fg, bg) for pos, (ch, fg, bg) in cells.items()}
    return cells
