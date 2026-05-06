"""Line endings panel: 2-column (start/end) x 5-row (styles) grid of flat Buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Button, Label, Static

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


class LineEndingsPanel(Static):
    """Line endings picker: 5 styles x 2 endpoints (start/end)."""

    DEFAULT_CSS = """
    LineEndingsPanel {
        layout: grid;
        grid-size: 2 7;
        grid-columns: 1fr 1fr;
        grid-rows: 1;
        padding: 0 1;
    }
    LineEndingsPanel Label.panel-label {
        column-span: 2;
        padding: 0;
    }
    LineEndingsPanel Label.endings-col-label {
        height: 1;
        padding: 0;
        text-style: dim;
        content-align: center middle;
        width: 100%;
    }
    LineEndingsPanel EndingButton {
        width: 100%;
        min-width: 3;
        content-align: center middle;
    }
    """

    def __init__(self) -> None:
        super().__init__(classes="panel")

    def compose(self) -> ComposeResult:
        yield Label("Ends", classes="panel-label")
        yield Label("Start", classes="endings-col-label")
        yield Label("End", classes="endings-col-label")
        for style in EndingStyle:
            yield EndingButton(style, "start", id=f"ending-start-{style.name.lower()}")
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
