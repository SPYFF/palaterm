"""Border style panel using flat Buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button

from ...models import BorderStyle
from .collapsible import CollapsiblePanel

_STYLES = [
    ("┌", BorderStyle.LIGHT),
    ("┏", BorderStyle.HEAVY),
    ("╔", BorderStyle.DOUBLE),
    ("╭", BorderStyle.ROUNDED),
    ("⡏", BorderStyle.BRAILLE),
    ("∅", BorderStyle.NONE),
]


class BorderStylePanel(CollapsiblePanel):
    """Border style picker: 5 icon Buttons in a row."""

    DEFAULT_CSS = """
    BorderStylePanel Button {
        width: 1fr;
    }
    BorderStylePanel Horizontal {
        height: 1;
    }
    """

    class StyleChanged(Message):
        def __init__(self, style: BorderStyle) -> None:
            super().__init__()
            self.style = style

    def __init__(self) -> None:
        super().__init__(title="Border", classes="panel")

    def compose_body(self) -> ComposeResult:
        with Horizontal():
            for icon, style in _STYLES[:-1]:
                yield Button(icon, id=f"border-{style.name.lower()}", compact=True)
        with Horizontal():
            yield Button("∅", id="border-none", compact=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        for _, style in _STYLES:
            if event.button.id == f"border-{style.name.lower()}":
                self.post_message(self.StyleChanged(style))
                break

    def set_active(self, style: BorderStyle | None) -> None:
        for btn in self.query(Button):
            btn.set_class(
                style is not None and btn.id == f"border-{style.name.lower()}", "active"
            )
