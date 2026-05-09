"""Shape models and enums."""

from .enums import (
    BorderStyle, BORDER_CHARS,
    EndingStyle,
    FillStyle, FILL_CHARS,
    HAlign, VAlign,
    LineStyle,
)
from .base import Shape, RectShape, render_border
from .charset import CharSet, to_ascii, braille_rect, braille_rect_precise
from .box import BoxShape
from .line import LineShape, _braille_line

# Aliases for transition
RectangleShape = BoxShape
TextShape = BoxShape

__all__ = [
    "BorderStyle", "BORDER_CHARS",
    "EndingStyle",
    "FillStyle", "FILL_CHARS",
    "HAlign", "VAlign",
    "LineStyle",
    "Shape", "RectShape",
    "BoxShape",
    "RectangleShape",
    "TextShape",
    "LineShape",
    "braille_rect",
    "braille_rect_precise",
    "CharSet", "to_ascii",
]
