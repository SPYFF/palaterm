"""Select mode panel (Full/Partial) using flat Buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Button, Label

from ...tools import SelectMode


class SelectModePanel(Vertical):
    """Select mode picker: Full or Partial."""

    DEFAULT_CSS = """
    SelectModePanel {
        height: auto;
    }
    SelectModePanel Button {
        width: 100%;
    }
    """

    class ModeChanged(Message):
        def __init__(self, mode: SelectMode) -> None:
            super().__init__()
            self.mode = mode

    def __init__(self) -> None:
        super().__init__(classes="panel")

    def compose(self) -> ComposeResult:
        yield Label("Select", classes="panel-label")
        yield Button("Full", id="mode-full", compact=True)
        yield Button("Part", id="mode-partial", compact=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        mode = SelectMode.FULL if event.button.id == "mode-full" else SelectMode.PARTIAL
        self.post_message(self.ModeChanged(mode))

    def set_active(self, mode: SelectMode) -> None:
        for btn in self.query(Button):
            is_active = (
                (btn.id == "mode-full" and mode == SelectMode.FULL) or
                (btn.id == "mode-partial" and mode == SelectMode.PARTIAL)
            )
            btn.set_class(is_active, "active")
