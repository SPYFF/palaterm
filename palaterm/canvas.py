"""Canvas model: manages shapes and composites them into a character grid."""

from __future__ import annotations

from .connectors import ConnectorManager
from .crossings import is_connectable, resolve_crossing
from .geometry import Rect
from .models import CharSet, Shape, to_ascii


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

    def render_region(
        self, viewport: Rect, charset: CharSet = CharSet.UNICODE
    ) -> dict[tuple[int, int], str]:
        """Composite all shapes within the viewport into a character dict."""
        cells: dict[tuple[int, int], str] = {}
        v_left, v_top, v_right, v_bottom = (
            viewport.left,
            viewport.top,
            viewport.right,
            viewport.bottom,
        )
        for shape in self.shapes:
            # Skip shapes whose bounding box doesn't intersect the viewport.
            # `shape.render()` is expensive (it materializes every cell), so
            # an AABB cull on the bound is much cheaper than rendering then
            # filtering per-cell.
            b = shape.bound
            if (
                b.right < v_left
                or b.left > v_right
                or b.bottom < v_top
                or b.top > v_bottom
            ):
                continue
            for (col, row), ch in shape.render(charset).items():
                if v_left <= col <= v_right and v_top <= row <= v_bottom:
                    existing = cells.get((col, row))
                    if existing and is_connectable(existing) and is_connectable(ch):
                        cells[(col, row)] = resolve_crossing(existing, ch)
                    else:
                        cells[(col, row)] = ch
        if charset == CharSet.ASCII:
            cells = {pos: to_ascii(ch) for pos, ch in cells.items()}
        return cells

    def export_to_text(
        self, shapes: list[Shape] | None = None, charset: CharSet = CharSet.UNICODE
    ) -> str:
        """Render shapes to a multi-line string. Uses all shapes if none specified."""
        targets = shapes if shapes else self.shapes
        if not targets:
            return ""
        cells: dict[tuple[int, int], str] = {}
        for shape in targets:
            cells.update(shape.render(charset))
        if not cells:
            return ""
        if charset == CharSet.ASCII:
            cells = {pos: to_ascii(ch) for pos, ch in cells.items()}
        min_col = min(c for c, r in cells)
        max_col = max(c for c, r in cells)
        min_row = min(r for c, r in cells)
        max_row = max(r for c, r in cells)
        lines = []
        for row in range(min_row, max_row + 1):
            line = "".join(
                cells.get((col, row), " ") for col in range(min_col, max_col + 1)
            )
            lines.append(line.rstrip())
        return "\n".join(lines)

    def render_styled(
        self, shapes: list[Shape] | None = None, charset: CharSet = CharSet.UNICODE
    ) -> tuple[Rect, dict[tuple[int, int], tuple[str, str | None, str | None]]]:
        """Composite shapes into a per-cell ``(char, fg, bg)`` grid.

        Returns ``(bounding_rect, cells)``. Mirrors :meth:`export_to_text`'s
        bounds-auto-cropping but keeps color information per cell.
        Background runs are produced where ``shape.bg`` is set; foreground
        always reflects ``shape.fg``. Crossing resolution applies to the
        char component only — the resolved char inherits the most recent
        shape's colors.

        Returns ``(Rect(0, 0, 0, 0), {})`` when there is nothing to render.
        """
        targets = shapes if shapes else self.shapes
        if not targets:
            return Rect(0, 0, 0, 0), {}

        cells: dict[tuple[int, int], tuple[str, str | None, str | None]] = {}
        for shape in targets:
            fg, bg = shape.fg, shape.bg
            for (col, row), ch in shape.render(charset).items():
                existing = cells.get((col, row))
                if existing and is_connectable(existing[0]) and is_connectable(ch):
                    ch = resolve_crossing(existing[0], ch)
                cells[(col, row)] = (ch, fg, bg)

        if not cells:
            return Rect(0, 0, 0, 0), {}

        if charset == CharSet.ASCII:
            cells = {pos: (to_ascii(ch), fg, bg) for pos, (ch, fg, bg) in cells.items()}

        min_col = min(c for c, r in cells)
        max_col = max(c for c, r in cells)
        min_row = min(r for c, r in cells)
        max_row = max(r for c, r in cells)
        bound = Rect(min_col, min_row, max_col - min_col + 1, max_row - min_row + 1)
        return bound, cells
