"""Modal screens."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Label, TextArea


class TextEditModal(ModalScreen[str | None]):
    """Modal screen with a TextArea for editing text shape content."""

    DEFAULT_CSS = """
    TextEditModal {
        align: center middle;
    }
    TextEditModal > Vertical {
        width: 60;
        height: 16;
        border: thick $accent;
        background: $surface;
        padding: 1;
    }
    TextEditModal TextArea {
        height: 1fr;
    }
    TextEditModal #hint {
        height: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("enter", "submit", "Submit", priority=True),
    ]

    def __init__(self, initial_text: str = "") -> None:
        super().__init__()
        self._initial = initial_text

    def compose(self) -> ComposeResult:
        with Vertical():
            yield TextArea(self._initial, id="editor")
            yield Label("Enter: save | Shift+Enter: newline | Esc: cancel", id="hint")

    def on_mount(self) -> None:
        self.query_one("#editor", TextArea).focus()

    def on_key(self, event: Key) -> None:
        if event.key == "shift+enter":
            event.prevent_default()
            event.stop()
            self.query_one("#editor", TextArea).insert("\n")

    def action_submit(self) -> None:
        self.dismiss(self.query_one("#editor", TextArea).text)

    def action_cancel(self) -> None:
        self.dismiss(None)


class FilePathModal(ModalScreen[str | None]):
    """Modal for entering a file path."""

    DEFAULT_CSS = """
    FilePathModal {
        align: center middle;
    }
    FilePathModal > Vertical {
        width: 60;
        height: auto;
        max-height: 12;
        border: thick $accent;
        background: $surface;
        padding: 1;
    }
    FilePathModal #prompt_label {
        height: 1;
    }
    FilePathModal #hint {
        height: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    def __init__(self, prompt: str = "File path:", initial: str = "") -> None:
        super().__init__()
        self._prompt = prompt
        self._initial = initial

    def compose(self) -> ComposeResult:
        from textual.widgets import Input
        with Vertical():
            yield Label(self._prompt, id="prompt_label")
            yield Input(self._initial, id="path_input")
            yield Label("Enter: confirm | Escape: cancel", id="hint")

    def on_mount(self) -> None:
        from textual.widgets import Input
        self.query_one("#path_input", Input).focus()

    def on_input_submitted(self, event) -> None:
        self.dismiss(event.value.strip() or None)

    def action_cancel(self) -> None:
        self.dismiss(None)
