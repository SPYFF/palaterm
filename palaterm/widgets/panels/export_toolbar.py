"""Always-visible export toolbar with Text / HTML / SVG buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Label


_EXPORT_FORMATS = [
    ("TXT", "text"),
    ("HTM", "html"),
    ("SVG", "svg"),
    ("PT",  "presenterm"),
]


class ExportToolbar(Vertical):
    """Three buttons that copy the canvas to the clipboard in different formats."""

    DEFAULT_CSS = """
    ExportToolbar {
        height: 2;
        width: 16;
    }
    ExportToolbar > Horizontal {
        width: 100%;
        height: 1;
    }
    ExportToolbar Button {
        width: 1fr;
        height: 1;
        padding: 0;
        min-width: 0;
    }
    ExportToolbar Label {
        width: 100%;
        height: 1;
        padding: 0;
        text-style: dim;
        text-align: center;
    }
    """

    class ExportRequested(Message):
        def __init__(self, format: str) -> None:
            super().__init__()
            self.format = format

    def compose(self) -> ComposeResult:
        yield Label("Export")
        with Horizontal():
            for label, fmt in _EXPORT_FORMATS:
                yield Button(label, id=f"export-{fmt}", compact=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid and bid.startswith("export-"):
            self.post_message(self.ExportRequested(bid[len("export-"):]))
