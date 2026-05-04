"""Generic draw tool and concrete shape-creation tools."""

from __future__ import annotations

from ..geometry import Point, Rect
from ..shapes import BorderStyle, EndingStyle, LineShape, LineStyle, RectangleShape, Shape, TextShape


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
                 line_style: LineStyle = LineStyle.ORTHOGONAL,
                 start_ending: EndingStyle = EndingStyle.NONE,
                 end_ending: EndingStyle = EndingStyle.NONE) -> None:
        super().__init__()
        self.border_style = border_style
        self.line_style = line_style
        self.start_ending = start_ending
        self.end_ending = end_ending
        self.snap_target: object | None = None  # SnapResult during drag

    def _create_shape(self, start: Point) -> Shape:
        return LineShape(Point(start.col, start.row), Point(start.col, start.row),
                         border=self.border_style, line_style=self.line_style,
                         start_ending=self.start_ending, end_ending=self.end_ending)

    def on_mouse_down(self, col: int, row: int, canvas) -> Shape | None:
        from ..connectors import Anchor, Connector, find_snap
        result = super().on_mouse_down(col, row, canvas)
        # Check snap for start point
        line = self._shape
        if isinstance(line, LineShape):
            snap = find_snap(col, row, canvas.shapes, exclude_id=line.id)
            if snap:
                line.start = snap.point
                line.start_side = snap.side.name.lower()
                line._recompute()
                connector = Connector(line.id, Anchor.START, snap.target_id, snap.side, snap.ratio)
                canvas.connector_mgr.add(connector)
        return result

    def _update_shape(self, shape: Shape, start: Point, current: Point) -> None:
        from ..connectors import find_snap
        assert isinstance(shape, LineShape)
        shape.end = Point(current.col, current.row)
        # Live snap detection for visual feedback
        snap = find_snap(current.col, current.row, shape._recompute.__self__.__class__ and [], exclude_id=shape.id)
        shape._recompute()

    def on_mouse_drag(self, col: int, row: int, canvas) -> None:
        from ..connectors import find_snap
        if self._shape and self._start:
            line = self._shape
            assert isinstance(line, LineShape)
            line.end = Point(col, row)
            # Check snap for visual feedback
            self.snap_target = find_snap(col, row, canvas.shapes, exclude_id=line.id)
            if self.snap_target:
                line.end = self.snap_target.point
                line.end_side = self.snap_target.side.name.lower()
            else:
                line.end_side = None
            line._recompute()

    def on_mouse_up(self, col: int, row: int, canvas) -> Shape | None:
        from ..connectors import Anchor, Connector, find_snap
        if self._shape and self._start:
            line = self._shape
            assert isinstance(line, LineShape)
            # Final snap for end point
            snap = find_snap(col, row, canvas.shapes, exclude_id=line.id)
            if snap:
                line.end = snap.point
                line.end_side = snap.side.name.lower()
                connector = Connector(line.id, Anchor.END, snap.target_id, snap.side, snap.ratio)
                canvas.connector_mgr.add(connector)
            else:
                line.end = Point(col, row)
                line.end_side = None
            line._recompute()
        self.snap_target = None
        result = self._shape
        self._shape = None
        self._start = None
        return result
