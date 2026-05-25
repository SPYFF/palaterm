"""Export panel with vertically stacked format buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Button

from .collapsible import CollapsiblePanel

_EXPORT_FORMATS = [
    ("Text", "text"),
    ("HTML", "html"),
    ("SVG", "svg"),
    ("Presenterm", "presenterm"),
]


class ExportPanel(CollapsiblePanel):
    """Buttons that copy the canvas to the clipboard in different formats."""

    DEFAULT_CSS = """
    ExportPanel Button {
        width: 100%;
        height: 1;
        padding: 0;
        min-width: 0;
    }
    """

    class ExportRequested(Message):
        def __init__(self, format: str) -> None:
            super().__init__()
            self.format = format

    def __init__(self) -> None:
        super().__init__(title="Export")

    def compose_body(self) -> ComposeResult:
        for label, fmt in _EXPORT_FORMATS:
            yield Button(label, id=f"export-{fmt}", compact=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid and bid.startswith("export-"):
            self.post_message(self.ExportRequested(bid[len("export-") :]))
