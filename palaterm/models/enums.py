"""Enums and character mappings for shapes."""

from enum import Enum, auto


class BorderStyle(Enum):
    NONE = auto()
    LIGHT = auto()
    HEAVY = auto()
    DOUBLE = auto()
    ROUNDED = auto()
    BRAILLE = auto()


BORDER_CHARS: dict[BorderStyle, tuple[str, str, str, str, str, str]] = {
    BorderStyle.LIGHT: ("┌", "┐", "└", "┘", "─", "│"),
    BorderStyle.HEAVY: ("┏", "┓", "┗", "┛", "━", "┃"),
    BorderStyle.DOUBLE: ("╔", "╗", "╚", "╝", "═", "║"),
    BorderStyle.ROUNDED: ("╭", "╮", "╰", "╯", "─", "│"),
}


class HAlign(Enum):
    LEFT = auto()
    CENTER = auto()
    RIGHT = auto()


class VAlign(Enum):
    TOP = auto()
    MIDDLE = auto()
    BOTTOM = auto()


class LineStyle(Enum):
    ORTHOGONAL = auto()
    STRAIGHT = auto()


class FillStyle(Enum):
    NONE = auto()
    SPACE = auto()
    FULL = auto()
    MEDIUM = auto()
    LIGHT = auto()


FILL_CHARS: dict[FillStyle, str] = {
    FillStyle.NONE: "",
    FillStyle.SPACE: " ",
    FillStyle.FULL: "█",
    FillStyle.MEDIUM: "▒",
    FillStyle.LIGHT: "░",
}


class EndingStyle(Enum):
    NONE = auto()
    ARROW = auto()
    SQUARE = auto()
    CIRCLE = auto()
    STAR = auto()


class Direction(Enum):
    N = auto()
    S = auto()
    E = auto()
    W = auto()
    NE = auto()
    NW = auto()
    SE = auto()
    SW = auto()


# Arrow characters per direction (Unicode)
# Only 4 triangle glyphs exist (▲▼◀▶), so diagonals map to the nearest
# visual match. Multiple directions sharing a character is intentional.
ARROW_CHARS: dict[Direction, str] = {
    Direction.N: "▲", Direction.S: "▼",
    Direction.E: "▶", Direction.W: "◀",
    Direction.NE: "◀", Direction.NW: "▶",
    Direction.SE: "◀", Direction.SW: "▶",
}

# Arrow characters per direction (ASCII)
ARROW_CHARS_ASCII: dict[Direction, str] = {
    Direction.N: "^", Direction.S: "v",
    Direction.E: ">", Direction.W: "<",
    Direction.NE: "<", Direction.NW: ">",
    Direction.SE: "^", Direction.SW: ">",
}

# Non-directional ending characters
ENDING_CHARS: dict[EndingStyle, tuple[str, str]] = {
    # (unicode, ascii)
    EndingStyle.SQUARE: ("■", "#"),
    EndingStyle.CIRCLE: ("●", "o"),
    EndingStyle.STAR: ("*", "*"),
}
