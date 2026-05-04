"""Select mode options panel."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Label, Static

from ...tools import SelectMode


class OptionButton(Static):
    """A clickable option in the sub-menu."""

    class Clicked(Message):
        def __init__(self, option_id: str) -> None:
            super().__init__()
            self.option_id = option_id

    def __init__(self, label: str, option_id: str, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self.option_id = option_id

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.option_id))


class ToolOptions(Static):
    """Context-aware sub-menu for the active tool."""

    DEFAULT_CSS = """
    ToolOptions {
        dock: bottom;
        width: 100%;
        height: auto;
        padding: 0 1;
        display: none;
    }
    ToolOptions.visible {
        display: block;
    }
    ToolOptions .opt-btn {
        width: 100%;
        height: 1;
        margin-bottom: 0;
    }
    ToolOptions .opt-btn.active {
        background: $accent;
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("── Mode ──", classes="opt-btn")
        yield OptionButton("● Full", "full", classes="opt-btn active")
        yield OptionButton("○ Partial", "partial", classes="opt-btn")

    def set_mode(self, mode: SelectMode) -> None:
        for btn in self.query(OptionButton):
            btn.set_class(
                (btn.option_id == "full" and mode == SelectMode.FULL) or
                (btn.option_id == "partial" and mode == SelectMode.PARTIAL),
                "active",
            )
