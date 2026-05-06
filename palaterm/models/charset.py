"""Character set mode, Unicode-to-ASCII translation, and braille rendering."""

from __future__ import annotations

import math
from enum import Enum, auto


class CharSet(Enum):
    UNICODE = auto()
    ASCII = auto()


# Blanket fallback: any Unicode char that escapes shape-level ASCII handling
# lands here. Shapes should prefer producing semantically-correct ASCII directly.
_UNICODE_TO_ASCII: dict[str, str] = {
    # Light box-drawing
    "┌": "+", "┐": "+", "└": "+", "┘": "+", "─": "-", "│": "|",
    # Heavy
    "┏": "+", "┓": "+", "┗": "+", "┛": "+", "━": "=", "┃": "|",
    # Double
    "╔": "+", "╗": "+", "╚": "+", "╝": "+", "═": "=", "║": "|",
    # Rounded
    "╭": "+", "╮": "+", "╰": "+", "╯": "+",
    # Crossings
    "┼": "+", "├": "+", "┤": "+", "┬": "+", "┴": "+",
    "╋": "+", "┣": "+", "┫": "+", "┳": "+", "┻": "+",
    "╬": "+", "╠": "+", "╣": "+", "╦": "+", "╩": "+",
    # Half-line (light)
    "╴": "-", "╶": "-", "╵": "|", "╷": "|",
    # Half-line (heavy)
    "╸": "=", "╺": "=", "╹": "|", "╻": "|",
    # Misc
    "•": "*", "□": "#",
    # Fills
    "█": "#", "▒": ":", "░": ".",
}


def to_ascii(ch: str) -> str:
    """Translate a single character to ASCII."""
    if not ch:
        return ch
    # Braille range: any lit dot becomes ".", empty becomes " "
    if "\u2800" <= ch <= "\u28ff":
        return "." if ord(ch) != 0x2800 else " "
    return _UNICODE_TO_ASCII.get(ch, ch if ord(ch) < 128 else "?")


# --- Braille rectangle rendering ---

# Braille edge bits: which dots to light for each edge
_TOP = (1 << 0) | (1 << 3)      # row 0
_BOTTOM = (1 << 6) | (1 << 7)   # row 3
_LEFT = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 6)   # col 0
_RIGHT = (1 << 3) | (1 << 4) | (1 << 5) | (1 << 7)  # col 1


def braille_rect(left: int, top: int, right: int, bottom: int,
                 charset: CharSet = CharSet.UNICODE) -> dict[tuple[int, int], str]:
    """Render a rectangle border using braille edge characters.

    In ASCII mode, falls back to + corners, - and | edges.
    """
    cells: dict[tuple[int, int], int] = {}

    for col in range(left, right + 1):
        for row in range(top, bottom + 1):
            bits = 0
            on_top = row == top
            on_bottom = row == bottom
            on_left = col == left
            on_right = col == right
            if not (on_top or on_bottom or on_left or on_right):
                continue
            if on_top:
                bits |= _TOP
            if on_bottom:
                bits |= _BOTTOM
            if on_left:
                bits |= _LEFT
            if on_right:
                bits |= _RIGHT
            cells[(col, row)] = bits

    if charset == CharSet.ASCII:
        result: dict[tuple[int, int], str] = {}
        for (col, row) in cells:
            on_top = row == top
            on_bottom = row == bottom
            on_left = col == left
            on_right = col == right
            is_corner = (on_top or on_bottom) and (on_left or on_right)
            if is_corner:
                result[(col, row)] = "+"
            elif on_top or on_bottom:
                result[(col, row)] = "-"
            else:
                result[(col, row)] = "|"
        return result

    return {pos: chr(0x2800 | bits) for pos, bits in cells.items()}


# Braille dot index: (sub_x 0-1, sub_y 0-3) -> bit position
_BRAILLE_DOT = {
    (0, 0): 0, (1, 0): 3,
    (0, 1): 1, (1, 1): 4,
    (0, 2): 2, (1, 2): 5,
    (0, 3): 6, (1, 3): 7,
}


def _to_braille_coord(c: float, scale: int) -> int:
    """Map a float cell coord to a braille sub-cell index, flooring negatives correctly."""
    base = math.floor(c)
    frac = c - base
    return base * scale + max(0, min(int(frac * scale), scale - 1))


def braille_rect_precise(left_f: float, top_f: float, right_f: float, bottom_f: float,
                         charset: CharSet = CharSet.UNICODE) -> dict[tuple[int, int], str]:
    """Render a rectangle border using braille with sub-cell precision.

    Float coordinates map fractional parts to braille dots within cells:
    sub_x: <0.5 -> dot col 0, >=0.5 -> dot col 1
    sub_y: quarters 0-3 mapped to dot rows 0-3
    """
    if charset == CharSet.ASCII:
        return braille_rect(math.floor(left_f), math.floor(top_f),
                            math.floor(right_f), math.floor(bottom_f), charset)

    # Convert float coords to braille sub-pixel coords (2x per cell horizontal, 4x vertical)
    bx0 = _to_braille_coord(left_f, 2)
    by0 = _to_braille_coord(top_f, 4)
    bx1 = _to_braille_coord(right_f, 2)
    by1 = _to_braille_coord(bottom_f, 4)

    if bx0 > bx1:
        bx0, bx1 = bx1, bx0
    if by0 > by1:
        by0, by1 = by1, by0

    cells: dict[tuple[int, int], int] = {}

    # Top and bottom edges (horizontal lines)
    for bx in range(bx0, bx1 + 1):
        cell_col, sub_x = divmod(bx, 2)
        # Top edge
        cell_row_t, sub_y_t = divmod(by0, 4)
        key_t = (cell_col, cell_row_t)
        cells[key_t] = cells.get(key_t, 0) | (1 << _BRAILLE_DOT[(sub_x, sub_y_t)])
        # Bottom edge
        cell_row_b, sub_y_b = divmod(by1, 4)
        key_b = (cell_col, cell_row_b)
        cells[key_b] = cells.get(key_b, 0) | (1 << _BRAILLE_DOT[(sub_x, sub_y_b)])

    # Left and right edges (vertical lines)
    for by in range(by0, by1 + 1):
        cell_row, sub_y = divmod(by, 4)
        # Left edge
        cell_col_l, sub_x_l = divmod(bx0, 2)
        key_l = (cell_col_l, cell_row)
        cells[key_l] = cells.get(key_l, 0) | (1 << _BRAILLE_DOT[(sub_x_l, sub_y)])
        # Right edge
        cell_col_r, sub_x_r = divmod(bx1, 2)
        key_r = (cell_col_r, cell_row)
        cells[key_r] = cells.get(key_r, 0) | (1 << _BRAILLE_DOT[(sub_x_r, sub_y)])

    return {pos: chr(0x2800 | bits) for pos, bits in cells.items()}
