"""Shape models and enums."""

from .base import RectShape, Shape, render_border
from .box import BoxShape
from .charset import CharSet, braille_rect, braille_rect_precise, to_ascii
from .enums import (
    BORDER_CHARS,
    FILL_CHARS,
    BorderStyle,
    EndingStyle,
    FillStyle,
    HAlign,
    LineStyle,
    VAlign,
)
from .line import LineShape, _braille_line

# Aliases for transition
RectangleShape = BoxShape
TextShape = BoxShape

__all__ = [
    "BorderStyle",
    "BORDER_CHARS",
    "EndingStyle",
    "FillStyle",
    "FILL_CHARS",
    "HAlign",
    "VAlign",
    "LineStyle",
    "Shape",
    "RectShape",
    "BoxShape",
    "RectangleShape",
    "TextShape",
    "LineShape",
    "_braille_line",
    "render_border",
    "braille_rect",
    "braille_rect_precise",
    "CharSet",
    "to_ascii",
]
