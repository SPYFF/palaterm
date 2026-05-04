"""Generic draw tool and concrete shape-creation tools."""

from __future__ import annotations

from ..geometry import Point, Rect
from ..shapes import BorderStyle, LineShape, LineStyle, RectangleShape, Shape, TextShape


class DrawTool:
    """Generic drag-to-create tool. Subclasses override shape creation."""

    def __init__(self) -> None:
        self._start: Point | None = None
        self._shape: Shape | None = None

    def _create_shape(self, start: Point) -> Shape:
        raise NotImplementedError

    def _update_shape(self, shape: Shape, start: Point, current: Point) -> None:
        shape.resize(Rect.from_points(start, current))  # type: ignore[attr-defined]

    def on_mouse_down(self, col: int, row: int, canvas) -> Shape | None:
        self._start = Point(col, row)
        self._shape = self._create_shape(self._start)
        canvas.add_shape(self._shape)
        return self._shape

    def on_mouse_drag(self, col: int, row: int, canvas) -> None:
        if self._shape and self._start:
            self._update_shape(self._shape, self._start, Point(col, row))

    def on_mouse_up(self, col: int, row: int, canvas) -> Shape | None:
        if self._shape and self._start:
            self._update_shape(self._shape, self._start, Point(col, row))
        result = self._shape
        self._shape = None
        self._start = None
        return result


class RectangleTool(DrawTool):
    def __init__(self, border_style: BorderStyle = BorderStyle.LIGHT) -> None:
        super().__init__()
        self.border_style = border_style

    def _create_shape(self, start: Point) -> Shape:
        return RectangleShape(Rect(start.col, start.row, 1, 1), border=self.border_style)


class TextTool(DrawTool):
    def _create_shape(self, start: Point) -> Shape:
        return TextShape(Rect(start.col, start.row, 1, 1))


class LineTool(DrawTool):
    def __init__(self, border_style: BorderStyle = BorderStyle.LIGHT,
                 line_style: LineStyle = LineStyle.ORTHOGONAL) -> None:
        super().__init__()
        self.border_style = border_style
        self.line_style = line_style

    def _create_shape(self, start: Point) -> Shape:
        return LineShape(Point(start.col, start.row), Point(start.col, start.row),
                         border=self.border_style, line_style=self.line_style)

    def _update_shape(self, shape: Shape, start: Point, current: Point) -> None:
        assert isinstance(shape, LineShape)
        shape.end = Point(current.col, current.row)
        shape._recompute()
