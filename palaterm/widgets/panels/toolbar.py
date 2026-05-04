"""Tool selection toolbar."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, Static

from ...tools import ToolType


class ToolButton(Static):
    """A clickable tool button."""

    class Selected(Message):
        def __init__(self, tool_type: ToolType) -> None:
            super().__init__()
            self.tool_type = tool_type

    def __init__(self, label: str, tool_type: ToolType, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self.tool_type = tool_type

    def on_click(self) -> None:
        self.post_message(self.Selected(self.tool_type))


class Toolbar(Static):
    """Tool selection sidebar."""

    DEFAULT_CSS = """
    Toolbar {
        width: 100%;
        height: auto;
        padding: 1;
    }
    Toolbar .tool-btn {
        width: 100%;
        height: 3;
        content-align: center middle;
        margin-bottom: 1;
    }
    Toolbar .tool-btn.active {
        background: $accent;
        color: $text;
    }
    """

    active_tool: reactive[ToolType] = reactive(ToolType.SELECT)

    def compose(self) -> ComposeResult:
        yield Label("─ Tools ─", classes="tool-btn")
        yield ToolButton("▢ Select", ToolType.SELECT, classes="tool-btn active")
        yield ToolButton("□ Rect", ToolType.RECTANGLE, classes="tool-btn")
        yield ToolButton("T Text", ToolType.TEXT, classes="tool-btn")
        yield ToolButton("╱ Line", ToolType.LINE, classes="tool-btn")

    def watch_active_tool(self, tool: ToolType) -> None:
        for btn in self.query(ToolButton):
            btn.set_class(btn.tool_type == tool, "active")
