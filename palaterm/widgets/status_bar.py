"""Three-zone status bar widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Label


class StatusBar(Widget):
    """Status bar with left, center, and right zones."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $accent;
        color: $text;
        layout: horizontal;
    }
    StatusBar > .status-left {
        width: 1fr;
        padding: 0 1;
    }
    StatusBar > .status-center {
        width: 1fr;
        text-align: center;
    }
    StatusBar > .status-right {
        width: 1fr;
        text-align: right;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._left = Label("", classes="status-left")
        self._center = Label("", classes="status-center")
        self._right = Label("", classes="status-right")

    def compose(self) -> ComposeResult:
        yield self._left
        yield self._center
        yield self._right

    def update(self, left: str, center: str, right: str) -> None:
        self._left.update(left)
        self._center.update(center)
        self._right.update(right)
