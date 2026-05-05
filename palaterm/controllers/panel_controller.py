"""Centralized panel visibility and state controller."""

from __future__ import annotations

from ..models.enums import EndingStyle
from ..shapes import LineShape, LineStyle, TextShape
from ..tools import LineTool, RectangleTool, SelectTool
from ..widgets.panels import (
    BorderStylePanel, LayerPanel, LineEndingsPanel, LineStylePanel,
    SelectModePanel, ShapeAlignPanel, TextAlignPanel, ToolPicker,
)


class PanelController:
    """Single source of truth for all panel visibility and active state."""

    def __init__(self, query_one) -> None:
        self._q = query_one

    def update(self, tool, tool_ctrl) -> None:
        """Update all panels based on current tool and selection state."""
        is_select = isinstance(tool, SelectTool)
        selected = tool.selected if is_select else []

        # Tool picker: always visible, sync active state
        self._q(ToolPicker).set_active(tool_ctrl.active_tool_type)

        # Select mode: only for select tool
        mode_panel = self._q(SelectModePanel)
        mode_panel.set_class(is_select, "visible")
        if is_select:
            mode_panel.set_active(tool.mode)

        # Border style: rect/line tool, or select with bordered shapes
        show_border = isinstance(tool, (RectangleTool, LineTool))
        if is_select:
            show_border = any(hasattr(s, "border") for s in selected)
        border_panel = self._q(BorderStylePanel)
        border_panel.set_class(show_border, "visible")
        if show_border:
            if isinstance(tool, (RectangleTool, LineTool)):
                border_panel.set_active(tool_ctrl.border_style)
            elif is_select:
                borders = [s.border for s in selected if hasattr(s, "border")]
                if borders and all(b == borders[0] for b in borders):
                    border_panel.set_active(borders[0])

        # Line style: line tool or select with LineShape
        show_line = isinstance(tool, LineTool)
        if is_select:
            show_line = any(isinstance(s, LineShape) for s in selected)
        line_panel = self._q(LineStylePanel)
        line_panel.set_class(show_line, "visible")
        if show_line:
            if isinstance(tool, LineTool):
                line_panel.set_active(tool_ctrl.line_style)
            elif is_select:
                styles = [s.line_style for s in selected if isinstance(s, LineShape)]
                if styles:
                    line_panel.set_active(styles[0])

        # Line endings: same visibility as line style
        endings_panel = self._q(LineEndingsPanel)
        endings_panel.set_class(show_line, "visible")
        if show_line:
            if isinstance(tool, LineTool):
                endings_panel.set_active(tool_ctrl.start_ending, tool_ctrl.end_ending)
            elif is_select:
                lines = [s for s in selected if isinstance(s, LineShape)]
                if lines:
                    endings_panel.set_active(lines[0].start_ending, lines[0].end_ending)

        # Text alignment: select with TextShape
        text_shapes = [s for s in selected if isinstance(s, TextShape)]
        text_panel = self._q(TextAlignPanel)
        text_panel.set_class(bool(text_shapes), "visible")
        if text_shapes:
            text_panel.set_active(text_shapes[0].halign, text_shapes[0].valign)

        # Shape align: select with 2+ shapes
        self._q(ShapeAlignPanel).set_class(len(selected) >= 2, "visible")

        # Layer: select with any selection
        self._q(LayerPanel).set_class(bool(selected), "visible")
