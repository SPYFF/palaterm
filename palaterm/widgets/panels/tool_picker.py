"""Tool selection panel using flat Buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Button, Static

from ...tools import ToolType

_TOOL_LABELS = [
    ("s Select", ToolType.SELECT),
    ("b Box", ToolType.RECTANGLE),
    ("t Text", ToolType.TEXT),
    ("l Line", ToolType.LINE),
]


class ToolPicker(Static):
    """Tool selection via Buttons."""

    DEFAULT_CSS = """
    ToolPicker {
        width: 100%;
        height: auto;
    }
    ToolPicker Button {
        width: 100%;
        text-align: left;
    }
    """

    class ToolSelected(Message):
        def __init__(self, tool_type: ToolType) -> None:
            super().__init__()
            self.tool_type = tool_type

    def compose(self) -> ComposeResult:
        for label, tool_type in _TOOL_LABELS:
            yield Button(label, id=f"tool-{tool_type.name.lower()}", compact=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        for label, tool_type in _TOOL_LABELS:
            if event.button.id == f"tool-{tool_type.name.lower()}":
                self.post_message(self.ToolSelected(tool_type))
                break

    def set_active(self, tool_type: ToolType) -> None:
        for btn in self.query(Button):
            btn.set_class(btn.id == f"tool-{tool_type.name.lower()}", "active")
