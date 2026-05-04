"""Tool switching and state management."""

from __future__ import annotations

from ..shapes import BorderStyle, EndingStyle, LineStyle
from ..tools import LineTool, RectangleTool, SelectTool, TextTool, ToolType


class ToolController:
    """Manages tool creation and persistent style state."""

    def __init__(self) -> None:
        self.border_style = BorderStyle.LIGHT
        self.line_style = LineStyle.ORTHOGONAL
        self.start_ending = EndingStyle.NONE
        self.end_ending = EndingStyle.NONE

    def create_tool(self, tool_type: ToolType):
        match tool_type:
            case ToolType.SELECT:
                return SelectTool()
            case ToolType.RECTANGLE:
                return RectangleTool(self.border_style)
            case ToolType.TEXT:
                return TextTool()
            case ToolType.LINE:
                return LineTool(self.border_style, self.line_style,
                                self.start_ending, self.end_ending)
