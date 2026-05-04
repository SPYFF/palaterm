"""Text alignment grid panel."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Label, Static

from ...shapes import HAlign, VAlign

_ALIGN_CHARS = [
    ["┌", "─", "┐"],
    ["│", "●", "│"],
    ["└", "─", "┘"],
]
_VALIGNS = [VAlign.TOP, VAlign.MIDDLE, VAlign.BOTTOM]
_HALIGNS = [HAlign.LEFT, HAlign.CENTER, HAlign.RIGHT]


class AlignCell(Static):
    """A single cell in the alignment grid."""

    class Clicked(Message):
        def __init__(self, halign: HAlign, valign: VAlign) -> None:
            super().__init__()
            self.halign = halign
            self.valign = valign

    def __init__(self, char: str, halign: HAlign, valign: VAlign, **kwargs) -> None:
        super().__init__(char, **kwargs)
        self.halign = halign
        self.valign = valign

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.halign, self.valign))


class AlignmentGrid(Static):
    """3x3 alignment picker grid."""

    DEFAULT_CSS = """
    AlignmentGrid {
        width: 100%;
        height: auto;
        padding: 0 1;
        display: none;
        layout: grid;
        grid-size: 3 4;
        grid-columns: 1fr 1fr 1fr;
    }
    AlignmentGrid.visible {
        display: block;
    }
    AlignmentGrid .align-label {
        column-span: 3;
        width: 100%;
        height: 1;
    }
    AlignmentGrid .align-cell {
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    AlignmentGrid .align-cell.active {
        background: $accent;
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("─ Text Align ─", classes="align-label")
        for row in range(3):
            for col in range(3):
                yield AlignCell(
                    _ALIGN_CHARS[row][col],
                    _HALIGNS[col],
                    _VALIGNS[row],
                    classes="align-cell",
                )

    def set_active(self, halign: HAlign, valign: VAlign) -> None:
        for cell in self.query(AlignCell):
            cell.set_class(cell.halign == halign and cell.valign == valign, "active")
