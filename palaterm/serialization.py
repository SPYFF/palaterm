"""Canvas serialization to/from JSON."""

from __future__ import annotations

import json
from pathlib import Path

from .canvas import Canvas
from .connectors import Anchor, Connector, ConnectorManager, Side
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
        "id": s.id,
        "left": s.rect.left, "top": s.rect.top,
        "width": s.rect.width, "height": s.rect.height,
        "border": _enum_str(s.border),
        "fill": _enum_str(s.fill),
    }


def _serialize_text(s: TextShape) -> dict:
    return {
        "type": "text",
        "id": s.id,
        "left": s.rect.left, "top": s.rect.top,
        "width": s.rect.width, "height": s.rect.height,
        "border": _enum_str(s.border),
        "has_border": s.has_border,
        "text": s.text,
        "halign": _enum_str(s.halign),
        "valign": _enum_str(s.valign),
    }


def _serialize_line(s: LineShape) -> dict:
    d = {
        "type": "line",
        "id": s.id,
        "start_col": s.start.col, "start_row": s.start.row,
        "end_col": s.end.col, "end_row": s.end.row,
        "border": _enum_str(s.border),
        "line_style": _enum_str(s.line_style),
    }
    if s.start_side:
        d["start_side"] = s.start_side
    if s.end_side:
        d["end_side"] = s.end_side
    return d


_SERIALIZERS = {
    RectangleShape: _serialize_rectangle,
    TextShape: _serialize_text,
    LineShape: _serialize_line,
}


def _serialize_connector(c: Connector) -> dict:
    return {
        "line_id": c.line_id,
        "anchor": c.anchor.name.lower(),
        "target_id": c.target_id,
        "side": c.side.name.lower(),
        "ratio": c.ratio,
    }


def _deserialize_rectangle(d: dict) -> RectangleShape:
    s = RectangleShape(
        Rect(d["left"], d["top"], d["width"], d["height"]),
        border=BorderStyle[d["border"].upper()],
        fill=FillStyle[d.get("fill", "none").upper()],
    )
    if "id" in d:
        s.id = d["id"]
    return s


def _deserialize_text(d: dict) -> TextShape:
    s = TextShape(
        Rect(d["left"], d["top"], d["width"], d["height"]),
        text=d.get("text", ""),
        border=BorderStyle[d["border"].upper()],
        has_border=d.get("has_border", False),
        halign=HAlign[d.get("halign", "left").upper()],
        valign=VAlign[d.get("valign", "top").upper()],
    )
    if "id" in d:
        s.id = d["id"]
    return s


def _deserialize_line(d: dict) -> LineShape:
    s = LineShape(
        Point(d["start_col"], d["start_row"]),
        Point(d["end_col"], d["end_row"]),
        border=BorderStyle[d["border"].upper()],
        line_style=LineStyle[d.get("line_style", "orthogonal").upper()],
    )
    if "id" in d:
        s.id = d["id"]
    if "start_side" in d:
        s.start_side = d["start_side"]
    if "end_side" in d:
        s.end_side = d["end_side"]
    s._recompute()
    return s


def _deserialize_connector(d: dict) -> Connector:
    return Connector(
        line_id=d["line_id"],
        anchor=Anchor[d["anchor"].upper()],
        target_id=d["target_id"],
        side=Side[d["side"].upper()],
        ratio=d["ratio"],
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
    connectors = [_serialize_connector(c) for c in canvas.connector_mgr.connectors]
    data = {
        "version": 2,
        "charset": _enum_str(charset),
        "shapes": shapes,
        "connectors": connectors,
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
    # Load connectors (v2+)
    for d in data.get("connectors", []):
        canvas.connector_mgr.add(_deserialize_connector(d))
    charset = CharSet[data.get("charset", "unicode").upper()]
    return canvas, charset
