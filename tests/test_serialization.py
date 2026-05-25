"""Tests for the .palaterm save format.

Covers idempotence, round-trip preservation, byte-stability, the
short-key format, and per-enum value-cipher coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from palaterm.canvas import Canvas
from palaterm.connectors import Anchor, Connector, Side
from palaterm.geometry import Point, Rect
from palaterm.models import (
    BorderStyle,
    BoxShape,
    CharSet,
    EndingStyle,
    FillStyle,
    HAlign,
    LineShape,
    LineStyle,
    VAlign,
)
from palaterm.serialization import load_canvas, save_canvas


def test_idempotent_save(fixed_canvas: Canvas, tmp_path: Path) -> None:
    """Saving the same canvas twice must produce byte-identical files."""
    a = tmp_path / "a.palaterm"
    b = tmp_path / "b.palaterm"
    save_canvas(fixed_canvas, a, CharSet.UNICODE)
    save_canvas(fixed_canvas, b, CharSet.UNICODE)
    assert a.read_bytes() == b.read_bytes()


def test_round_trip_byte_stable(fixed_canvas: Canvas, tmp_path: Path) -> None:
    """save → load → save must be byte-stable (no information drift)."""
    a = tmp_path / "a.palaterm"
    b = tmp_path / "b.palaterm"
    save_canvas(fixed_canvas, a, CharSet.UNICODE)
    loaded, charset = load_canvas(a)
    save_canvas(loaded, b, charset)
    assert a.read_bytes() == b.read_bytes()


def test_round_trip_preserves_shape_count(fixed_canvas: Canvas, tmp_path: Path) -> None:
    a = tmp_path / "a.palaterm"
    save_canvas(fixed_canvas, a, CharSet.UNICODE)
    loaded, _ = load_canvas(a)
    assert len(loaded.shapes) == len(fixed_canvas.shapes)
    assert len(loaded.connector_mgr.connectors) == len(
        fixed_canvas.connector_mgr.connectors
    )


def test_round_trip_preserves_box_attributes(
    fixed_canvas: Canvas, tmp_path: Path
) -> None:
    a = tmp_path / "a.palaterm"
    save_canvas(fixed_canvas, a, CharSet.UNICODE)
    loaded, _ = load_canvas(a)

    by_id_orig = {s.id: s for s in fixed_canvas.shapes}
    by_id_load = {s.id: s for s in loaded.shapes}

    for sid, orig in by_id_orig.items():
        if not isinstance(orig, BoxShape):
            continue
        load = by_id_load[sid]
        assert isinstance(load, BoxShape)
        assert load.rect == orig.rect, sid
        assert load.text == orig.text, sid
        assert load.border is orig.border, sid
        assert load.fill is orig.fill, sid
        assert load.halign is orig.halign, sid
        assert load.valign is orig.valign, sid
        assert load.fg == orig.fg, sid
        assert load.bg == orig.bg, sid
        # rect_f is rounded to 4 decimals on save (well below braille's
        # 1/4-cell rendering resolution). Compare with that precision.
        if orig.rect_f is None:
            assert load.rect_f is None, sid
        else:
            assert load.rect_f is not None, sid
            for o, ld in zip(orig.rect_f, load.rect_f):
                assert ld == pytest.approx(round(o, 4), abs=1e-9), sid


def test_round_trip_preserves_line_attributes(
    fixed_canvas: Canvas, tmp_path: Path
) -> None:
    a = tmp_path / "a.palaterm"
    save_canvas(fixed_canvas, a, CharSet.UNICODE)
    loaded, _ = load_canvas(a)

    by_id_orig = {s.id: s for s in fixed_canvas.shapes}
    by_id_load = {s.id: s for s in loaded.shapes}

    for sid, orig in by_id_orig.items():
        if not isinstance(orig, LineShape):
            continue
        load = by_id_load[sid]
        assert isinstance(load, LineShape)
        assert load.start == orig.start, sid
        assert load.end == orig.end, sid
        assert load.border is orig.border, sid
        assert load.line_style is orig.line_style, sid
        assert load.start_ending is orig.start_ending, sid
        assert load.end_ending is orig.end_ending, sid
        assert load.start_sub == orig.start_sub, sid
        assert load.end_sub == orig.end_sub, sid


def test_round_trip_preserves_connectors(fixed_canvas: Canvas, tmp_path: Path) -> None:
    a = tmp_path / "a.palaterm"
    save_canvas(fixed_canvas, a, CharSet.UNICODE)
    loaded, _ = load_canvas(a)

    orig = fixed_canvas.connector_mgr.connectors
    load = loaded.connector_mgr.connectors
    assert len(load) == len(orig)
    by_key_orig = {(c.line_id, c.anchor.name): c for c in orig}
    by_key_load = {(c.line_id, c.anchor.name): c for c in load}
    for key, oc in by_key_orig.items():
        lc = by_key_load[key]
        assert lc.target_id == oc.target_id
        assert lc.side is oc.side
        # Saved ratio is rounded to 4 decimals; compare with that precision.
        assert lc.ratio == pytest.approx(round(oc.ratio, 4), abs=1e-9)


def test_save_empty_canvas(empty_canvas: Canvas, tmp_path: Path) -> None:
    a = tmp_path / "empty.palaterm"
    save_canvas(empty_canvas, a, CharSet.UNICODE)
    data = json.loads(a.read_text())
    assert data["shapes"] == []
    assert data["connectors"] == []
    # Loading produces an equally empty canvas.
    loaded, charset = load_canvas(a)
    assert loaded.shapes == []
    assert loaded.connector_mgr.connectors == []
    assert charset is CharSet.UNICODE


def test_short_keys_in_output(fixed_canvas: Canvas, tmp_path: Path) -> None:
    """Guard against accidentally re-introducing long keys in the format."""
    a = tmp_path / "a.palaterm"
    save_canvas(fixed_canvas, a, CharSet.UNICODE)
    text = a.read_text()
    # Common short keys must appear.
    assert '"t":"box"' in text
    assert '"id":"s00"' in text
    assert '"g":[' in text  # box geometry tuple
    assert '"e":[' in text  # line endpoints tuple
    # Long keys must NOT appear.
    assert '"type":' not in text
    assert '"left":' not in text
    assert '"start_col":' not in text
    assert '"line_style":' not in text


@pytest.mark.parametrize("border", list(BorderStyle))
def test_box_round_trip_every_border(border: BorderStyle, tmp_path: Path) -> None:
    c = Canvas()
    box = BoxShape(Rect(0, 0, 4, 3), border=border)
    box.id = "b0"
    c.add_shape(box)
    a = tmp_path / "x.palaterm"
    save_canvas(c, a, CharSet.UNICODE)
    loaded, _ = load_canvas(a)
    out = loaded.shapes[0]
    assert isinstance(out, BoxShape)
    assert out.border is border


@pytest.mark.parametrize("fill", list(FillStyle))
def test_box_round_trip_every_fill(fill: FillStyle, tmp_path: Path) -> None:
    c = Canvas()
    box = BoxShape(Rect(0, 0, 4, 3), fill=fill)
    box.id = "b0"
    c.add_shape(box)
    a = tmp_path / "x.palaterm"
    save_canvas(c, a, CharSet.UNICODE)
    loaded, _ = load_canvas(a)
    out = loaded.shapes[0]
    assert isinstance(out, BoxShape)
    assert out.fill is fill


@pytest.mark.parametrize("halign", list(HAlign))
@pytest.mark.parametrize("valign", list(VAlign))
def test_box_round_trip_every_alignment(
    halign: HAlign,
    valign: VAlign,
    tmp_path: Path,
) -> None:
    c = Canvas()
    box = BoxShape(Rect(0, 0, 6, 4), text="x", halign=halign, valign=valign)
    box.id = "b0"
    c.add_shape(box)
    a = tmp_path / "x.palaterm"
    save_canvas(c, a, CharSet.UNICODE)
    loaded, _ = load_canvas(a)
    out = loaded.shapes[0]
    assert isinstance(out, BoxShape)
    assert out.halign is halign
    assert out.valign is valign


@pytest.mark.parametrize("line_style", list(LineStyle))
def test_line_round_trip_every_line_style(
    line_style: LineStyle, tmp_path: Path
) -> None:
    c = Canvas()
    line = LineShape(Point(0, 0), Point(5, 5), line_style=line_style)
    line.id = "l0"
    c.add_shape(line)
    a = tmp_path / "x.palaterm"
    save_canvas(c, a, CharSet.UNICODE)
    loaded, _ = load_canvas(a)
    out = loaded.shapes[0]
    assert isinstance(out, LineShape)
    assert out.line_style is line_style


@pytest.mark.parametrize("ending", list(EndingStyle))
def test_line_round_trip_every_ending(ending: EndingStyle, tmp_path: Path) -> None:
    c = Canvas()
    line = LineShape(Point(0, 0), Point(5, 5), start_ending=ending, end_ending=ending)
    line.id = "l0"
    c.add_shape(line)
    a = tmp_path / "x.palaterm"
    save_canvas(c, a, CharSet.UNICODE)
    loaded, _ = load_canvas(a)
    out = loaded.shapes[0]
    assert isinstance(out, LineShape)
    assert out.start_ending is ending
    assert out.end_ending is ending


@pytest.mark.parametrize("anchor", list(Anchor))
@pytest.mark.parametrize("side", list(Side))
def test_connector_round_trip_every_enum(
    anchor: Anchor,
    side: Side,
    tmp_path: Path,
) -> None:
    c = Canvas()
    box = BoxShape(Rect(0, 0, 4, 3))
    box.id = "b0"
    line = LineShape(Point(10, 0), Point(20, 5))
    line.id = "l0"
    c.add_shape(box)
    c.add_shape(line)
    c.connector_mgr.add(
        Connector(line_id="l0", anchor=anchor, target_id="b0", side=side, ratio=0.5)
    )
    a = tmp_path / "x.palaterm"
    save_canvas(c, a, CharSet.UNICODE)
    loaded, _ = load_canvas(a)
    conn = loaded.connector_mgr.connectors[0]
    assert conn.anchor is anchor
    assert conn.side is side


@pytest.mark.parametrize("charset", list(CharSet))
def test_charset_round_trip(charset: CharSet, tmp_path: Path) -> None:
    c = Canvas()
    box = BoxShape(Rect(0, 0, 4, 3))
    box.id = "b0"
    c.add_shape(box)
    a = tmp_path / "x.palaterm"
    save_canvas(c, a, charset)
    _, loaded_charset = load_canvas(a)
    assert loaded_charset is charset


def test_round_trip_preserves_edge_modified_joints(tmp_path: Path) -> None:
    """An edge-dragged line keeps its custom joint path through save/load."""
    c = Canvas()
    line = LineShape(Point(0, 0), Point(10, 4), line_style=LineStyle.ORTHOGONAL)
    line.id = "l0"
    line.start_side = "left"
    line.end_side = "left"
    line._recompute()
    line.move_edge(1, Point(7, 2))
    expected = list(line.joint_points)
    c.add_shape(line)
    p = tmp_path / "x.palaterm"
    save_canvas(c, p)
    loaded, _ = load_canvas(p)
    reloaded = loaded.shapes[0]
    assert isinstance(reloaded, LineShape)
    assert reloaded.routing.edges_modified
    assert reloaded.joint_points == expected


def test_unedited_line_omits_joint_fields_from_disk(tmp_path: Path) -> None:
    """Unmodified lines round-trip without bloating the file."""
    c = Canvas()
    line = LineShape(Point(0, 0), Point(5, 3), line_style=LineStyle.ORTHOGONAL)
    line.id = "l0"
    c.add_shape(line)
    p = tmp_path / "x.palaterm"
    save_canvas(c, p)
    raw = p.read_text()
    assert '"j"' not in raw
    assert '"em"' not in raw
