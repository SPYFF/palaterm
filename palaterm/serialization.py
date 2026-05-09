"""Canvas serialization to/from JSON."""

from __future__ import annotations

import json
from pathlib import Path

from .canvas import Canvas
from .connectors import Anchor, Connector, ConnectorManager, Side
from .geometry import Point, Rect
from .models import (
    BorderStyle, BoxShape, CharSet, EndingStyle, FillStyle, HAlign, VAlign, LineStyle,
    LineShape,
)


def _enum_str(e) -> str:
    return e.name.lower()


def _add_colors(d: dict, s) -> dict:
    if s.fg is not None:
        d["fg"] = s.fg
    if s.bg is not None:
        d["bg"] = s.bg
    return d


def _serialize_box(s: BoxShape) -> dict:
    d = {
        "type": "box",
        "id": s.id,
        "left": s.rect.left, "top": s.rect.top,
        "width": s.rect.width, "height": s.rect.height,
        "border": _enum_str(s.border),
        "fill": _enum_str(s.fill),
        "text": s.text,
        "halign": _enum_str(s.halign),
        "valign": _enum_str(s.valign),
    }
    if s.rect_f is not None:
        d["rect_f"] = list(s.rect_f)
    return _add_colors(d, s)


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
    if s.start_ending != EndingStyle.NONE:
        d["start_ending"] = _enum_str(s.start_ending)
    if s.end_ending != EndingStyle.NONE:
        d["end_ending"] = _enum_str(s.end_ending)
    if s.start_sub:
        d["start_sub"] = list(s.start_sub)
    if s.end_sub:
        d["end_sub"] = list(s.end_sub)
    return _add_colors(d, s)


_SERIALIZERS = {
    BoxShape: _serialize_box,
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


def _apply_colors(s, d: dict) -> None:
    s.fg = d.get("fg")
    s.bg = d.get("bg")


def _deserialize_box(d: dict) -> BoxShape:
    s = BoxShape(
        Rect(d["left"], d["top"], d["width"], d["height"]),
        text=d.get("text", ""),
        border=BorderStyle[d["border"].upper()],
        fill=FillStyle[d.get("fill", "none").upper()],
        halign=HAlign[d.get("halign", "left").upper()],
        valign=VAlign[d.get("valign", "top").upper()],
    )
    if "id" in d:
        s.id = d["id"]
    if "rect_f" in d:
        s.rect_f = tuple(d["rect_f"])
    _apply_colors(s, d)
    return s


def _deserialize_line(d: dict) -> LineShape:
    s = LineShape(
        Point(d["start_col"], d["start_row"]),
        Point(d["end_col"], d["end_row"]),
        border=BorderStyle[d["border"].upper()],
        line_style=LineStyle[d.get("line_style", "orthogonal").upper()],
        start_ending=EndingStyle[d.get("start_ending", "none").upper()],
        end_ending=EndingStyle[d.get("end_ending", "none").upper()],
    )
    if "id" in d:
        s.id = d["id"]
    if "start_side" in d:
        s.start_side = d["start_side"]
    if "end_side" in d:
        s.end_side = d["end_side"]
    if "start_sub" in d:
        s.start_sub = tuple(d["start_sub"])
    if "end_sub" in d:
        s.end_sub = tuple(d["end_sub"])
    _apply_colors(s, d)
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
    "box": _deserialize_box,
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
        "version": 4,
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
    for d in data.get("connectors", []):
        canvas.connector_mgr.add(_deserialize_connector(d))
    charset = CharSet[data.get("charset", "unicode").upper()]
    return canvas, charset
