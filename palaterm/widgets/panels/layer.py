"""Layer reordering panel using flat Buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Label, Static

_LAYER_ACTIONS = [
    ("⤒", "bring_to_front"),
    ("↑", "bring_forward"),
    ("↓", "send_backward"),
    ("⤓", "send_to_back"),
]


class LayerPanel(Static):
    """Layer reordering buttons, anchored to bottom."""

    DEFAULT_CSS = """
    LayerPanel {
        dock: bottom;
    }
    LayerPanel Horizontal {
        width: 100%;
        height: 1;
    }
    LayerPanel Button {
        width: 1fr;
        padding: 0;
    }
    """

    class LayerAction(Message):
        def __init__(self, action: str) -> None:
            super().__init__()
            self.action = action

    def __init__(self) -> None:
        super().__init__(classes="panel")

    def compose(self) -> ComposeResult:
        yield Label("Layer", classes="panel-label")
        with Horizontal():
            for icon, action in _LAYER_ACTIONS:
                yield Button(icon, id=f"layer-{action}", classes="flat")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action and action.startswith("layer-"):
            self.post_message(self.LayerAction(action[6:]))
