"""Persistent style state and Sidebar view application.

``ToolController`` carries the style state that survives a tool switch (the
border/fill/line style chosen in the panels) and constructs fresh tools when
the user picks a different one.

``SidebarView`` applies a ``SidebarState`` snapshot to the live Panel widgets.
The state is computed by :func:`palaterm.sidebar_state.compute_sidebar_state`
— a pure function that's the actual test surface. This class is a thin
adapter that just performs the Textual queries.
"""

from __future__ import annotations

from .models import BorderStyle, EndingStyle, FillStyle, LineStyle
from .sidebar_state import SidebarState
from .tools import LineTool, RectangleTool, SelectTool, TextTool, ToolType
from .widgets.panels import (
    BorderStylePanel, FillPanel, LayerPanel, LineEndingsPanel, LineStylePanel,
    SelectModePanel, ShapeAlignPanel, TextAlignPanel, ToolPicker,
)


class ToolController:
    """Manages tool creation and persistent style state."""

    def __init__(self) -> None:
        self.border_style = BorderStyle.LIGHT
        self.fill = FillStyle.NONE
        self.line_style = LineStyle.ORTHOGONAL
        self.start_ending = EndingStyle.NONE
        self.end_ending = EndingStyle.NONE
        self.active_tool_type = ToolType.SELECT

    def create_tool(self, tool_type: ToolType):
        match tool_type:
            case ToolType.SELECT:
                return SelectTool()
            case ToolType.RECTANGLE:
                return RectangleTool(self.border_style, self.fill)
            case ToolType.TEXT:
                return TextTool(self.border_style, self.fill)
            case ToolType.LINE:
                return LineTool(self.border_style, self.line_style,
                                self.start_ending, self.end_ending)


class SidebarView:
    """Applies a ``SidebarState`` snapshot to the Panel widgets."""

    def __init__(self, query_one) -> None:
        self._q = query_one

    def apply(self, state: SidebarState) -> None:
        self._q(ToolPicker).set_active(state.tool_picker_active)

        mode_panel = self._q(SelectModePanel)
        mode_panel.set_class(state.select_mode.visible, "visible")
        if state.select_mode.visible and state.select_mode.active is not None:
            mode_panel.set_active(state.select_mode.active)

        border_panel = self._q(BorderStylePanel)
        border_panel.set_class(state.border.visible, "visible")
        if state.border.visible:
            border_panel.set_active(state.border.active)

        fill_panel = self._q(FillPanel)
        fill_panel.set_class(state.fill.visible, "visible")
        if state.fill.visible:
            fill_panel.set_active(state.fill.active)

        line_panel = self._q(LineStylePanel)
        line_panel.set_class(state.line_style.visible, "visible")
        if state.line_style.visible and state.line_style.active is not None:
            line_panel.set_active(state.line_style.active)

        endings_panel = self._q(LineEndingsPanel)
        endings_panel.set_class(state.line_endings.visible, "visible")
        if (state.line_endings.visible
                and state.line_endings.start is not None
                and state.line_endings.end is not None):
            endings_panel.set_active(state.line_endings.start, state.line_endings.end)

        text_panel = self._q(TextAlignPanel)
        text_panel.set_class(state.text_align.visible, "visible")
        if (state.text_align.visible
                and state.text_align.halign is not None
                and state.text_align.valign is not None):
            text_panel.set_active(state.text_align.halign, state.text_align.valign)

        self._q(ShapeAlignPanel).set_class(state.shape_align.visible, "visible")
        self._q(LayerPanel).set_class(state.layer.visible, "visible")
