"""Border style panel using flat Buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Label

from ...shapes import BorderStyle

_STYLES = [
    ("┌", BorderStyle.LIGHT),
    ("┏", BorderStyle.HEAVY),
    ("╔", BorderStyle.DOUBLE),
    ("╭", BorderStyle.ROUNDED),
    ("⡏", BorderStyle.BRAILLE),
]


class BorderStylePanel(Vertical):
    """Border style picker: 5 icon Buttons in a row."""

    DEFAULT_CSS = """
    BorderStylePanel Horizontal {
        width: auto;
        height: 1;
    }
    BorderStylePanel Button {
        width: 3;
        min-width: 3;
        height: 1;
        padding: 0;
        border: none;
        background: transparent;
        color: $text;
        text-style: none;
        content-align: center middle;
    }
    BorderStylePanel Button:hover {
        background: $surface;
    }
    BorderStylePanel Button.active {
        background: $accent;
        color: $text;
    }
    """

    class StyleChanged(Message):
        def __init__(self, style: BorderStyle) -> None:
            super().__init__()
            self.style = style

    def __init__(self) -> None:
        super().__init__(classes="panel")

    def compose(self) -> ComposeResult:
        yield Label("Border", classes="panel-label")
        with Horizontal():
            for icon, style in _STYLES:
                yield Button(icon, id=f"border-{style.name.lower()}")

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
