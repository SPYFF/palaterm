"""Drawing tools: handle mouse interactions to create/modify shapes."""

from __future__ import annotations

from enum import Enum, auto

from ..geometry import Point, Rect
from ..models import LineShape, Shape
from .draw import DrawTool, LineTool, RectangleTool, TextTool
from .select import SelectMode, SelectTool


class ToolType(Enum):
    SELECT = auto()
    RECTANGLE = auto()
    TEXT = auto()
    LINE = auto()


class Handle(Enum):
    TOP_LEFT = auto()
    TOP_MID = auto()
    TOP_RIGHT = auto()
    MID_LEFT = auto()
    MID_RIGHT = auto()
    BOT_LEFT = auto()
    BOT_MID = auto()
    BOT_RIGHT = auto()
    LINE_START = auto()
    LINE_END = auto()


def get_handles(shape: Shape) -> dict[Handle, Point]:
    if isinstance(shape, LineShape):
        return {
            Handle.LINE_START: Point(shape.start.col, shape.start.row),
            Handle.LINE_END: Point(shape.end.col, shape.end.row),
        }
    b = shape.bound
    mid_col = b.left + b.width // 2
    mid_row = b.top + b.height // 2
    return {
        Handle.TOP_LEFT: Point(b.left, b.top),
        Handle.TOP_MID: Point(mid_col, b.top),
        Handle.TOP_RIGHT: Point(b.right, b.top),
        Handle.MID_LEFT: Point(b.left, mid_row),
        Handle.MID_RIGHT: Point(b.right, mid_row),
        Handle.BOT_LEFT: Point(b.left, b.bottom),
        Handle.BOT_MID: Point(mid_col, b.bottom),
        Handle.BOT_RIGHT: Point(b.right, b.bottom),
    }


def handle_at(
    shape: Shape,
    col: int,
    row: int,
    pointer_x: float | None = None,
    pointer_y: float | None = None,
) -> Handle | None:
    import math

    matches = [
        (h, pt)
        for h, pt in get_handles(shape).items()
        if pt.col == col and pt.row == row
    ]
    if not matches:
        return None
    if len(matches) == 1 or pointer_x is None or pointer_y is None:
        return matches[0][0]
    # Use fractional part to pick the closest handle by logical position
    fx = pointer_x - math.floor(pointer_x)
    fy = pointer_y - math.floor(pointer_y)
    b = shape.bound

    def expected(pt: Point) -> tuple[float, float]:
        hx = 0.0 if pt.col == b.left else (1.0 if pt.col == b.right else 0.5)
        hy = 0.0 if pt.row == b.top else (1.0 if pt.row == b.bottom else 0.5)
        return hx, hy

    return min(
        matches,
        key=lambda hp: (fx - expected(hp[1])[0]) ** 2 + (fy - expected(hp[1])[1]) ** 2,
    )[0]


__all__ = [
    "ToolType",
    "Handle",
    "Rect",
    "get_handles",
    "handle_at",
    "DrawTool",
    "RectangleTool",
    "TextTool",
    "LineTool",
    "SelectTool",
    "SelectMode",
]
