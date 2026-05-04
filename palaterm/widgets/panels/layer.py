"""Layer reordering panel."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Label, Static


class LayerButton(Static):
    """A clickable layer action button."""

    class Clicked(Message):
        def __init__(self, action: str) -> None:
            super().__init__()
            self.action = action

    def __init__(self, label: str, action: str, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self.action = action

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.action))


class LayerButtons(Static):
    """Layer reordering buttons, visible only when select tool has a selection."""

    DEFAULT_CSS = """
    LayerButtons {
        width: 100%;
        height: auto;
        padding: 0 1;
        display: none;
    }
    LayerButtons.visible {
        display: block;
    }
    LayerButtons .layer-btn {
        width: 100%;
        height: 1;
        margin-bottom: 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("── Layer ──", classes="layer-btn")
        yield LayerButton("⤒ Front", "bring_to_front", classes="layer-btn")
        yield LayerButton("↑ Forward", "bring_forward", classes="layer-btn")
        yield LayerButton("↓ Backward", "send_backward", classes="layer-btn")
        yield LayerButton("⤓ Back", "send_to_back", classes="layer-btn")
