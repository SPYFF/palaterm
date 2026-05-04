"""Border style picker panel."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Label, Static

from ...shapes import BorderStyle


class StyleButton(Static):
    """A clickable border style button."""

    class Clicked(Message):
        def __init__(self, style: BorderStyle) -> None:
            super().__init__()
            self.style = style

    def __init__(self, label: str, style: BorderStyle, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self.style = style

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.style))


class StyleButtons(Static):
    """Border style picker, visible for Rectangle/Line tools or selected shapes."""

    DEFAULT_CSS = """
    StyleButtons {
        width: 100%;
        height: auto;
        padding: 0 1;
        display: none;
    }
    StyleButtons.visible {
        display: block;
    }
    StyleButtons .style-btn {
        width: 100%;
        height: 1;
        margin-bottom: 0;
    }
    StyleButtons .style-btn.active {
        background: $accent;
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("── Style ──", classes="style-btn")
        yield StyleButton("┌ Light", BorderStyle.LIGHT, classes="style-btn active")
        yield StyleButton("┏ Heavy", BorderStyle.HEAVY, classes="style-btn")
        yield StyleButton("╔ Double", BorderStyle.DOUBLE, classes="style-btn")
        yield StyleButton("╭ Rounded", BorderStyle.ROUNDED, classes="style-btn")
        yield StyleButton("⡏ Braille", BorderStyle.BRAILLE, classes="style-btn")

    def set_active(self, style: BorderStyle | None) -> None:
        for btn in self.query(StyleButton):
            btn.set_class(style is not None and btn.style == style, "active")
