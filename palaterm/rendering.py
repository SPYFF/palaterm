"""Frame rendering: composites canvas cells into styled Strips with caching."""

from __future__ import annotations

from typing import NamedTuple

from rich.segment import Segment
from rich.style import Style as RichStyle
from textual.strip import Strip

from .canvas import Canvas
from .compositing import composite
from .connectors import Side
from .geometry import Rect
from .models import CharSet, braille_rect, braille_rect_precise
from .tools import DrawTool, SelectTool, get_handles
from .tools.overlays import EdgeHover, SnapHighlight

# Foreground-only style fragments. They are merged with the canvas widget's
# resolved style each frame so highlights inherit the theme background; emitting
# them with bg=None makes the terminal fall back to its default background,
# which differs from the canvas's themed bg and produces a visible color bleed.
_FG_CYAN = RichStyle(color="cyan")
_FG_GREEN = RichStyle(color="green")
_FG_RED = RichStyle(color="red")
_FG_MAGENTA = RichStyle(color="bright_magenta")
_FG_SNAP = RichStyle(color="green", bold=True)
_FG_EDGE_HOVER = RichStyle(color="bright_yellow", bold=True)
_FG_HIGHLIGHT = {
    "yellow": RichStyle(color="yellow"),
    "bright_cyan": RichStyle(color="bright_cyan"),
}


class _FrameCache(NamedTuple):
    cells: dict[tuple[int, int], str]
    highlight_cells: dict[tuple[int, int], str]
    handle_cells: set[tuple[int, int]]
    sel_rect: Rect | None
    sel_braille: dict[tuple[int, int], str]
    base_style: RichStyle
    snap_edge_cells: set[tuple[int, int]]
    cell_styles: dict[tuple[int, int], RichStyle]
    edge_hover_cells: set[tuple[int, int]]
    cyan_style: RichStyle
    magenta_style: RichStyle
    snap_style: RichStyle
    edge_hover_style: RichStyle
    highlight_yellow: RichStyle
    highlight_cyan: RichStyle


class FrameRenderer:
    """Caches per-frame compositing data and renders individual lines."""

    def __init__(self, canvas: Canvas) -> None:
        self.canvas = canvas
        self._cache: _FrameCache | None = None
        self._dirty_rect: Rect | None = None
        self._cache_viewport: Rect | None = None
        self._cache_charset: CharSet | None = None

    def invalidate(self, dirty_rect: Rect | None = None) -> None:
        """Mark the cache as needing a rebuild.

        If ``dirty_rect`` is provided and a cache already exists, only the
        cells within that rect will be recomputed on the next render pass.
        If ``None``, the entire cache is discarded.
        """
        if dirty_rect is None:
            self._cache = None
            self._dirty_rect = None
            return
        if self._cache is None:
            return
        if self._dirty_rect is None:
            self._dirty_rect = dirty_rect
        else:
            d = self._dirty_rect
            left = min(d.left, dirty_rect.left)
            top = min(d.top, dirty_rect.top)
            right = max(d.left + d.width - 1, dirty_rect.left + dirty_rect.width - 1)
            bottom = max(d.top + d.height - 1, dirty_rect.top + dirty_rect.height - 1)
            self._dirty_rect = Rect(left, top, right - left + 1, bottom - top + 1)

    def _ensure_cache(
        self,
        viewport: Rect,
        tool: DrawTool | SelectTool | None,
        base_style: RichStyle,
        charset: CharSet,
    ) -> _FrameCache:
        if self._cache is not None and (
            viewport != self._cache_viewport or charset != self._cache_charset
        ):
            self._cache = None
            self._dirty_rect = None

        if self._cache is not None and self._dirty_rect is None:
            return self._cache

        if self._cache is None:
            cells, cell_styles = self._composite_to_cache(viewport, charset, base_style)
        else:
            cells = self._cache.cells
            cell_styles = self._cache.cell_styles
            self._patch_cells(
                cells, cell_styles, self._dirty_rect, viewport, charset, base_style
            )

        self._dirty_rect = None
        self._cache_viewport = viewport
        self._cache_charset = charset

        highlight_cells, handle_cells, snap_edge_cells, edge_hover_cells = (
            self._build_overlays(tool, charset)
        )

        sel_rect = None
        if isinstance(tool, SelectTool) and tool.selection_rect:
            sel_rect = tool.selection_rect

        sel_braille: dict[tuple[int, int], str] = {}
        if sel_rect:
            if isinstance(tool, SelectTool) and tool.selection_rect_f:
                lf, tf, rf, bf = tool.selection_rect_f
                sel_braille = braille_rect_precise(lf, tf, rf, bf, charset)
            else:
                sel_braille = braille_rect(
                    sel_rect.left,
                    sel_rect.top,
                    sel_rect.right,
                    sel_rect.bottom,
                    charset,
                )

        self._cache = _FrameCache(
            cells=cells,
            highlight_cells=highlight_cells,
            handle_cells=handle_cells,
            sel_rect=sel_rect,
            sel_braille=sel_braille,
            base_style=base_style,
            snap_edge_cells=snap_edge_cells,
            cell_styles=cell_styles,
            edge_hover_cells=edge_hover_cells,
            cyan_style=base_style + _FG_CYAN,
            magenta_style=base_style + _FG_MAGENTA,
            snap_style=base_style + _FG_SNAP,
            edge_hover_style=base_style + _FG_EDGE_HOVER,
            highlight_yellow=base_style + _FG_HIGHLIGHT["yellow"],
            highlight_cyan=base_style + _FG_HIGHLIGHT["bright_cyan"],
        )
        return self._cache

    def _composite_to_cache(
        self, region: Rect, charset: CharSet, base_style: RichStyle
    ) -> tuple[dict[tuple[int, int], str], dict[tuple[int, int], RichStyle]]:
        """Run the unified compositor and split into cells + cell_styles."""
        styled = composite(self.canvas.shapes, region, charset)
        cells: dict[tuple[int, int], str] = {}
        cell_styles: dict[tuple[int, int], RichStyle] = {}
        for pos, (ch, fg, bg) in styled.items():
            cells[pos] = ch
            if fg is not None or bg is not None:
                cell_styles[pos] = base_style + RichStyle(color=fg, bgcolor=bg)
        return cells, cell_styles

    def _patch_cells(
        self,
        cells: dict[tuple[int, int], str],
        cell_styles: dict[tuple[int, int], RichStyle],
        dirty: Rect,
        viewport: Rect,
        charset: CharSet,
        base_style: RichStyle,
    ) -> None:
        """Recompute cells within the dirty rect via the unified compositor."""
        d_left, d_top = dirty.left, dirty.top
        d_right = dirty.left + dirty.width - 1
        d_bottom = dirty.top + dirty.height - 1

        v_left, v_top = viewport.left, viewport.top
        v_right = viewport.left + viewport.width - 1
        v_bottom = viewport.top + viewport.height - 1
        r_left = max(d_left, v_left)
        r_top = max(d_top, v_top)
        r_right = min(d_right, v_right)
        r_bottom = min(d_bottom, v_bottom)
        if r_left > r_right or r_top > r_bottom:
            return

        # Clear dirty cells
        for row in range(r_top, r_bottom + 1):
            for col in range(r_left, r_right + 1):
                pos = (col, row)
                cells.pop(pos, None)
                cell_styles.pop(pos, None)

        # Re-composite the dirty sub-region
        patch_region = Rect(r_left, r_top, r_right - r_left + 1, r_bottom - r_top + 1)
        styled = composite(self.canvas.shapes, patch_region, charset)
        for pos, (ch, fg, bg) in styled.items():
            cells[pos] = ch
            if fg is not None or bg is not None:
                cell_styles[pos] = base_style + RichStyle(color=fg, bgcolor=bg)

    def _build_overlays(
        self, tool: DrawTool | SelectTool | None, charset: CharSet
    ) -> tuple[
        dict[tuple[int, int], str],
        set[tuple[int, int]],
        set[tuple[int, int]],
        set[tuple[int, int]],
    ]:
        highlight_cells: dict[tuple[int, int], str] = {}
        handle_cells: set[tuple[int, int]] = set()
        snap_edge_cells: set[tuple[int, int]] = set()
        edge_hover_cells: set[tuple[int, int]] = set()

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

        if tool is not None and hasattr(tool, "overlays"):
            for overlay in tool.overlays():
                if isinstance(overlay, SnapHighlight):
                    snap_edge_cells |= self._snap_edge_cells(overlay)
                elif isinstance(overlay, EdgeHover):
                    edge_hover_cells |= self._edge_hover_cells(overlay, charset)

        return highlight_cells, handle_cells, snap_edge_cells, edge_hover_cells

    def _edge_hover_cells(
        self, overlay: EdgeHover, charset: CharSet
    ) -> set[tuple[int, int]]:
        line = overlay.line
        if overlay.whole:
            return set(line.render(charset).keys())
        idx = overlay.edge_index
        if idx is None:
            return set()
        joints = line.joint_points
        if idx < 0 or idx >= len(joints) - 1:
            return set()
        p1, p2 = joints[idx], joints[idx + 1]
        cells: set[tuple[int, int]] = set()
        if p1.row == p2.row:
            for c in range(min(p1.col, p2.col), max(p1.col, p2.col) + 1):
                cells.add((c, p1.row))
        else:
            for r in range(min(p1.row, p2.row), max(p1.row, p2.row) + 1):
                cells.add((p1.col, r))
        return cells

    def _snap_edge_cells(self, overlay: SnapHighlight) -> set[tuple[int, int]]:
        """Cells along the target shape's snapped edge."""
        target = next(
            (s for s in self.canvas.shapes if s.id == overlay.target_id), None
        )
        if not target:
            return set()
        b = target.bound
        cells: set[tuple[int, int]] = set()
        match overlay.side:
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

    def render_line(
        self,
        y: int,
        viewport: Rect,
        tool: DrawTool | SelectTool | None,
        base_style: RichStyle,
        charset: CharSet = CharSet.UNICODE,
    ) -> Strip:
        c = self._ensure_cache(viewport, tool, base_style, charset)

        row = y + viewport.top
        width = viewport.width
        scroll_col = viewport.left

        # Selection rect style — computed once per row (only when active).
        sel_modifier = ""
        sel_drag_start: tuple[int, int] | None = None
        if isinstance(tool, SelectTool):
            sel_modifier = tool._modifier
            if tool._drag_start:
                sel_drag_start = (tool._drag_start.col, tool._drag_start.row)
        if sel_modifier == "add":
            sel_style = c.base_style + _FG_GREEN
        elif sel_modifier == "remove":
            sel_style = c.base_style + _FG_RED
        else:
            sel_style = c.cyan_style

        # Determine if any selection overlay is active for this frame.
        has_sel = bool(c.sel_braille or c.sel_rect)
        handle_ch = "*" if charset == CharSet.ASCII else "◆"

        # Build segments — use local variable references for speed.
        _Seg = Segment
        _get = c.cells.get
        segments: list[Segment] = []
        _append = segments.append

        for x in range(width):
            col = x + scroll_col
            pos = (col, row)

            if has_sel and sel_drag_start and pos == sel_drag_start:
                sign = (
                    "+"
                    if sel_modifier == "add"
                    else "−"
                    if sel_modifier == "remove"
                    else ""
                )
                if sign:
                    _append(_Seg(sign, sel_style))
                    continue

            if pos in c.sel_braille:
                _append(_Seg(c.sel_braille[pos], sel_style))
            elif c.sel_rect and c.sel_rect.contains(col, row):
                _append(_Seg(_get(pos, " "), sel_style))
            elif pos in c.handle_cells:
                _append(_Seg(handle_ch, c.magenta_style))
            elif pos in c.snap_edge_cells:
                _append(_Seg(_get(pos, " "), c.snap_style))
            elif pos in c.edge_hover_cells:
                _append(_Seg(_get(pos, " "), c.edge_hover_style))
            elif pos in c.highlight_cells:
                _append(
                    _Seg(
                        _get(pos, " "),
                        c.highlight_yellow
                        if c.highlight_cells[pos] == "yellow"
                        else c.highlight_cyan,
                    )
                )
            elif pos in c.cell_styles:
                _append(_Seg(_get(pos, " "), c.cell_styles[pos]))
            else:
                _append(_Seg(_get(pos, " "), c.base_style))

        return Strip(segments, width)
