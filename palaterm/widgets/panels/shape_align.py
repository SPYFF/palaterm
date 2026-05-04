"""Shape alignment grid panel."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Label, Static

_SHAPE_ALIGN_CHARS = [
    ["├", "┼", "┤"],
    ["┬", "─", "┴"],
]
_SHAPE_ALIGN_DIRS = [
    ["left", "center_h", "right"],
    ["top", "center_v", "bottom"],
]


class ShapeAlignCell(Static):
    """A single cell in the shape alignment grid."""

    class Clicked(Message):
        def __init__(self, direction: str) -> None:
            super().__init__()
            self.direction = direction

    def __init__(self, char: str, direction: str, **kwargs) -> None:
        super().__init__(char, **kwargs)
        self.direction = direction

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.direction))


class ShapeAlignButtons(Static):
    """2x3 shape alignment grid, visible when 2+ shapes selected."""

    DEFAULT_CSS = """
    ShapeAlignButtons {
        width: 100%;
        height: auto;
        padding: 0 1;
        display: none;
        layout: grid;
        grid-size: 3 3;
        grid-columns: 1fr 1fr 1fr;
    }
    ShapeAlignButtons.visible {
        display: block;
    }
    ShapeAlignButtons .salign-label {
        column-span: 3;
        width: 100%;
        height: 1;
    }
    ShapeAlignButtons .salign-cell {
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("─ Shape Align ─", classes="salign-label")
        for row in range(2):
            for col in range(3):
                yield ShapeAlignCell(
                    _SHAPE_ALIGN_CHARS[row][col],
                    _SHAPE_ALIGN_DIRS[row][col],
                    classes="salign-cell",
                )
