"""Shared test fixtures.

Owned by the test suite, but ``scripts/bench_serialize.py`` and
``scripts/bench_render.py`` import :func:`build_fixed_canvas` so the
benches and the tests measure / verify the same canvas. Editing this
file means re-running the benches to refresh their baselines.
"""

from __future__ import annotations

from palaterm.canvas import Canvas
from palaterm.connectors import Anchor, Connector, Side
from palaterm.geometry import Point, Rect
from palaterm.models import (
    BorderStyle,
    BoxShape,
    EndingStyle,
    FillStyle,
    HAlign,
    LineShape,
    LineStyle,
    VAlign,
)


def build_fixed_canvas() -> Canvas:
    """A 50-shape canvas with deterministic IDs and a representative mix.

    30 boxes in a 6×5 grid covering all border/fill/alignment enum
    members; 20 lines covering orthogonal/straight/braille and arrow
    + circle endings; 3 connectors with non-clean ratios; 3 boxes
    with sub-cell ``rect_f`` precision.

    Shape IDs are pinned to ``s00``..``s49`` so two runs produce
    byte-identical serializations.
    """
    canvas = Canvas()

    border_cycle = [
        BorderStyle.LIGHT,
        BorderStyle.HEAVY,
        BorderStyle.DOUBLE,
        BorderStyle.ROUNDED,
        BorderStyle.BRAILLE,
    ]
    fill_cycle = [FillStyle.NONE, FillStyle.LIGHT, FillStyle.MEDIUM]
    halign_cycle = [HAlign.LEFT, HAlign.CENTER, HAlign.RIGHT]
    valign_cycle = [VAlign.TOP, VAlign.MIDDLE, VAlign.BOTTOM]
    placed = 0
    for r in range(5):
        for c in range(6):
            if placed >= 30:
                break
            box = BoxShape(
                Rect(2 + c * 26, 1 + r * 9, 24, 8),
                text=f"box {placed}" if placed % 3 == 0 else "",
                border=border_cycle[placed % len(border_cycle)],
                fill=fill_cycle[placed % len(fill_cycle)],
                halign=halign_cycle[placed % len(halign_cycle)],
                valign=valign_cycle[placed % len(valign_cycle)],
            )
            if placed % 4 == 0:
                box.fg = "cyan"
            canvas.add_shape(box)
            placed += 1

    for i in range(20):
        a = Point(5 + (i * 17) % 180, 2 + (i * 7) % 50)
        b = Point(10 + (i * 23) % 180, 5 + (i * 11) % 50)
        line = LineShape(
            a,
            b,
            border=BorderStyle.BRAILLE if i % 3 == 0 else BorderStyle.LIGHT,
            line_style=LineStyle.STRAIGHT if i % 2 else LineStyle.ORTHOGONAL,
            start_ending=EndingStyle.ARROW if i % 5 == 0 else EndingStyle.NONE,
            end_ending=EndingStyle.CIRCLE if i % 7 == 0 else EndingStyle.NONE,
        )
        if i % 4 == 0:
            line.start_sub = (0, 1)
            line.end_sub = (1, 2)
        canvas.add_shape(line)

    for i, shape in enumerate(canvas.shapes):
        shape.id = f"s{i:02}"

    for sid, lf, tf, rf, bf in [
        ("s04", 106.0, 1.0, 113.42105263157896, 8.875),
        ("s09", 80.5, 10.5, 92.66666666666667, 17.625),
        ("s14", 54.25, 19.0, 65.33333333333333, 26.5),
    ]:
        box = next(s for s in canvas.shapes if s.id == sid)
        assert isinstance(box, BoxShape)
        box.resize_f(lf, tf, rf, bf)

    canvas.connector_mgr.add(
        Connector(
            line_id="s30",
            anchor=Anchor.START,
            target_id="s00",
            side=Side.RIGHT,
            ratio=1 / 3,
        )
    )
    canvas.connector_mgr.add(
        Connector(
            line_id="s31",
            anchor=Anchor.END,
            target_id="s05",
            side=Side.TOP,
            ratio=2 / 7,
        )
    )
    canvas.connector_mgr.add(
        Connector(
            line_id="s32",
            anchor=Anchor.START,
            target_id="s10",
            side=Side.BOTTOM,
            ratio=5 / 9,
        )
    )

    return canvas
