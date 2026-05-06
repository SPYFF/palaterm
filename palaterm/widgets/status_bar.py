"""Three-zone status bar widget with charset toggle."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Label

from ..models import CharSet


class StatusBar(Widget):
    """Status bar with left, center, right zones and charset toggle."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $accent;
        color: $text;
        layout: horizontal;
    }
    StatusBar > .status-left {
        width: 1fr;
        padding: 0 1;
    }
    StatusBar > .status-center {
        width: 1fr;
        text-align: center;
    }
    StatusBar > .status-right {
        width: auto;
        padding: 0 1;
    }
    StatusBar Button {
        height: 1;
        min-width: 0;
        border: none;
        padding: 0 1;
        background: transparent;
        width: auto;
    }
    StatusBar Button.active {
        background: $surface;
        text-style: bold;
    }
    """

    class CharsetChanged(Message):
        def __init__(self, charset: CharSet) -> None:
            super().__init__()
            self.charset = charset

    def __init__(self) -> None:
        super().__init__()
        self._left = Label("", classes="status-left")
        self._center = Label("", classes="status-center")
        self._right = Label("", classes="status-right")

    def compose(self) -> ComposeResult:
        yield self._left
        yield self._center
        yield self._right
        yield Button("Uni", id="charset-unicode", compact=True)
        yield Button("Asc", id="charset-ascii", compact=True)

    def on_mount(self) -> None:
        self.query_one("#charset-unicode", Button).add_class("active")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "charset-unicode":
            self.post_message(self.CharsetChanged(CharSet.UNICODE))
        elif event.button.id == "charset-ascii":
            self.post_message(self.CharsetChanged(CharSet.ASCII))

    def set_charset(self, charset: CharSet) -> None:
        uni = self.query_one("#charset-unicode", Button)
        asc = self.query_one("#charset-ascii", Button)
        uni.set_class(charset == CharSet.UNICODE, "active")
        asc.set_class(charset == CharSet.ASCII, "active")

    def update(self, left: str, center: str, right: str) -> None:
        self._left.update(left)
        self._center.update(center)
        self._right.update(right)
