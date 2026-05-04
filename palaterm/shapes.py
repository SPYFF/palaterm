"""Backward-compatible re-exports from models package."""

from .models import (
    BorderStyle, BORDER_CHARS,
    FillStyle, FILL_CHARS,
    HAlign, VAlign,
    LineStyle,
    Shape, RectShape,
    RectangleShape,
    TextShape,
    LineShape, _braille_line,
    braille_rect,
    CharSet, to_ascii,
)

__all__ = [
    "BorderStyle", "BORDER_CHARS",
    "FillStyle", "FILL_CHARS",
    "HAlign", "VAlign",
    "LineStyle",
    "Shape", "RectShape",
    "RectangleShape",
    "TextShape",
    "LineShape", "_braille_line",
    "braille_rect",
    "CharSet", "to_ascii",
]
