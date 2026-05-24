"""Fill panel: pick interior treatment for Box shapes."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button

from ...models import FillStyle
from .collapsible import CollapsiblePanel

_STYLES: list[tuple[str, FillStyle]] = [
    ("∅", FillStyle.NONE),
    ("Void", FillStyle.SPACE),
    ("░", FillStyle.LIGHT),
    ("▒", FillStyle.MEDIUM),
    ("█", FillStyle.FULL),
]


class FillPanel(CollapsiblePanel):
    """Fill picker: 5 buttons in a row."""

    DEFAULT_CSS = """
    FillPanel Button {
        width: 1fr;
    }
    FillPanel Horizontal {
        height: 1;
    }
    """

    class StyleChanged(Message):
        def __init__(self, style: FillStyle) -> None:
            super().__init__()
            self.style = style

    def __init__(self) -> None:
        super().__init__(title="Fill", classes="panel")

    def compose_body(self) -> ComposeResult:
        with Horizontal():
            for icon, style in _STYLES:
                yield Button(icon, id=f"fill-{style.name.lower()}", compact=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        for _, style in _STYLES:
            if event.button.id == f"fill-{style.name.lower()}":
                self.post_message(self.StyleChanged(style))
                break

    def set_active(self, style: FillStyle | None) -> None:
        for btn in self.query(Button):
            btn.set_class(
                style is not None and btn.id == f"fill-{style.name.lower()}", "active"
            )
