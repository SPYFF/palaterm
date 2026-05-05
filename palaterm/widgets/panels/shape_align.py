"""Shape alignment panel using flat Buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Button, Label, Static

_ALIGN_ACTIONS = [
    ("├", "left"), ("┼", "center_h"), ("┤", "right"),
    ("┬", "top"), ("─", "center_v"), ("┴", "bottom"),
]


class ShapeAlignPanel(Static):
    """Shape alignment buttons (2 rows of 3)."""

    DEFAULT_CSS = """
    ShapeAlignPanel.visible {
        layout: grid;
        grid-size: 3 3;
        grid-columns: 1fr 1fr 1fr;
    }
    ShapeAlignPanel Label.panel-label {
        column-span: 3;
    }
    ShapeAlignPanel Button {
        width: 100%;
        padding: 0;
    }
    """

    class AlignClicked(Message):
        def __init__(self, direction: str) -> None:
            super().__init__()
            self.direction = direction

    def __init__(self) -> None:
        super().__init__(classes="panel")

    def compose(self) -> ComposeResult:
        yield Label("Align", classes="panel-label")
        for icon, action in _ALIGN_ACTIONS:
            yield Button(icon, id=f"salign-{action}", classes="flat")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action and action.startswith("salign-"):
            direction = action[7:]
            self.post_message(self.AlignClicked(direction))
