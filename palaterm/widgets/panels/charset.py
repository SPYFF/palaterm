"""Character set toggle panel (Unicode / ASCII)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Label, Static

from ...shapes import CharSet


class CharsetButton(Static):
    """A clickable charset button."""

    class Clicked(Message):
        def __init__(self, charset: CharSet) -> None:
            super().__init__()
            self.charset = charset

    def __init__(self, label: str, charset: CharSet, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self.charset = charset

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.charset))


class CharsetButtons(Static):
    """Character set picker: Unicode / ASCII. Always visible."""

    DEFAULT_CSS = """
    CharsetButtons {
        width: 100%;
        height: auto;
        padding: 0 1;
    }
    CharsetButtons .cset-btn {
        width: 100%;
        height: 1;
        margin-bottom: 0;
    }
    CharsetButtons .cset-btn.active {
        background: $accent;
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("── Charset ──", classes="cset-btn")
        yield CharsetButton("⎈ Unicode", CharSet.UNICODE, classes="cset-btn active")
        yield CharsetButton("A ASCII", CharSet.ASCII, classes="cset-btn")

    def set_active(self, charset: CharSet) -> None:
        for btn in self.query(CharsetButton):
            btn.set_class(btn.charset == charset, "active")
