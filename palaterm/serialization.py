"""Canvas serialization to/from JSON.

The on-disk format is git-friendly:
  * One shape/connector per line for line-localized diffs.
  * Default attribute values are omitted at write time.
  * Keys are abbreviated to 1-2 chars on disk; the in-memory dicts and the
    per-shape (de)serializers keep the full names for readability.
  * Enum values are 1-char codes, decoded per-field (the same letter
    means different things in different fields).
  * Geometry collapses into a single tuple per shape.

Shape order on disk = ``Canvas.shapes`` insertion order = z-order. Diffs
under structural churn (delete/add) shift the line numbers of surviving
shapes, but git's diff algorithm reports them as a single hunk anyway —
``scripts/bench_serialize.py`` confirms this. Sorting on disk by id
produced more diff noise in practice (z-field churn), so we keep
insertion order.

Translation (key abbreviation + enum encoding) happens once at the file
boundary.

Single, current format. No version numbering, no backward compat —
palaterm is in early development; old files will not load.

Key cipher (saved file ↔ source code):

    common            t id fg bg
    box geometry      g  → [left, top, width, height]
    box style         b fl tx ha va rf
    line endpoints    e  → [start_col, start_row, end_col, end_row]
    line style        ls se ee ss es sb eb
    line joints       j em
    connector         lid a tid s r

Value cipher (per field, defaults are omitted entirely):

    border         H=heavy  D=double  R=rounded  B=braille  N=none
                   (default: light)
    fill           L=light  M=medium  F=full  _=space
                   (default: none)
    halign         c=center r=right                 (default: left)
    valign         m=middle b=bottom                (default: top)
    line_style     s=straight                       (default: orthogonal)
    start_ending,  a=arrow s=square c=circle *=star (default: none)
    end_ending
    start_side,    l=left r=right t=top b=bottom    (no default)
    end_side, side
    anchor         s=start e=end                    (no default)
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from .canvas import Canvas
from .connectors import Anchor, Connector, Side
from .geometry import Point, Rect
from .models import (
    BorderStyle, BoxShape, CharSet, EndingStyle, FillStyle, HAlign, VAlign, LineStyle,
    LineShape,
)


# --- key cipher ------------------------------------------------------------

_LONG_TO_SHORT: dict[str, str] = {
    # common
    "type": "t", "id": "id", "fg": "fg", "bg": "bg",
    # box geometry (single tuple) and style
    "rect":   "g",   # [left, top, width, height]
    "border": "b",
    "fill":   "fl",
    "text":   "tx",
    "halign": "ha",
    "valign": "va",
    "rect_f": "rf",
    # line endpoints (single tuple) and style
    "endpoints":    "e",   # [start_col, start_row, end_col, end_row]
    "line_style":   "ls",
    "start_ending": "se",  "end_ending": "ee",
    "start_side":   "ss",  "end_side":   "es",
    "start_sub":    "sb",  "end_sub":    "eb",
    "joints":         "j",
    "edges_modified": "em",
    # connector
    "line_id":   "lid",
    "anchor":    "a",
    "target_id": "tid",
    "side":      "s",
    "ratio":     "r",
}

_SHORT_TO_LONG: dict[str, str] = {v: k for k, v in _LONG_TO_SHORT.items()}


def _shorten_keys(d: dict) -> dict:
    return {_LONG_TO_SHORT.get(k, k): v for k, v in d.items()}


def _lengthen_keys(d: dict) -> dict:
    return {_SHORT_TO_LONG.get(k, k): v for k, v in d.items()}


# --- value cipher ----------------------------------------------------------
#
# Field-aware: the same letter can mean different things in different fields.
# Inner dicts map the in-memory enum instance to the on-disk 1-char string.

_VALUE_CIPHERS: dict[str, dict[Enum, str]] = {
    "border": {
        BorderStyle.NONE: "N", BorderStyle.HEAVY: "H",
        BorderStyle.DOUBLE: "D", BorderStyle.ROUNDED: "R",
        BorderStyle.BRAILLE: "B",
        # BorderStyle.LIGHT is the default; never appears on disk.
    },
    "fill": {
        FillStyle.SPACE: "_", FillStyle.FULL: "F",
        FillStyle.MEDIUM: "M", FillStyle.LIGHT: "L",
        # FillStyle.NONE is the default.
    },
    "halign": {HAlign.CENTER: "c", HAlign.RIGHT: "r"},
    "valign": {VAlign.MIDDLE: "m", VAlign.BOTTOM: "b"},
    "line_style": {LineStyle.STRAIGHT: "s"},
    "start_ending": {
        EndingStyle.ARROW: "a", EndingStyle.SQUARE: "s",
        EndingStyle.CIRCLE: "c", EndingStyle.STAR: "*",
    },
    "end_ending": {
        EndingStyle.ARROW: "a", EndingStyle.SQUARE: "s",
        EndingStyle.CIRCLE: "c", EndingStyle.STAR: "*",
    },
    "anchor": {Anchor.START: "s", Anchor.END: "e"},
    "side": {
        Side.LEFT: "l", Side.RIGHT: "r",
        Side.TOP: "t", Side.BOTTOM: "b",
    },
    # start_side / end_side are stored on LineShape as already-lowercased
    # strings ("left"/"right"/"top"/"bottom"), not Side enum members. They
    # get a separate cipher keyed on the string value.
    "start_side": {"left": "l", "right": "r", "top": "t", "bottom": "b"},  # type: ignore[dict-item]
    "end_side":   {"left": "l", "right": "r", "top": "t", "bottom": "b"},  # type: ignore[dict-item]
}

_VALUE_CIPHERS_INV: dict[str, dict[str, object]] = {
    field: {short: long for long, short in cipher.items()}
    for field, cipher in _VALUE_CIPHERS.items()
}


def _encode_values(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        cipher = _VALUE_CIPHERS.get(k)
        if cipher is not None and v in cipher:
            out[k] = cipher[v]
        else:
            out[k] = v
    return out


def _decode_values(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        inv = _VALUE_CIPHERS_INV.get(k)
        if inv is not None and v in inv:
            out[k] = inv[v]
        else:
            out[k] = v
    return out


# --- defaults (omitted at save) --------------------------------------------
#
# Values are enum *instances*, not strings — so they compare equal to the
# values that the per-shape serializers put into the working dict.

_BOX_DEFAULTS: dict[str, object] = {
    "border": BorderStyle.LIGHT,
    "fill":   FillStyle.NONE,
    "text":   "",
    "halign": HAlign.LEFT,
    "valign": VAlign.TOP,
}

_LINE_DEFAULTS: dict[str, object] = {
    "border":       BorderStyle.LIGHT,
    "line_style":   LineStyle.ORTHOGONAL,
    "start_ending": EndingStyle.NONE,
    "end_ending":   EndingStyle.NONE,
}

_CONNECTOR_DEFAULTS: dict[str, object] = {}


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
        "rect": [s.rect.left, s.rect.top, s.rect.width, s.rect.height],
        "border": s.border,
        "fill": s.fill,
        "text": s.text,
        "halign": s.halign,
        "valign": s.valign,
    }
    if s.rect_f is not None:
        # Pointer floats serialize to full 17-digit repr by default. Render
        # resolution is 1/4 of a cell (braille sub-rows), so 4 decimals is
        # already overkill — keeps `rect_f` short on disk without losing any
        # visible precision.
        d["rect_f"] = [round(v, 4) for v in s.rect_f]
    _add_colors(d, s)
    return _drop_defaults(d, _BOX_DEFAULTS)


def _serialize_line(s: LineShape) -> dict:
    d: dict = {
        "type": "line",
        "id": s.id,
        "endpoints": [s.start.col, s.start.row, s.end.col, s.end.row],
        "border": s.border,
        "line_style": s.line_style,
        "start_ending": s.start_ending,
        "end_ending": s.end_ending,
    }
    if s.start_side:
        d["start_side"] = s.start_side
    if s.end_side:
        d["end_side"] = s.end_side
    if s.start_sub:
        d["start_sub"] = list(s.start_sub)
    if s.end_sub:
        d["end_sub"] = list(s.end_sub)
    if s.edges_modified:
        d["edges_modified"] = True
        d["joints"] = [[p.col, p.row] for p in s.joint_points]
    _add_colors(d, s)
    return _drop_defaults(d, _LINE_DEFAULTS)


_SERIALIZERS = {
    BoxShape: _serialize_box,
    LineShape: _serialize_line,
}


def _serialize_connector(c: Connector) -> dict:
    d = {
        "line_id": c.line_id,
        "anchor": c.anchor,
        "target_id": c.target_id,
        "side": c.side,
        # Ratio resolves to integer cell positions on the target's edge
        # (round(ratio * (height-1))), so 4 decimals is well below the
        # smallest meaningful step.
        "ratio": round(c.ratio, 4),
    }
    return _drop_defaults(d, _CONNECTOR_DEFAULTS)


def _apply_colors(s, d: dict) -> None:
    s.fg = d.get("fg")
    s.bg = d.get("bg")


def _deserialize_box(d: dict) -> BoxShape:
    left, top, width, height = d["rect"]
    s = BoxShape(
        Rect(left, top, width, height),
        text=d.get("text", ""),
        border=d.get("border", BorderStyle.LIGHT),
        fill=d.get("fill", FillStyle.NONE),
        halign=d.get("halign", HAlign.LEFT),
        valign=d.get("valign", VAlign.TOP),
    )
    s.id = d["id"]
    if "rect_f" in d:
        s.rect_f = tuple(d["rect_f"])
    _apply_colors(s, d)
    return s


def _deserialize_line(d: dict) -> LineShape:
    sc, sr, ec, er = d["endpoints"]
    s = LineShape(
        Point(sc, sr), Point(ec, er),
        border=d.get("border", BorderStyle.LIGHT),
        line_style=d.get("line_style", LineStyle.ORTHOGONAL),
        start_ending=d.get("start_ending", EndingStyle.NONE),
        end_ending=d.get("end_ending", EndingStyle.NONE),
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
    if d.get("edges_modified") and d.get("joints"):
        s._joint_points = [Point(c, r) for c, r in d["joints"]]
        s._edges_modified = True
        s.start = s._joint_points[0]
        s.end = s._joint_points[-1]
    else:
        s._recompute()
    return s


def _deserialize_connector(d: dict) -> Connector:
    return Connector(
        line_id=d["line_id"],
        anchor=d["anchor"],
        target_id=d["target_id"],
        side=d["side"],
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


def _enum_str(e: Enum) -> str:
    return e.name.lower()


def save_canvas(canvas: Canvas, path: Path, charset: CharSet = CharSet.UNICODE) -> None:
    """Serialize all shapes to a JSON file in the compact, short-keyed format."""
    shapes = []
    for shape in canvas.shapes:
        serializer = _SERIALIZERS.get(type(shape))
        if serializer:
            shapes.append(_shorten_keys(_encode_values(serializer(shape))))
    connectors = [_shorten_keys(_encode_values(_serialize_connector(c)))
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
        d = _decode_values(_lengthen_keys(short))
        deserializer = _DESERIALIZERS.get(d.get("type"))
        if deserializer:
            canvas.add_shape(deserializer(d))
    for short in data.get("connectors", []):
        canvas.connector_mgr.add(_deserialize_connector(_decode_values(_lengthen_keys(short))))
    charset = CharSet[data.get("charset", "unicode").upper()]
    return canvas, charset
