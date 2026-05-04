"""Braille rectangle rendering."""

from .charset import CharSet

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

