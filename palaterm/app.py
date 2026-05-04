"""Palaterm - A TUI drawing application."""

from __future__ import annotations

import os

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import MouseUp

from .commands import AddShape, CommandHistory, MoveShapes, RemoveShapes
from .controllers import PanelController, ToolController
from .serialization import load_canvas, save_canvas
from .shapes import CharSet, HAlign, LineShape, LineStyle, RectangleShape, TextShape, VAlign
from .tools import LineTool, RectangleTool, SelectMode, SelectTool, ToolType
from .widgets import (
    AlignCell, AlignmentGrid, CanvasWidget, CharsetButton, CharsetButtons,
    FilePathModal, LayerButton, LayerButtons,
    LineStyleButton, LineStyleButtons, OptionButton, ShapeAlignButtons,
    ShapeAlignCell, StatusBar, StyleButton, StyleButtons, ToolButton, Toolbar, ToolOptions,
)


def _terminal_is_light() -> bool:
    """Detect if the terminal is using a light background."""
    try:
        import select
        import termios
        import tty

        fd = os.open("/dev/tty", os.O_RDWR)
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            os.write(fd, b"\033]11;?\x1b\\")
            response = b""
            while select.select([fd], [], [], 0.1)[0]:
                response += os.read(fd, 128)
            if b"rgb:" in response:
                rgb_part = response.split(b"rgb:")[1].split(b"\033")[0].split(b"\a")[0]
                components = rgb_part.decode().split("/")
                if len(components) == 3:
                    r = int(components[0][:2], 16)
                    g = int(components[1][:2], 16)
                    b = int(components[2][:2], 16)
                    return 0.299 * r + 0.587 * g + 0.114 * b > 128
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            os.close(fd)
    except (ImportError, OSError, ValueError):
        pass

    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg:
        try:
            return int(colorfgbg.rsplit(";", 1)[-1]) >= 7
        except ValueError:
            pass
    return False


class PalatermApp(App):
    """The main Palaterm application."""

    CSS = """
    Screen {
        layout: horizontal;
    }
    #sidebar {
        width: 14;
        height: 100%;
        border-right: solid $accent;
    }
    """

    BINDINGS = [
        Binding("s", "set_tool('select')", "Select", priority=True),
        Binding("r", "set_tool('rect')", "Rectangle", priority=True),
        Binding("t", "set_tool('text')", "Text", priority=True),
        Binding("l", "set_tool('line')", "Line", priority=True),
        Binding("delete", "delete_shape", "Delete", priority=True),
        Binding("ctrl+e", "export", "Export", priority=True),
        Binding("ctrl+s", "save", "Save", priority=True),
        Binding("ctrl+shift+s", "save_as", "Save As", priority=True),
        Binding("ctrl+o", "open_file", "Open", priority=True),
        Binding("ctrl+u", "toggle_charset", "Charset", priority=True),
        Binding("right_square_bracket", "layer('bring_forward')", "Forward", priority=True),
        Binding("left_square_bracket", "layer('send_backward')", "Backward", priority=True),
        Binding("right_curly_bracket", "layer('bring_to_front')", "To Front", priority=True),
        Binding("left_curly_bracket", "layer('send_to_back')", "To Back", priority=True),
        Binding("q", "quit", "Quit", priority=True),
        Binding("a", "cycle_halign", "H-Align", priority=True),
        Binding("A", "cycle_valign", "V-Align", priority=True),
        Binding("ctrl+z", "undo", "Undo", priority=True),
        Binding("ctrl+y", "redo", "Redo", priority=True),
        Binding("up", "scroll('up')", "Scroll Up", show=False),
        Binding("down", "scroll('down')", "Scroll Down", show=False),
        Binding("left", "scroll('left')", "Scroll Left", show=False),
        Binding("right", "scroll('right')", "Scroll Right", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.theme = "textual-light" if _terminal_is_light() else "textual-dark"
        self._tool_ctrl = ToolController()
        self._panel_ctrl: PanelController | None = None
        self.history = CommandHistory()
        self._file_path: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="sidebar"):
            yield Toolbar()
            yield ToolOptions()
            yield StyleButtons()
            yield LineStyleButtons()
            yield AlignmentGrid()
            yield ShapeAlignButtons()
            yield LayerButtons()
            yield CharsetButtons()
        yield CanvasWidget()
        yield StatusBar()

    def on_mount(self) -> None:
        self._panel_ctrl = PanelController(self.query_one)
        self._canvas_widget = self.query_one(CanvasWidget)
        self._toolbar = self.query_one(Toolbar)
        self._status_bar = self.query_one(StatusBar)
        self._charset_buttons = self.query_one(CharsetButtons)

    @property
    def canvas_widget(self) -> CanvasWidget:
        return self._canvas_widget

    # --- Event handlers ---

    def on_canvas_widget_shape_created(self, event: CanvasWidget.ShapeCreated) -> None:
        cmd = AddShape(self.canvas_widget.canvas, event.shape)
        self.history._undo.append(cmd)
        self.history._redo.clear()

    def on_canvas_widget_shape_moved(self, event: CanvasWidget.ShapeMoved) -> None:
        # Shape already moved by tool; record for undo (reverse the move on undo)
        cmd = MoveShapes(event.shapes, event.dcol, event.drow, self.canvas_widget.canvas)
        self.history._undo.append(cmd)
        self.history._redo.clear()

    def on_tool_button_selected(self, event: ToolButton.Selected) -> None:
        self._switch_tool(event.tool_type)

    def on_option_button_clicked(self, event: OptionButton.Clicked) -> None:
        tool = self.canvas_widget.tool
        if isinstance(tool, SelectTool):
            tool.mode = SelectMode.FULL if event.option_id == "full" else SelectMode.PARTIAL
            self.query_one(ToolOptions).set_mode(tool.mode)
            self._update_status()

    def on_style_button_clicked(self, event: StyleButton.Clicked) -> None:
        self._tool_ctrl.border_style = event.style
        self.query_one(StyleButtons).set_active(event.style)
        cw = self.canvas_widget
        tool = cw.tool
        if isinstance(tool, (RectangleTool, LineTool)):
            tool.border_style = event.style
        elif isinstance(tool, SelectTool):
            for shape in tool.selected:
                if isinstance(shape, (RectangleShape, TextShape)):
                    shape.border = event.style
                elif hasattr(shape, "border"):
                    shape.border = event.style
            cw.refresh()

    def on_charset_button_clicked(self, event: CharsetButton.Clicked) -> None:
        self._set_charset(event.charset)

    def on_line_style_button_clicked(self, event: LineStyleButton.Clicked) -> None:
        self._tool_ctrl.line_style = event.line_style
        self.query_one(LineStyleButtons).set_active(event.line_style)
        cw = self.canvas_widget
        tool = cw.tool
        if isinstance(tool, LineTool):
            tool.line_style = event.line_style
        elif isinstance(tool, SelectTool):
            for shape in tool.selected:
                if isinstance(shape, LineShape):
                    shape.line_style = event.line_style
            cw.refresh()

    def on_align_cell_clicked(self, event: AlignCell.Clicked) -> None:
        cw = self.canvas_widget
        if not isinstance(cw.tool, SelectTool):
            return
        for shape in cw.tool.selected:
            if isinstance(shape, TextShape):
                shape.halign = event.halign
                shape.valign = event.valign
        self.query_one(AlignmentGrid).set_active(event.halign, event.valign)
        cw.refresh()
        self._update_status()

    def on_shape_align_cell_clicked(self, event: ShapeAlignCell.Clicked) -> None:
        cw = self.canvas_widget
        if not isinstance(cw.tool, SelectTool) or len(cw.tool.selected) < 2:
            return
        shapes = cw.tool.selected
        bounds = [s.bound for s in shapes]
        match event.direction:
            case "left":
                target = min(b.left for b in bounds)
                for s, b in zip(shapes, bounds):
                    s.move(target - b.left, 0)
            case "center_h":
                centers = [b.left + b.width // 2 for b in bounds]
                target = sum(centers) // len(centers)
                for s, b in zip(shapes, bounds):
                    s.move(target - (b.left + b.width // 2), 0)
            case "right":
                target = max(b.right for b in bounds)
                for s, b in zip(shapes, bounds):
                    s.move(target - b.right, 0)
            case "top":
                target = min(b.top for b in bounds)
                for s, b in zip(shapes, bounds):
                    s.move(0, target - b.top)
            case "center_v":
                centers = [b.top + b.height // 2 for b in bounds]
                target = sum(centers) // len(centers)
                for s, b in zip(shapes, bounds):
                    s.move(0, target - (b.top + b.height // 2))
            case "bottom":
                target = max(b.bottom for b in bounds)
                for s, b in zip(shapes, bounds):
                    s.move(0, target - b.bottom)
        cw.refresh()

    def on_layer_button_clicked(self, event: LayerButton.Clicked) -> None:
        self.action_layer(event.action)

    def on_mouse_up(self, event: MouseUp) -> None:
        self._update_status()

    def on_mouse_move(self, event) -> None:
        if self._canvas_widget._mouse_down:
            self._update_status()

    # --- Actions ---

    def _switch_tool(self, tool_type: ToolType) -> None:
        cw = self.canvas_widget
        if cw._editing:
            return
        self._toolbar.active_tool = tool_type
        cw.tool = self._tool_ctrl.create_tool(tool_type)
        self._update_panels()
        self._update_status()

    def action_set_tool(self, tool: str) -> None:
        if self.canvas_widget._editing:
            return
        mapping = {"select": ToolType.SELECT, "rect": ToolType.RECTANGLE, "text": ToolType.TEXT, "line": ToolType.LINE}
        self._switch_tool(mapping[tool])

    def action_delete_shape(self) -> None:
        cw = self.canvas_widget
        if cw._editing:
            return
        if isinstance(cw.tool, SelectTool) and cw.tool.selected:
            cmd = RemoveShapes(cw.canvas, cw.tool.selected)
            self.history.execute(cmd)
            cw.tool.selected = []
            cw.refresh()
            self._update_status()

    def action_layer(self, direction: str) -> None:
        cw = self.canvas_widget
        if not isinstance(cw.tool, SelectTool) or not cw.tool.selected:
            return
        for shape in cw.tool.selected:
            getattr(cw.canvas, direction)(shape)
        cw.refresh()

    def action_export(self) -> None:
        import pyperclip

        cw = self.canvas_widget
        shapes = None
        if isinstance(cw.tool, SelectTool) and cw.tool.selected:
            shapes = cw.tool.selected
        text = cw.canvas.export_to_text(shapes, cw.charset)
        if text:
            pyperclip.copy(text)
            self.notify("Copied to clipboard!", timeout=2)

    def action_save(self) -> None:
        if self._file_path:
            self._do_save(self._file_path)
        else:
            self._prompt_save()

    def action_save_as(self) -> None:
        self._prompt_save()

    def action_toggle_charset(self) -> None:
        cw = self.canvas_widget
        new = CharSet.ASCII if cw.charset == CharSet.UNICODE else CharSet.UNICODE
        self._set_charset(new)

    def _set_charset(self, charset: CharSet) -> None:
        cw = self.canvas_widget
        if cw.charset == charset:
            return
        cw.charset = charset
        self._charset_buttons.set_active(charset)
        cw.refresh()
        self._update_status()

    def action_open_file(self) -> None:
        def on_dismiss(path: str | None) -> None:
            if path:
                self._do_open(path)
        self.push_screen(FilePathModal("Open file:", self._file_path or ""), on_dismiss)

    def _prompt_save(self) -> None:
        def on_dismiss(path: str | None) -> None:
            if path:
                self._do_save(path)
        self.push_screen(FilePathModal("Save as:", self._file_path or "drawing.palaterm"), on_dismiss)

    def _do_save(self, path: str) -> None:
        from pathlib import Path
        try:
            save_canvas(self.canvas_widget.canvas, Path(path), self.canvas_widget.charset)
            self._file_path = path
            self.history.mark_saved()
            self.notify(f"Saved: {path}", timeout=2)
            self._update_status()
        except OSError as e:
            self.notify(f"Save failed: {e}", severity="error", timeout=3)

    def _do_open(self, path: str) -> None:
        from pathlib import Path
        try:
            canvas, charset = load_canvas(Path(path))
            cw = self.canvas_widget
            cw.canvas = canvas
            cw._renderer.canvas = canvas
            cw.charset = charset
            self._charset_buttons.set_active(charset)
            if isinstance(cw.tool, SelectTool):
                cw.tool.selected = []
            self._file_path = path
            self.history = CommandHistory()
            cw.refresh()
            self.notify(f"Opened: {path}", timeout=2)
            self._update_status()
        except (OSError, Exception) as e:
            self.notify(f"Open failed: {e}", severity="error", timeout=3)

    def action_scroll(self, direction: str) -> None:
        cw = self.canvas_widget
        match direction:
            case "up":
                cw._scroll_row -= 3
            case "down":
                cw._scroll_row += 3
            case "left":
                cw._scroll_col -= 5
            case "right":
                cw._scroll_col += 5
        cw.refresh()

    def action_cycle_halign(self) -> None:
        cw = self.canvas_widget
        if not isinstance(cw.tool, SelectTool):
            return
        cycle = [HAlign.LEFT, HAlign.CENTER, HAlign.RIGHT]
        for shape in cw.tool.selected:
            if isinstance(shape, TextShape):
                shape.halign = cycle[(cycle.index(shape.halign) + 1) % 3]
        cw.refresh()
        self._update_status()

    def action_cycle_valign(self) -> None:
        cw = self.canvas_widget
        if not isinstance(cw.tool, SelectTool):
            return
        cycle = [VAlign.TOP, VAlign.MIDDLE, VAlign.BOTTOM]
        for shape in cw.tool.selected:
            if isinstance(shape, TextShape):
                shape.valign = cycle[(cycle.index(shape.valign) + 1) % 3]
        cw.refresh()
        self._update_status()

    def action_undo(self) -> None:
        if self.history.undo():
            self.canvas_widget.refresh()
            self._update_status()

    def action_redo(self) -> None:
        if self.history.redo():
            self.canvas_widget.refresh()
            self._update_status()

    # --- Internal ---

    def _update_panels(self) -> None:
        if self._panel_ctrl:
            try:
                self._panel_ctrl.update(
                    self.canvas_widget.tool,
                    self._tool_ctrl.border_style,
                    self._tool_ctrl.line_style,
                )
            except Exception:
                pass

    def _update_status(self) -> None:
        try:
            cw = self.canvas_widget
        except Exception:
            return

        # --- Left zone: tool + tool-specific context ---
        tool_name = self._toolbar.active_tool.name.capitalize()
        left = f"Tool: {tool_name}"
        if isinstance(cw.tool, SelectTool):
            mode = "Full" if cw.tool.mode == SelectMode.FULL else "Partial"
            left += f" [{mode}]"
            if cw.tool.selected:
                left += f" Sel: {len(cw.tool.selected)}"
        elif cw._editing:
            left += " [Editing]"

        # --- Center zone: dimensions / selection bounds / move delta ---
        center = ""
        from .tools import DrawTool
        if isinstance(cw.tool, DrawTool) and cw.tool._start and cw.tool._shape:
            b = cw.tool._shape.bound
            s = cw.tool._start
            center = f"{s.col},{s.row} → {b.right},{b.bottom} ({b.width}×{b.height})"
        elif isinstance(cw.tool, SelectTool):
            if cw.tool._moving and cw._move_start and cw.tool._drag_start:
                # During move — but _drag_start resets each frame, use canvas _move_start
                pass
            elif cw.tool.selected:
                bounds = [s.bound for s in cw.tool.selected]
                left_b = min(b.left for b in bounds)
                top_b = min(b.top for b in bounds)
                right_b = max(b.right for b in bounds)
                bottom_b = max(b.bottom for b in bounds)
                w = right_b - left_b + 1
                h = bottom_b - top_b + 1
                center = f"{left_b},{top_b} ({w}×{h})"

        # --- Right zone: filename + dirty + charset + shape count ---
        from pathlib import Path
        charset_indicator = "U" if cw.charset == CharSet.UNICODE else "A"
        count = len(cw.canvas.shapes)

        if self._file_path:
            dirty = " ●" if self.history.is_dirty else ""
            file_part = f"{Path(self._file_path).name}{dirty}"
        else:
            file_part = "[new]"

        right = f"{file_part} [{charset_indicator}] │ {count} shapes"

        self._update_panels()
        self._status_bar.update(left, center, right)


def main() -> None:
    app = PalatermApp()
    app.run()


if __name__ == "__main__":
    main()
