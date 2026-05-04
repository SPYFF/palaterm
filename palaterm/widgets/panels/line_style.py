"""Line style picker panel."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Label, Static

from ...shapes import LineStyle


class LineStyleButton(Static):
    """A clickable line style button."""

    class Clicked(Message):
        def __init__(self, line_style: LineStyle) -> None:
            super().__init__()
            self.line_style = line_style

    def __init__(self, label: str, line_style: LineStyle, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self.line_style = line_style

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.line_style))


class LineStyleButtons(Static):
    """Line style picker: orthogonal vs straight (braille)."""

    DEFAULT_CSS = """
    LineStyleButtons {
        width: 100%;
        height: auto;
        padding: 0 1;
        display: none;
    }
    LineStyleButtons.visible {
        display: block;
    }
    LineStyleButtons .lstyle-btn {
        width: 100%;
        height: 1;
        margin-bottom: 0;
    }
    LineStyleButtons .lstyle-btn.active {
        background: $accent;
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("── Line ──", classes="lstyle-btn")
        yield LineStyleButton("⌐ Orthogonal", LineStyle.ORTHOGONAL, classes="lstyle-btn active")
        yield LineStyleButton("⠡ Straight", LineStyle.STRAIGHT, classes="lstyle-btn")

    def set_active(self, line_style: LineStyle) -> None:
        for btn in self.query(LineStyleButton):
            btn.set_class(btn.line_style == line_style, "active")
