"""Line style panel using flat Buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Button

from ...models import LineStyle
from .collapsible import CollapsiblePanel

_STYLES = [
    ("Orthogonal", LineStyle.ORTHOGONAL),
    ("Straight", LineStyle.STRAIGHT),
]


class LineStylePanel(CollapsiblePanel):
    """Line style picker: Orthogonal or Straight."""

    DEFAULT_CSS = """
    LineStylePanel Button {
        width: 100%;
    }
    """

    class StyleChanged(Message):
        def __init__(self, style: LineStyle) -> None:
            super().__init__()
            self.style = style

    def __init__(self) -> None:
        super().__init__(title="Line", classes="panel")

    def compose_body(self) -> ComposeResult:
        for label, style in _STYLES:
            yield Button(label, id=f"lstyle-{style.name.lower()}", compact=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        for _, style in _STYLES:
            if event.button.id == f"lstyle-{style.name.lower()}":
                self.post_message(self.StyleChanged(style))
                break

    def set_active(self, style: LineStyle) -> None:
        for btn in self.query(Button):
            btn.set_class(btn.id == f"lstyle-{style.name.lower()}", "active")
