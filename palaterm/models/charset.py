"""Character set mode and Unicode-to-ASCII translation."""

from __future__ import annotations

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
