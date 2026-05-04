"""Centralized panel visibility controller."""

from __future__ import annotations

from ..shapes import LineShape, LineStyle, TextShape
from ..tools import LineTool, RectangleTool, SelectTool
from ..widgets import (
    AlignmentGrid, LayerButtons, LineStyleButtons,
    ShapeAlignButtons, StyleButtons, ToolOptions,
)


class PanelController:
    """Manages sidebar panel visibility based on tool and selection state."""

    def __init__(self, query_one) -> None:
        self._q = query_one

    def update(self, tool, border_style, line_style) -> None:
        is_select = isinstance(tool, SelectTool)
        selected = tool.selected if is_select else []

        # ToolOptions: only for select tool
        self._q(ToolOptions).set_class(is_select, "visible")

        # StyleButtons: for rect/line tools, or select with bordered shapes
        show_styles = isinstance(tool, (RectangleTool, LineTool))
        if is_select:
            show_styles = any(hasattr(s, "border") for s in selected)
        styles_widget = self._q(StyleButtons)
        styles_widget.set_class(show_styles, "visible")
        if show_styles:
            if isinstance(tool, (RectangleTool, LineTool)):
                styles_widget.set_active(border_style)
            elif is_select:
                borders = [s.border for s in selected if hasattr(s, "border")]
                if borders and all(b == borders[0] for b in borders):
                    styles_widget.set_active(borders[0])
                else:
                    styles_widget.set_active(None)

        # AlignmentGrid: only for select with TextShape selected
        text_shapes = [s for s in selected if isinstance(s, TextShape)]
        align_widget = self._q(AlignmentGrid)
        align_widget.set_class(bool(text_shapes), "visible")
        if text_shapes:
            align_widget.set_active(text_shapes[0].halign, text_shapes[0].valign)

        # LineStyleButtons: Line tool active, or select with LineShape selected
        show_line_style = isinstance(tool, LineTool)
        if is_select:
            show_line_style = any(isinstance(s, LineShape) for s in selected)
        ls_widget = self._q(LineStyleButtons)
        ls_widget.set_class(show_line_style, "visible")
        if show_line_style:
            if isinstance(tool, LineTool):
                ls_widget.set_active(line_style)
            elif is_select:
                styles = [s.line_style for s in selected if isinstance(s, LineShape)]
                if styles:
                    ls_widget.set_active(styles[0])

        # ShapeAlignButtons: select tool with 2+ shapes selected
        self._q(ShapeAlignButtons).set_class(len(selected) >= 2, "visible")

        # LayerButtons: select tool with any selection
        self._q(LayerButtons).set_class(bool(selected), "visible")
