"""Always-visible color toolbar for setting the foreground color of selected shapes."""

from __future__ import annotations

from rich.segment import Segment
from rich.style import Style as RichStyle
from textual.events import Click
from textual.message import Message
from textual.strip import Strip
from textual.widget import Widget

_COLORS = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
_BRIGHT = [f"bright_{c}" for c in _COLORS]

_WIDTH = 16
_SWATCH = 2

_TITLE_ROW = 0
_NORMAL_ROW = 1
_BRIGHT_ROW = 2
_DEFAULT_ROW = 3


class ColorToolbar(Widget):
    """Foreground color picker. Pinned to the sidebar bottom; recolors current selection."""

    DEFAULT_CSS = """
    ColorToolbar {
        width: 16;
        height: 4;
        margin-bottom: 0;
    }
    """

    class ColorChanged(Message):
        def __init__(self, color: str | None) -> None:
            super().__init__()
            self.color = color

    def render_line(self, y: int) -> Strip:
        base = self.rich_style
        if y == _TITLE_ROW:
            return Strip([Segment("     Color      ", base + RichStyle(dim=True))])
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
