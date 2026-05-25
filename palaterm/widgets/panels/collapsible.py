"""Collapsible sidebar panel base class."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.reactive import reactive
from textual.widgets import Static


class _PanelHeader(Horizontal):
    """Header row: triangle indicator on the left, centered title.
    Click toggles parent."""

    DEFAULT_CSS = """
    _PanelHeader {
        width: 100%;
        height: 1;
    }
    _PanelHeader > .panel-triangle {
        width: 1;
        height: 1;
        padding: 0;
    }
    _PanelHeader > .panel-title {
        width: 1fr;
        height: 1;
        padding: 0;
        text-style: dim;
        text-align: center;
    }
    """

    def __init__(self, title: str) -> None:
        super().__init__()
        self._title = title

    def compose(self) -> ComposeResult:
        yield Static("▼", classes="panel-triangle")
        yield Static(self._title, classes="panel-title")

    def set_collapsed(self, collapsed: bool) -> None:
        self.query_one(".panel-triangle", Static).update("▶" if collapsed else "▼")

    def on_click(self, event: Click) -> None:
        event.stop()
        parent = self.parent
        if isinstance(parent, CollapsiblePanel):
            parent.collapsed = not parent.collapsed


class CollapsiblePanel(Vertical):
    """Sidebar panel with a clickable header that hides/shows the body.

    Subclasses override ``compose_body()`` instead of ``compose()`` to add
    children below the header.
    """

    DEFAULT_CSS = """
    CollapsiblePanel {
        height: auto;
    }
    CollapsiblePanel > .panel-body {
        height: auto;
    }
    CollapsiblePanel.collapsed > .panel-body {
        display: none;
    }
    """

    collapsed = reactive(False, init=False)

    def __init__(self, title: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title

    def compose(self) -> ComposeResult:
        yield _PanelHeader(self._title)
        with Vertical(classes="panel-body"):
            yield from self.compose_body()

    def compose_body(self) -> ComposeResult:
        return iter(())

    def watch_collapsed(self, value: bool) -> None:
        self.set_class(value, "collapsed")
        try:
            header = self.query_one(_PanelHeader)
        except Exception:
            return
        header.set_collapsed(value)
