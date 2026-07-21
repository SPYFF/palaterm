"""Layer reordering panel using flat Buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button

from .collapsible import CollapsiblePanel

_LAYER_ACTIONS = [
    ("⤒", "bring_to_front"),
    ("↑", "bring_forward"),
    ("↓", "send_backward"),
    ("⤓", "send_to_back"),
]


class LayerPanel(CollapsiblePanel):
    """Layer reordering buttons."""

    DEFAULT_CSS = """
    LayerPanel #layer-bring_to_front {
        width: 3;
    }
    LayerPanel #layer-bring_forward {
        width: 5;
    }
    LayerPanel #layer-send_backward {
        width: 4;
    }
    LayerPanel #layer-send_to_back {
        width: 3;
    }
    LayerPanel Horizontal {
        height: 1;
    }
    """

    class LayerAction(Message):
        def __init__(self, action: str) -> None:
            super().__init__()
            self.action = action

    def __init__(self) -> None:
        super().__init__(title="Layer", classes="panel")

    def compose_body(self) -> ComposeResult:
        with Horizontal():
            for icon, action in _LAYER_ACTIONS:
                yield Button(icon, id=f"layer-{action}", compact=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action and action.startswith("layer-"):
            self.post_message(self.LayerAction(action[6:]))
