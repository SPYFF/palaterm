"""Canvas model: manages shapes and composites them into a character grid."""

from __future__ import annotations

from .compositing import composite
from .connectors import ConnectorManager
from .geometry import Rect
from .models import CharSet, Shape


class Canvas:
    """Manages a collection of shapes and composites them for rendering."""

    def __init__(self) -> None:
        self.shapes: list[Shape] = []
        self.connector_mgr = ConnectorManager()

    def add_shape(self, shape: Shape) -> None:
        self.shapes.append(shape)

    def remove_shape(self, shape: Shape) -> None:
        self.shapes = [s for s in self.shapes if s.id != shape.id]

    def shape_at(self, col: int, row: int) -> Shape | None:
        """Find topmost shape at position (last in list = topmost)."""
        for shape in reversed(self.shapes):
            if shape.hit_test(col, row):
                return shape
        return None

    def shapes_fully_in(self, region: Rect) -> list[Shape]:
        """Return shapes whose bounds are entirely within region."""
        return [
            s
            for s in self.shapes
            if region.contains(s.bound.left, s.bound.top)
            and region.contains(s.bound.right, s.bound.bottom)
        ]

    def shapes_partially_in(self, region: Rect) -> list[Shape]:
        """Return shapes whose bounds overlap with region."""
        return [
            s
            for s in self.shapes
            if s.bound.left <= region.right
            and s.bound.right >= region.left
            and s.bound.top <= region.bottom
            and s.bound.bottom >= region.top
        ]

    def bring_to_front(self, shape: Shape) -> None:
        self.shapes.remove(shape)
        self.shapes.append(shape)

    def send_to_back(self, shape: Shape) -> None:
        self.shapes.remove(shape)
        self.shapes.insert(0, shape)

    def bring_forward(self, shape: Shape) -> None:
        i = self.shapes.index(shape)
        if i < len(self.shapes) - 1:
            self.shapes[i], self.shapes[i + 1] = self.shapes[i + 1], self.shapes[i]

    def send_backward(self, shape: Shape) -> None:
        i = self.shapes.index(shape)
        if i > 0:
            self.shapes[i], self.shapes[i - 1] = self.shapes[i - 1], self.shapes[i]

    def composite(
        self,
        region: Rect,
        charset: CharSet = CharSet.UNICODE,
        shapes: list[Shape] | None = None,
    ) -> dict[tuple[int, int], tuple[str, str | None, str | None]]:
        """Composite shapes within *region*. Delegates to :mod:`compositing`."""
        return composite(shapes if shapes is not None else self.shapes, region, charset)

    def export_to_text(
        self, shapes: list[Shape] | None = None, charset: CharSet = CharSet.UNICODE
    ) -> str:
        """Render shapes to a multi-line string. Uses all shapes if none specified."""
        targets = shapes if shapes else self.shapes
        if not targets:
            return ""
        min_col = min(s.bound.left for s in targets)
        max_col = max(s.bound.right for s in targets)
        min_row = min(s.bound.top for s in targets)
        max_row = max(s.bound.bottom for s in targets)
        region = Rect(min_col, min_row, max_col - min_col + 1, max_row - min_row + 1)
        styled = composite(targets, region, charset)
        if not styled:
            return ""
        lines = []
        for row in range(min_row, max_row + 1):
            line = "".join(
                styled[(col, row)][0] if (col, row) in styled else " "
                for col in range(min_col, max_col + 1)
            )
            lines.append(line.rstrip())
        return "\n".join(lines)

    def render_styled(
        self, shapes: list[Shape] | None = None, charset: CharSet = CharSet.UNICODE
    ) -> tuple[Rect, dict[tuple[int, int], tuple[str, str | None, str | None]]]:
        """Composite shapes into a per-cell ``(char, fg, bg)`` grid.

        Returns ``(bounding_rect, cells)``.
        Returns ``(Rect(0, 0, 0, 0), {})`` when there is nothing to render.
        """
        targets = shapes if shapes else self.shapes
        if not targets:
            return Rect(0, 0, 0, 0), {}
        min_col = min(s.bound.left for s in targets)
        max_col = max(s.bound.right for s in targets)
        min_row = min(s.bound.top for s in targets)
        max_row = max(s.bound.bottom for s in targets)
        region = Rect(min_col, min_row, max_col - min_col + 1, max_row - min_row + 1)
        cells = composite(targets, region, charset)
        if not cells:
            return Rect(0, 0, 0, 0), {}
        return region, cells
