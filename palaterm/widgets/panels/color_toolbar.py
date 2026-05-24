"""Color panel for setting the foreground color of selected shapes."""

from __future__ import annotations

from rich.segment import Segment
from rich.style import Style as RichStyle
from textual.app import ComposeResult
from textual.events import Click
from textual.message import Message
from textual.strip import Strip
from textual.widget import Widget

from .collapsible import CollapsiblePanel

_COLORS = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
_BRIGHT = [f"bright_{c}" for c in _COLORS]

_WIDTH = 16
_SWATCH = 2

_NORMAL_ROW = 0
_BRIGHT_ROW = 1
_DEFAULT_ROW = 2


class ColorSwatchGrid(Widget):
    """Two rows of color swatches plus a 'default' reset row."""

    DEFAULT_CSS = """
    ColorSwatchGrid {
        width: 16;
        height: 3;
    }
    """

    class ColorChanged(Message):
        def __init__(self, color: str | None) -> None:
            super().__init__()
            self.color = color

    def render_line(self, y: int) -> Strip:
        base = self.rich_style
        if y == _NORMAL_ROW:
            return Strip([Segment("  ", base + RichStyle(bgcolor=c)) for c in _COLORS])
        if y == _BRIGHT_ROW:
            return Strip([Segment("  ", base + RichStyle(bgcolor=c)) for c in _BRIGHT])
        if y == _DEFAULT_ROW:
            return Strip([Segment("    default    ", base)])
        return Strip([Segment(" " * _WIDTH, base)])

    def on_click(self, event: Click) -> None:
        y = event.y
        if y == _NORMAL_ROW and 0 <= event.x < _WIDTH:
            self.post_message(self.ColorChanged(_COLORS[event.x // _SWATCH]))
        elif y == _BRIGHT_ROW and 0 <= event.x < _WIDTH:
            self.post_message(self.ColorChanged(_BRIGHT[event.x // _SWATCH]))
        elif y == _DEFAULT_ROW:
            self.post_message(self.ColorChanged(None))


class ColorPanel(CollapsiblePanel):
    """Foreground color picker panel."""

    DEFAULT_CSS = """
    ColorPanel {
        width: 16;
    }
    """

    class ColorChanged(Message):
        def __init__(self, color: str | None) -> None:
            super().__init__()
            self.color = color

    def __init__(self) -> None:
        super().__init__(title="Color")

    def compose_body(self) -> ComposeResult:
        yield ColorSwatchGrid()

    def on_color_swatch_grid_color_changed(
        self, event: ColorSwatchGrid.ColorChanged
    ) -> None:
        event.stop()
        self.post_message(self.ColorChanged(event.color))
