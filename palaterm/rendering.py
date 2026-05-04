"""Frame rendering: composites canvas cells into styled Strips with caching."""

from __future__ import annotations

from rich.segment import Segment
from rich.style import Style as RichStyle
from textual.strip import Strip

from .canvas import Canvas
from .geometry import Rect
from .shapes import CharSet, Shape, braille_rect
from .tools import SelectTool, get_handles


# Pre-allocated style singletons
_STYLE_CYAN = RichStyle(color="cyan")
_STYLE_MAGENTA = RichStyle(color="bright_magenta")
_STYLE_SNAP = RichStyle(color="green", bold=True)
_STYLE_HIGHLIGHT = {
    "yellow": RichStyle(color="yellow"),
    "bright_cyan": RichStyle(color="bright_cyan"),
}


class FrameRenderer:
    """Caches per-frame compositing data and renders individual lines."""

    def __init__(self, canvas: Canvas) -> None:
        self.canvas = canvas
        self._cache: tuple | None = None

    def invalidate(self) -> None:
        self._cache = None

    def _ensure_cache(self, viewport: Rect, tool, base_style: RichStyle,
                      charset: CharSet) -> tuple:
        if self._cache is not None:
            return self._cache

        cells = self.canvas.render_region(viewport, charset)

        highlight_cells: dict[tuple[int, int], str] = {}
        handle_cells: set[tuple[int, int]] = set()
        snap_edge_cells: set[tuple[int, int]] = set()

        if isinstance(tool, SelectTool):
            for shape in tool.selected:
                for pos in shape.render(charset):
                    highlight_cells[pos] = "yellow"
                for _, pt in get_handles(shape).items():
                    handle_cells.add((pt.col, pt.row))
            if tool.hover_shape and tool.hover_shape not in tool.selected:
                for pos in tool.hover_shape.render(charset):
                    highlight_cells[pos] = "bright_cyan"
                for _, pt in get_handles(tool.hover_shape).items():
                    handle_cells.add((pt.col, pt.row))
            # Snap edge highlight for line handle drag
            if hasattr(tool, 'snap_target') and tool.snap_target:
                snap_edge_cells = self._get_edge_cells(tool.snap_target)

        # Snap edge highlight for line tool
        from .tools import LineTool
        if isinstance(tool, LineTool) and hasattr(tool, 'snap_target') and tool.snap_target:
            snap_edge_cells = self._get_edge_cells(tool.snap_target)

        sel_rect = None
        if isinstance(tool, SelectTool) and tool.selection_rect:
            sel_rect = tool.selection_rect

        sel_braille: dict[tuple[int, int], str] = {}
        if sel_rect:
            sel_braille = braille_rect(sel_rect.left, sel_rect.top, sel_rect.right, sel_rect.bottom, charset)

        self._cache = (cells, highlight_cells, handle_cells, sel_rect, sel_braille, base_style, snap_edge_cells)
        return self._cache

    def _get_edge_cells(self, snap_result) -> set[tuple[int, int]]:
        """Get the cells along the target shape's snapped edge."""
        from .connectors import Side
        target = next((s for s in self.canvas.shapes if s.id == snap_result.target_id), None)
        if not target:
            return set()
        b = target.bound
        cells: set[tuple[int, int]] = set()
        match snap_result.side:
            case Side.LEFT:
                for row in range(b.top, b.bottom + 1):
                    cells.add((b.left, row))
            case Side.RIGHT:
                for row in range(b.top, b.bottom + 1):
                    cells.add((b.right, row))
            case Side.TOP:
                for col in range(b.left, b.right + 1):
                    cells.add((col, b.top))
            case Side.BOTTOM:
                for col in range(b.left, b.right + 1):
                    cells.add((col, b.bottom))
        return cells

    def render_line(self, y: int, viewport: Rect, tool, base_style: RichStyle,
                    charset: CharSet = CharSet.UNICODE) -> Strip:
        cells, highlight_cells, handle_cells, sel_rect, sel_braille, base_style, snap_edge_cells = self._ensure_cache(
            viewport, tool, base_style, charset
        )
        row = y + viewport.top
        width = viewport.width
        scroll_col = viewport.left

        segments: list[Segment] = []
        for x in range(width):
            col = x + scroll_col
            pos = (col, row)
            ch = cells.get(pos, " ")

            if pos in sel_braille:
                segments.append(Segment(sel_braille[pos], _STYLE_CYAN))
            elif sel_rect and sel_rect.contains(col, row):
                segments.append(Segment(ch, _STYLE_CYAN))
            elif pos in handle_cells:
                handle_ch = "*" if charset == CharSet.ASCII else "◆"
                segments.append(Segment(handle_ch, _STYLE_MAGENTA))
            elif pos in snap_edge_cells:
                segments.append(Segment(ch, _STYLE_SNAP))
            elif pos in highlight_cells:
                segments.append(Segment(ch, _STYLE_HIGHLIGHT[highlight_cells[pos]]))
            else:
                segments.append(Segment(ch, base_style))
        return Strip(segments)
