"""Enums and character mappings for shapes."""

from enum import Enum, auto


class BorderStyle(Enum):
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
