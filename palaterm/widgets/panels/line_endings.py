"""Line endings panel: two horizontal rows (start/end) of ending style buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Label

from ...models.charset import CharSet
from ...models.enums import EndingStyle

_UNICODE_GLYPHS = {
    EndingStyle.NONE: "×",
    EndingStyle.ARROW: "▶",
    EndingStyle.SQUARE: "■",
    EndingStyle.CIRCLE: "●",
    EndingStyle.STAR: "*",
}

_ASCII_GLYPHS = {
    EndingStyle.NONE: "x",
    EndingStyle.ARROW: ">",
    EndingStyle.SQUARE: "#",
    EndingStyle.CIRCLE: "o",
    EndingStyle.STAR: "*",
}


def _button_label(ending: EndingStyle, charset: CharSet) -> str:
    glyphs = _UNICODE_GLYPHS if charset == CharSet.UNICODE else _ASCII_GLYPHS
    return glyphs[ending]


class EndingButton(Button):
    """A flat button tagged with an ending style and endpoint."""

    class Clicked(Message):
        def __init__(self, ending: EndingStyle, endpoint: str) -> None:
            super().__init__()
            self.ending = ending
            self.endpoint = endpoint

    def __init__(self, ending: EndingStyle, endpoint: str, **kwargs) -> None:
        super().__init__(_button_label(ending, CharSet.UNICODE), compact=True, **kwargs)
        self.ending = ending
        self.endpoint = endpoint

    def set_charset(self, charset: CharSet) -> None:
        self.label = _button_label(self.ending, charset)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(self.Clicked(self.ending, self.endpoint))


class LineEndingsPanel(Vertical):
    """Line endings picker: 5 styles × 2 rows (start/end)."""

    DEFAULT_CSS = """
    LineEndingsPanel {
        height: auto;
    }
    LineEndingsPanel Button {
        width: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__(classes="panel")

    def compose(self) -> ComposeResult:
        yield Label("Endings", classes="panel-label")
        with Horizontal():
            for style in EndingStyle:
                yield EndingButton(style, "start", id=f"ending-start-{style.name.lower()}")
        with Horizontal():
            for style in EndingStyle:
                yield EndingButton(style, "end", id=f"ending-end-{style.name.lower()}")

    def on_mount(self) -> None:
        self.set_active(EndingStyle.NONE, EndingStyle.NONE)

    def set_active(self, start: EndingStyle, end: EndingStyle) -> None:
        for btn in self.query(EndingButton):
            is_active = (
                (btn.endpoint == "start" and btn.ending == start) or
                (btn.endpoint == "end" and btn.ending == end)
            )
            btn.set_class(is_active, "active")

    def set_charset(self, charset: CharSet) -> None:
        for btn in self.query(EndingButton):
            btn.set_charset(charset)
