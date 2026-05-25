"""Tests for the unified ``Tool.overlays()`` interface."""

from __future__ import annotations

from palaterm.canvas import Canvas
from palaterm.connectors import Side, SnapResult
from palaterm.geometry import Point, Rect
from palaterm.models import BoxShape, LineShape
from palaterm.tools import LineTool, RectangleTool, SelectTool
from palaterm.tools.overlays import EdgeHover, SnapHighlight


def test_idle_select_tool_emits_no_overlays() -> None:
    assert SelectTool().overlays() == []


def test_idle_line_tool_emits_no_overlays() -> None:
    assert LineTool().overlays() == []


def test_rectangle_tool_emits_no_overlays() -> None:
    assert RectangleTool().overlays() == []


def test_line_tool_with_snap_target_emits_snap_highlight() -> None:
    tool = LineTool()
    tool.snap_target = SnapResult(
        target_id="abc", side=Side.RIGHT, ratio=0.5, point=Point(0, 0)
    )
    overlays = tool.overlays()
    assert overlays == [SnapHighlight(target_id="abc", side=Side.RIGHT)]


def test_select_tool_emits_edge_hover_when_hovering_edge() -> None:
    tool = SelectTool()
    line = LineShape(start=Point(0, 0), end=Point(10, 0))
    tool.hover_edge_line = line
    tool.hover_edge_index = 0
    tool.hover_edge_whole = False

    overlays = tool.overlays()

    assert overlays == [EdgeHover(line=line, edge_index=0, whole=False)]


def test_select_tool_emits_whole_line_edge_hover_at_joint() -> None:
    tool = SelectTool()
    line = LineShape(start=Point(0, 0), end=Point(10, 5))
    tool.hover_edge_line = line
    tool.hover_edge_whole = True

    overlays = tool.overlays()

    assert len(overlays) == 1
    overlay = overlays[0]
    assert isinstance(overlay, EdgeHover)
    assert overlay.whole is True


def test_renderer_consumes_snap_highlight() -> None:
    """The cache should populate snap_edge_cells from a SnapHighlight overlay."""
    from palaterm.models import CharSet
    from palaterm.rendering import FrameRenderer
    from rich.style import Style as RichStyle

    canvas = Canvas()
    box = BoxShape(rect=Rect(2, 2, 6, 4))
    canvas.add_shape(box)

    tool = LineTool()
    tool.snap_target = SnapResult(
        target_id=box.id, side=Side.LEFT, ratio=0.5, point=Point(2, 4)
    )

    renderer = FrameRenderer(canvas)
    cache = renderer._ensure_cache(
        Rect(0, 0, 20, 20), tool, RichStyle(), CharSet.UNICODE
    )
    snap_edge_cells = cache[6]

    # Left edge runs from (2, 2) to (2, 5).
    assert (2, 2) in snap_edge_cells
    assert (2, 5) in snap_edge_cells
