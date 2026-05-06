"""Text alignment grid panel using flat Buttons."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Button, Label, Static

from ...models import HAlign, VAlign

_ALIGN_CHARS = [
    ["┌", "─", "┐"],
    ["│", "+", "│"],
    ["└", "─", "┘"],
]
_VALIGNS = [VAlign.TOP, VAlign.MIDDLE, VAlign.BOTTOM]
_HALIGNS = [HAlign.LEFT, HAlign.CENTER, HAlign.RIGHT]


class AlignCell(Button):
    """A flat button tagged with a halign/valign pair."""

    class Clicked(Message):
        def __init__(self, halign: HAlign, valign: VAlign) -> None:
            super().__init__()
            self.halign = halign
            self.valign = valign

    def __init__(self, char: str, halign: HAlign, valign: VAlign, **kwargs) -> None:
        super().__init__(char, compact=True, **kwargs)
        self.halign = halign
        self.valign = valign

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(self.Clicked(self.halign, self.valign))


class TextAlignPanel(Static):
    """3x3 text alignment picker grid."""

    DEFAULT_CSS = """
    TextAlignPanel {
        layout: grid;
        grid-size: 3 4;
        grid-columns: 1fr 1fr 1fr;
    }
    TextAlignPanel Label.panel-label {
        column-span: 3;
    }
    TextAlignPanel AlignCell {
        width: 100%;
        content-align: center middle;
    }
    """

    def __init__(self) -> None:
        super().__init__(classes="panel")

    def compose(self) -> ComposeResult:
        yield Label("Text align", classes="panel-label")
        for row in range(3):
            for col in range(3):
                yield AlignCell(
                    _ALIGN_CHARS[row][col],
                    _HALIGNS[col],
                    _VALIGNS[row],
                )

    def set_active(self, halign: HAlign, valign: VAlign) -> None:
        for cell in self.query(AlignCell):
            cell.set_class(cell.halign == halign and cell.valign == valign, "active")
