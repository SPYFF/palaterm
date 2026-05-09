"""Canvas serialization to/from JSON.

The on-disk format is git-friendly:
  * One shape/connector per line for line-localized diffs.
  * Default attribute values are omitted at write time.
  * Keys are abbreviated to 1-2 chars on disk; the in-memory dicts and the
    per-shape (de)serializers keep the full names for readability. Keys are
    translated at the file boundary only.

Single, current format. No version numbering, no backward compat — palaterm
is in early development; old files will not load. Re-create them.

Key cipher (saved to file ↔ used in code):

    geometry          x y w h
    box style         b fl tx ha va rf
    line endpoints    sc sr ec er
    line style        ls se ee ss es sb eb
    connector         lid a tid s r
    common            t id fg bg

Two pairs that look similar at a glance:
  * ``ss`` (start_side) vs ``se`` (start_ending) — values disambiguate
    (``"left"`` vs ``"arrow"``).
  * ``sb`` (start_sub) vs ``b`` (border) — values disambiguate (array vs
    string).
"""

from __future__ import annotations

import json
from pathlib import Path

from .canvas import Canvas
from .connectors import Anchor, Connector, Side
from .geometry import Point, Rect
from .models import (
    BorderStyle, BoxShape, CharSet, EndingStyle, FillStyle, HAlign, VAlign, LineStyle,
    LineShape,
)


# --- key cipher ------------------------------------------------------------
#
# Internal dicts (built by the per-shape serializers, consumed by the
# per-shape deserializers) use the long, readable names. Translation to/from
# the short on-disk keys happens once, at the file boundary.

_LONG_TO_SHORT: dict[str, str] = {
    # box geometry
    "type":   "t",
    "left":   "x",
    "top":    "y",
    "width":  "w",
    "height": "h",
    # box style
    "border": "b",
    "fill":   "fl",
    "text":   "tx",
    "halign": "ha",
    "valign": "va",
    "rect_f": "rf",
    # line endpoints
    "start_col": "sc", "start_row": "sr",
    "end_col":   "ec", "end_row":   "er",
    # line style
    "line_style":   "ls",
    "start_ending": "se",  "end_ending": "ee",
    "start_side":   "ss",  "end_side":   "es",
    "start_sub":    "sb",  "end_sub":    "eb",
    # connector
    "line_id":   "lid",
    "anchor":    "a",
    "target_id": "tid",
    "side":      "s",
    "ratio":     "r",
    # passthrough — already short, no abbreviation worth doing
    "id": "id", "fg": "fg", "bg": "bg",
}

_SHORT_TO_LONG: dict[str, str] = {v: k for k, v in _LONG_TO_SHORT.items()}


def _shorten_keys(d: dict) -> dict:
    return {_LONG_TO_SHORT.get(k, k): v for k, v in d.items()}


def _lengthen_keys(d: dict) -> dict:
    return {_SHORT_TO_LONG.get(k, k): v for k, v in d.items()}


# --- defaults (omitted at save) --------------------------------------------
#
# Keyed on the long, readable JSON field names so the table reads cleanly.
# A serialized shape only includes a key when its value differs from the
# default here. Loaders supply the same default via ``dict.get`` literals.

_BOX_DEFAULTS: dict[str, object] = {
    "border": "light",
    "fill":   "none",
    "text":   "",
    "halign": "left",
    "valign": "top",
}

_LINE_DEFAULTS: dict[str, object] = {
    "border":       "light",
    "line_style":   "orthogonal",
    "start_ending": "none",
    "end_ending":   "none",
}

_CONNECTOR_DEFAULTS: dict[str, object] = {
    # No defaults today: every field carries information. Defined here for
    # symmetry with the shape dicts.
}


def _enum_str(e) -> str:
    return e.name.lower()


_MISSING = object()


def _drop_defaults(d: dict, defaults: dict[str, object]) -> dict:
    """Remove keys whose value equals the default for that field."""
    return {k: v for k, v in d.items() if defaults.get(k, _MISSING) != v}


def _add_colors(d: dict, s) -> dict:
    if s.fg is not None:
        d["fg"] = s.fg
    if s.bg is not None:
        d["bg"] = s.bg
    return d


def _serialize_box(s: BoxShape) -> dict:
    d: dict = {
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
    _add_colors(d, s)
    return _drop_defaults(d, _BOX_DEFAULTS)


def _serialize_line(s: LineShape) -> dict:
    d: dict = {
        "type": "line",
        "id": s.id,
        "start_col": s.start.col, "start_row": s.start.row,
        "end_col": s.end.col, "end_row": s.end.row,
        "border": _enum_str(s.border),
        "line_style": _enum_str(s.line_style),
        "start_ending": _enum_str(s.start_ending),
        "end_ending": _enum_str(s.end_ending),
    }
    if s.start_side:
        d["start_side"] = s.start_side
    if s.end_side:
        d["end_side"] = s.end_side
    if s.start_sub:
        d["start_sub"] = list(s.start_sub)
    if s.end_sub:
        d["end_sub"] = list(s.end_sub)
    _add_colors(d, s)
    return _drop_defaults(d, _LINE_DEFAULTS)


_SERIALIZERS = {
    BoxShape: _serialize_box,
    LineShape: _serialize_line,
}


def _serialize_connector(c: Connector) -> dict:
    d = {
        "line_id": c.line_id,
        "anchor": c.anchor.name.lower(),
        "target_id": c.target_id,
        "side": c.side.name.lower(),
        "ratio": c.ratio,
    }
    return _drop_defaults(d, _CONNECTOR_DEFAULTS)


def _apply_colors(s, d: dict) -> None:
    s.fg = d.get("fg")
    s.bg = d.get("bg")


def _deserialize_box(d: dict) -> BoxShape:
    s = BoxShape(
        Rect(d["left"], d["top"], d["width"], d["height"]),
        text=d.get("text", ""),
        border=BorderStyle[d.get("border", "light").upper()],
        fill=FillStyle[d.get("fill", "none").upper()],
        halign=HAlign[d.get("halign", "left").upper()],
        valign=VAlign[d.get("valign", "top").upper()],
    )
    s.id = d["id"]
    if "rect_f" in d:
        s.rect_f = tuple(d["rect_f"])
    _apply_colors(s, d)
    return s


def _deserialize_line(d: dict) -> LineShape:
    s = LineShape(
        Point(d["start_col"], d["start_row"]),
        Point(d["end_col"], d["end_row"]),
        border=BorderStyle[d.get("border", "light").upper()],
        line_style=LineStyle[d.get("line_style", "orthogonal").upper()],
        start_ending=EndingStyle[d.get("start_ending", "none").upper()],
        end_ending=EndingStyle[d.get("end_ending", "none").upper()],
    )
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


def _emit_jsonl_array(items: list[dict]) -> str:
    """Render a list of dicts as one-element-per-line JSON.

    Output looks like:

        [
          {"a": 1},
          {"b": 2}
        ]

    Empty lists collapse to ``[]`` so trailing-comma issues don't arise.
    """
    if not items:
        return "[]"
    body = ",\n    ".join(json.dumps(item, separators=(",", ":")) for item in items)
    return "[\n    " + body + "\n  ]"


def save_canvas(canvas: Canvas, path: Path, charset: CharSet = CharSet.UNICODE) -> None:
    """Serialize all shapes to a JSON file in the compact, short-keyed format."""
    shapes = []
    for shape in canvas.shapes:
        serializer = _SERIALIZERS.get(type(shape))
        if serializer:
            shapes.append(_shorten_keys(serializer(shape)))
    connectors = [_shorten_keys(_serialize_connector(c))
                  for c in canvas.connector_mgr.connectors]

    parts = [
        "{",
        f'  "charset": {json.dumps(_enum_str(charset))},',
        f'  "shapes": {_emit_jsonl_array(shapes)},',
        f'  "connectors": {_emit_jsonl_array(connectors)}',
        "}",
        "",
    ]
    path.write_text("\n".join(parts))


def load_canvas(path: Path) -> tuple[Canvas, CharSet]:
    """Deserialize shapes from a JSON file. Returns ``(canvas, charset)``."""
    data = json.loads(path.read_text())
    canvas = Canvas()
    for short in data.get("shapes", []):
        d = _lengthen_keys(short)
        deserializer = _DESERIALIZERS.get(d.get("type"))
        if deserializer:
            canvas.add_shape(deserializer(d))
    for short in data.get("connectors", []):
        canvas.connector_mgr.add(_deserialize_connector(_lengthen_keys(short)))
    charset = CharSet[data.get("charset", "unicode").upper()]
    return canvas, charset
