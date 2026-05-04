"""Canvas serialization to/from JSON."""

from __future__ import annotations

import json
from pathlib import Path

from .canvas import Canvas
from .geometry import Point, Rect
from .models import (
    BorderStyle, CharSet, FillStyle, HAlign, VAlign, LineStyle,
    RectangleShape, TextShape, LineShape,
)


def _enum_str(e) -> str:
    return e.name.lower()


def _serialize_rectangle(s: RectangleShape) -> dict:
    return {
        "type": "rectangle",
        "left": s.rect.left, "top": s.rect.top,
        "width": s.rect.width, "height": s.rect.height,
        "border": _enum_str(s.border),
        "fill": _enum_str(s.fill),
    }


def _serialize_text(s: TextShape) -> dict:
    return {
        "type": "text",
        "left": s.rect.left, "top": s.rect.top,
        "width": s.rect.width, "height": s.rect.height,
        "border": _enum_str(s.border),
        "has_border": s.has_border,
        "text": s.text,
        "halign": _enum_str(s.halign),
        "valign": _enum_str(s.valign),
    }


def _serialize_line(s: LineShape) -> dict:
    return {
        "type": "line",
        "start_col": s.start.col, "start_row": s.start.row,
        "end_col": s.end.col, "end_row": s.end.row,
        "border": _enum_str(s.border),
        "line_style": _enum_str(s.line_style),
    }


_SERIALIZERS = {
    RectangleShape: _serialize_rectangle,
    TextShape: _serialize_text,
    LineShape: _serialize_line,
}


def _deserialize_rectangle(d: dict) -> RectangleShape:
    return RectangleShape(
        Rect(d["left"], d["top"], d["width"], d["height"]),
        border=BorderStyle[d["border"].upper()],
        fill=FillStyle[d.get("fill", "none").upper()],
    )


def _deserialize_text(d: dict) -> TextShape:
    return TextShape(
        Rect(d["left"], d["top"], d["width"], d["height"]),
        text=d.get("text", ""),
        border=BorderStyle[d["border"].upper()],
        has_border=d.get("has_border", False),
        halign=HAlign[d.get("halign", "left").upper()],
        valign=VAlign[d.get("valign", "top").upper()],
    )


def _deserialize_line(d: dict) -> LineShape:
    return LineShape(
        Point(d["start_col"], d["start_row"]),
        Point(d["end_col"], d["end_row"]),
        border=BorderStyle[d["border"].upper()],
        line_style=LineStyle[d.get("line_style", "orthogonal").upper()],
    )


_DESERIALIZERS = {
    "rectangle": _deserialize_rectangle,
    "text": _deserialize_text,
    "line": _deserialize_line,
}


def save_canvas(canvas: Canvas, path: Path, charset: CharSet = CharSet.UNICODE) -> None:
    """Serialize all shapes to a JSON file."""
    shapes = []
    for shape in canvas.shapes:
        serializer = _SERIALIZERS.get(type(shape))
        if serializer:
            shapes.append(serializer(shape))
    data = {
        "version": 1,
        "charset": _enum_str(charset),
        "shapes": shapes,
    }
    path.write_text(json.dumps(data, indent=2))


def load_canvas(path: Path) -> tuple[Canvas, CharSet]:
    """Deserialize shapes from a JSON file. Returns (canvas, charset)."""
    data = json.loads(path.read_text())
    canvas = Canvas()
    for d in data.get("shapes", []):
        deserializer = _DESERIALIZERS.get(d.get("type"))
        if deserializer:
            canvas.add_shape(deserializer(d))
    charset = CharSet[data.get("charset", "unicode").upper()]
    return canvas, charset
