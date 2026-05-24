"""Palaterm - A TUI drawing application."""

from __future__ import annotations

import argparse
import json
import os
import sys

from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import MouseUp

from .commands import AddShape, AddShapes, CommandHistory, MoveLineEdge, MoveShapes, RemoveShapes, TransformShapes
from .controllers import PanelController, ToolController
from .serialization import load_canvas, save_canvas
from .exporters import export_html, export_presenterm, export_svg
from .models import BoxShape, CharSet, EndingStyle, FillStyle, HAlign, LineShape, LineStyle, Shape, VAlign
from .tools import LineTool, RectangleTool, SelectMode, SelectTool, TextTool, ToolType
from .widgets import (
    AlignCell, BorderStylePanel, CanvasWidget, ColorPanel, ConfirmModal, EndingButton,
    ExportPanel, FilePathModal, FillPanel, LayerPanel, LineEndingsPanel, LineStylePanel,
    SelectModePanel, ShapeAlignPanel, StatusBar, TextAlignPanel, ToolPicker,
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
        width: 16;
        height: 100%;
        border-right: solid $accent;
    }
    #sidebar > * {
        margin-bottom: 1;
    }
    #sidebar-spacer {
        height: 1fr;
        margin: 0;
    }
    .panel {
        width: 100%;
        height: auto;
        display: none;
    }
    .panel.visible {
        display: block;
    }
    .panel Horizontal {
        width: 100%;
        height: 1;
    }
    .panel Button {
        padding: 0;
        min-width: 0;
        height: 1;
    }
    #sidebar Button.active {
        background: $surface-darken-1;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("s", "set_tool('select')", "Select", priority=True),
        Binding("b", "set_tool('rect')", "Box", priority=True),
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
        Binding("ctrl+c", "copy", "Copy"),
        Binding("ctrl+x", "cut", "Cut"),
        Binding("ctrl+v", "paste", "Paste"),
        Binding("ctrl+shift+c", "copy", "Copy", priority=True, show=False),
        Binding("ctrl+shift+x", "cut", "Cut", priority=True, show=False),
        Binding("ctrl+shift+v", "paste", "Paste", priority=True, show=False),
        Binding("escape", "deselect", "Deselect", show=False),
        Binding("up", "scroll('up')", "Scroll Up", show=False),
        Binding("down", "scroll('down')", "Scroll Down", show=False),
        Binding("left", "scroll('left')", "Scroll Left", show=False),
        Binding("right", "scroll('right')", "Scroll Right", show=False),
    ]

    def __init__(self, initial_file: str | None = None) -> None:
        super().__init__()
        self.theme = "textual-light" if _terminal_is_light() else "textual-dark"
        self._tool_ctrl = ToolController()
        self._panel_ctrl: PanelController | None = None
        self.history = CommandHistory()
        self._file_path: str | None = None
        self._clipboard: list = []
        self._paste_count: int = 0
        self._initial_file = initial_file

    def compose(self) -> ComposeResult:
        with Vertical(id="sidebar"):
            yield ToolPicker()
            yield SelectModePanel()
            yield BorderStylePanel()
            yield FillPanel()
            yield LineStylePanel()
            yield LineEndingsPanel()
            yield TextAlignPanel()
            yield ShapeAlignPanel()
            yield Vertical(id="sidebar-spacer")
            yield LayerPanel()
            yield ColorPanel()
            yield ExportPanel()
        yield CanvasWidget()
        yield StatusBar()

    def on_mount(self) -> None:
        self._panel_ctrl = PanelController(self.query_one)
        self._canvas_widget = self.query_one(CanvasWidget)
        self._status_bar = self.query_one(StatusBar)
        if self._initial_file:
            self._do_open(self._initial_file)
        self._update_terminal_title()

    @property
    def canvas_widget(self) -> CanvasWidget:
        return self._canvas_widget

    # --- Event handlers (mutate model only, then _update_panels) ---

    def on_canvas_widget_shape_created(self, event: CanvasWidget.ShapeCreated) -> None:
        cmd = AddShape(self.canvas_widget.canvas, event.shape)
        self.history.push(cmd)

    def on_canvas_widget_shape_moved(self, event: CanvasWidget.ShapeMoved) -> None:
        cmd = MoveShapes(event.shapes, event.dcol, event.drow, self.canvas_widget.canvas)
        self.history.push(cmd)

    def on_canvas_widget_shape_resized(self, event: CanvasWidget.ShapeResized) -> None:
        cmd = TransformShapes([(event.shape, event.old_attrs)])
        self.history.push(cmd)

    def on_canvas_widget_line_edge_moved(self, event: CanvasWidget.LineEdgeMoved) -> None:
        cmd = MoveLineEdge(event.line, event.before_joints, event.before_modified)
        self.history.push(cmd)

    def on_tool_picker_tool_selected(self, event: ToolPicker.ToolSelected) -> None:
        self._switch_tool(event.tool_type)

    def on_select_mode_panel_mode_changed(self, event: SelectModePanel.ModeChanged) -> None:
        tool = self.canvas_widget.tool
        if isinstance(tool, SelectTool):
            tool.mode = event.mode
        self._update_panels()

    def on_border_style_panel_style_changed(self, event: BorderStylePanel.StyleChanged) -> None:
        self._tool_ctrl.border_style = event.style
        cw = self.canvas_widget
        tool = cw.tool
        if isinstance(tool, (RectangleTool, TextTool, LineTool)):
            tool.border_style = event.style
        elif isinstance(tool, SelectTool):
            targets = [s for s in tool.selected if isinstance(s, (BoxShape, LineShape))]
            if targets:
                snapshots: list[tuple[Shape, dict[str, Any]]] = [
                    (s, {"border": s.border}) for s in targets
                ]
                for s in targets:
                    s.border = event.style
                self.history.push(TransformShapes(snapshots))
                cw.refresh()
        self._update_panels()

    def on_fill_panel_style_changed(self, event: FillPanel.StyleChanged) -> None:
        self._tool_ctrl.fill = event.style
        cw = self.canvas_widget
        tool = cw.tool
        if isinstance(tool, (RectangleTool, TextTool)):
            tool.fill = event.style
        elif isinstance(tool, SelectTool):
            targets = [s for s in tool.selected if isinstance(s, BoxShape)]
            if targets:
                snapshots: list[tuple[Shape, dict[str, Any]]] = [
                    (s, {"fill": s.fill}) for s in targets
                ]
                for s in targets:
                    s.fill = event.style
                self.history.push(TransformShapes(snapshots))
                cw.refresh()
        self._update_panels()

    def on_line_style_panel_style_changed(self, event: LineStylePanel.StyleChanged) -> None:
        self._tool_ctrl.line_style = event.style
        cw = self.canvas_widget
        tool = cw.tool
        if isinstance(tool, LineTool):
            tool.line_style = event.style
        elif isinstance(tool, SelectTool):
            targets = [s for s in tool.selected if isinstance(s, LineShape)]
            if targets:
                # Switching style invalidates any edge-edited routing — snapshot
                # the modified flag and joint list alongside line_style.
                snapshots: list[tuple[Shape, dict[str, Any]]] = [
                    (s, {
                        "line_style": s.line_style,
                        "_edges_modified": s._edges_modified,
                        "_joint_points": list(s._joint_points),
                    })
                    for s in targets
                ]
                for s in targets:
                    s.line_style = event.style
                    s.reset_edges_modified()
                self.history.push(TransformShapes(snapshots))
                cw.refresh()
        self._update_panels()

    def on_ending_button_clicked(self, event: EndingButton.Clicked) -> None:
        if event.endpoint == "start":
            self._tool_ctrl.start_ending = event.ending
        else:
            self._tool_ctrl.end_ending = event.ending
        cw = self.canvas_widget
        tool = cw.tool
        if isinstance(tool, LineTool):
            tool.start_ending = self._tool_ctrl.start_ending
            tool.end_ending = self._tool_ctrl.end_ending
        elif isinstance(tool, SelectTool):
            targets = [s for s in tool.selected if isinstance(s, LineShape)]
            if targets:
                attr = "start_ending" if event.endpoint == "start" else "end_ending"
                snapshots: list[tuple[Shape, dict[str, Any]]] = [
                    (s, {attr: getattr(s, attr)}) for s in targets
                ]
                for s in targets:
                    setattr(s, attr, event.ending)
                self.history.push(TransformShapes(snapshots))
                cw.refresh()
        self._update_panels()

    def on_align_cell_clicked(self, event: AlignCell.Clicked) -> None:
        cw = self.canvas_widget
        if not isinstance(cw.tool, SelectTool):
            return
        for shape in cw.tool.selected:
            if isinstance(shape, BoxShape):
                shape.halign = event.halign
                shape.valign = event.valign
        cw.refresh()
        self._update_panels()

    def on_shape_align_panel_align_clicked(self, event: ShapeAlignPanel.AlignClicked) -> None:
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

    def on_color_panel_color_changed(self, event: ColorPanel.ColorChanged) -> None:
        cw = self.canvas_widget
        tool = cw.tool
        if not isinstance(tool, SelectTool) or not tool.selected:
            return
        old = [(s, {"fg": s.fg}) for s in tool.selected]
        for s in tool.selected:
            s.fg = event.color
        self.history.push(TransformShapes(old))
        cw.refresh()
        self._update_panels()

    def on_layer_panel_layer_action(self, event: LayerPanel.LayerAction) -> None:
        self.action_layer(event.action)

    def on_status_bar_charset_changed(self, event: StatusBar.CharsetChanged) -> None:
        self._set_charset(event.charset)

    def on_mouse_up(self, event: MouseUp) -> None:
        self._update_panels()
        self._update_status()

    def on_mouse_move(self, event) -> None:
        if self._canvas_widget._mouse_down:
            self._update_status()

    # --- Actions ---

    def _switch_tool(self, tool_type: ToolType) -> None:
        cw = self.canvas_widget
        if cw._editing:
            return
        self._tool_ctrl.active_tool_type = tool_type
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

    def action_deselect(self) -> None:
        cw = self.canvas_widget
        if cw._editing:
            return
        if isinstance(cw.tool, SelectTool) and cw.tool.selected:
            cw.tool.selected = []
            cw.refresh()
            self._update_panels()
            self._update_status()

    def action_quit(self) -> None:
        """Quit, prompting first if there are unsaved changes."""
        if self.canvas_widget._editing:
            return
        if not self.history.is_dirty:
            self.exit()
            return

        def on_dismiss(confirmed: bool) -> None:
            if confirmed:
                self.exit()

        self.push_screen(
            ConfirmModal("Discard unsaved changes and quit?"),
            on_dismiss,
        )

    def action_layer(self, direction: str) -> None:
        cw = self.canvas_widget
        if not isinstance(cw.tool, SelectTool) or not cw.tool.selected:
            return
        for shape in cw.tool.selected:
            getattr(cw.canvas, direction)(shape)
        cw.refresh()

    def action_export(self) -> None:
        self._copy_export("text")

    def on_export_panel_export_requested(self, event: ExportPanel.ExportRequested) -> None:
        self._copy_export(event.format)

    def _copy_export(self, fmt: str) -> None:
        """Render the canvas in ``fmt`` and copy to the system clipboard.

        ``fmt`` is one of ``"text"``, ``"html"``, ``"svg"``. Selection is
        respected: if SelectTool has shapes selected, only those are
        exported; otherwise the whole canvas.
        """
        import pyperclip

        cw = self.canvas_widget
        shapes = None
        if isinstance(cw.tool, SelectTool) and cw.tool.selected:
            shapes = cw.tool.selected

        if fmt == "html":
            out = export_html(cw.canvas, cw.charset, shapes)
            label = "HTML"
        elif fmt == "svg":
            out = export_svg(cw.canvas, cw.charset, shapes)
            label = "SVG"
        elif fmt == "presenterm":
            out = export_presenterm(cw.canvas, cw.charset, shapes)
            label = "presenterm"
        else:
            out = cw.canvas.export_to_text(shapes, cw.charset)
            label = "text"

        if out:
            pyperclip.copy(out)
            self.notify(f"Copied {label} to clipboard!", timeout=2)

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
        self._status_bar.set_charset(charset)
        self.query_one(LineEndingsPanel).set_charset(charset)
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
        if not path.lower().endswith(".palaterm"):
            path = path + ".palaterm"
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
        except FileNotFoundError:
            self.notify(f"No such file: {path}", severity="error", timeout=3)
            return
        except PermissionError:
            self.notify(f"Permission denied: {path}", severity="error", timeout=3)
            return
        except json.JSONDecodeError as e:
            self.notify(f"Not a valid .palaterm file ({e.msg})",
                        severity="error", timeout=3)
            return
        except OSError as e:
            self.notify(f"Open failed: {e}", severity="error", timeout=3)
            return

        cw = self.canvas_widget
        cw.canvas = canvas
        cw._renderer.canvas = canvas
        cw.charset = charset
        self._status_bar.set_charset(charset)
        self.query_one(LineEndingsPanel).set_charset(charset)
        if isinstance(cw.tool, SelectTool):
            cw.tool.selected = []
        self._file_path = path
        self.history = CommandHistory()
        cw.refresh()
        self.notify(f"Opened: {path}", timeout=2)
        self._update_status()

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
            if isinstance(shape, BoxShape) and shape.text:
                shape.halign = cycle[(cycle.index(shape.halign) + 1) % 3]
        cw.refresh()
        self._update_panels()

    def action_cycle_valign(self) -> None:
        cw = self.canvas_widget
        if not isinstance(cw.tool, SelectTool):
            return
        cycle = [VAlign.TOP, VAlign.MIDDLE, VAlign.BOTTOM]
        for shape in cw.tool.selected:
            if isinstance(shape, BoxShape) and shape.text:
                shape.valign = cycle[(cycle.index(shape.valign) + 1) % 3]
        cw.refresh()
        self._update_panels()

    def action_undo(self) -> None:
        if self.history.undo():
            self.canvas_widget.refresh()
            self._update_status()

    def action_redo(self) -> None:
        if self.history.redo():
            self.canvas_widget.refresh()
            self._update_status()

    def action_copy(self) -> None:
        import copy, uuid
        cw = self.canvas_widget
        if not isinstance(cw.tool, SelectTool) or not cw.tool.selected:
            return
        self._clipboard = []
        for s in cw.tool.selected:
            clone = copy.deepcopy(s)
            clone.id = uuid.uuid4().hex[:8]
            self._clipboard.append((s.id, clone))
        self._paste_count = 0

    def action_cut(self) -> None:
        cw = self.canvas_widget
        if not isinstance(cw.tool, SelectTool) or not cw.tool.selected:
            return
        self.action_copy()
        cmd = RemoveShapes(cw.canvas, cw.tool.selected)
        self.history.execute(cmd)
        cw.tool.selected = []
        cw.refresh()
        self._update_status()

    def action_paste(self) -> None:
        import copy, uuid
        from .connectors import Connector

        if not self._clipboard:
            return

        cw = self.canvas_widget
        self._paste_count += 1

        # Clone shapes with new IDs and offset position
        id_map: dict[str, str] = {}
        new_shapes = []
        for orig_id, stored in self._clipboard:
            clone = copy.deepcopy(stored)
            clone.id = uuid.uuid4().hex[:8]
            clone.move(2 * self._paste_count, 1 * self._paste_count)
            id_map[stored.id] = clone.id
            new_shapes.append(clone)

        # Remap connectors that are internal to the copied group
        copied_orig_ids = {orig_id for orig_id, _ in self._clipboard}
        new_connectors = self._remap_connectors(cw.canvas, copied_orig_ids, id_map)

        cmd = AddShapes(cw.canvas, new_shapes, new_connectors)
        self.history.execute(cmd)

        # Select the pasted shapes
        if not isinstance(cw.tool, SelectTool):
            self._switch_tool(ToolType.SELECT)
        cw.tool.selected = new_shapes
        cw.refresh()
        self._update_panels()
        self._update_status()

    # --- Internal ---

    def _remap_connectors(self, canvas, copied_orig_ids: set[str], id_map: dict[str, str]):
        """Create new connectors for lines whose targets are both in the copied group."""
        from .connectors import Connector

        new_connectors: list[Connector] = []
        for orig_id, stored in self._clipboard:
            if not isinstance(stored, LineShape):
                continue
            for conn in canvas.connector_mgr.get_by_line(orig_id):
                if conn.target_id not in copied_orig_ids:
                    continue
                target_stored_id = next(s.id for oid, s in self._clipboard if oid == conn.target_id)
                new_connectors.append(Connector(
                    line_id=id_map[stored.id],
                    anchor=conn.anchor,
                    target_id=id_map[target_stored_id],
                    side=conn.side,
                    ratio=conn.ratio,
                ))
        return new_connectors

    def _update_panels(self) -> None:
        if self._panel_ctrl:
            try:
                self._panel_ctrl.update(self.canvas_widget.tool, self._tool_ctrl)
            except Exception:
                pass

    def _update_status(self) -> None:
        try:
            cw = self.canvas_widget
        except Exception:
            return

        tool_name = self._tool_ctrl.active_tool_type.name.capitalize()
        left = f"Tool: {tool_name}"
        if isinstance(cw.tool, SelectTool):
            mode = "Full" if cw.tool.mode == SelectMode.FULL else "Partial"
            left += f" [{mode}]"
            if cw.tool.selected:
                left += f" Sel: {len(cw.tool.selected)}"
        elif cw._editing:
            left += " [Editing]"

        center = ""
        from .tools import DrawTool
        if isinstance(cw.tool, DrawTool) and cw.tool._start and cw.tool._shape:
            b = cw.tool._shape.bound
            s = cw.tool._start
            center = f"{s.col},{s.row} → {b.right},{b.bottom} ({b.width}×{b.height})"
        elif isinstance(cw.tool, SelectTool):
            if cw.tool.selected:
                bounds = [s.bound for s in cw.tool.selected]
                left_b = min(b.left for b in bounds)
                top_b = min(b.top for b in bounds)
                right_b = max(b.right for b in bounds)
                bottom_b = max(b.bottom for b in bounds)
                w = right_b - left_b + 1
                h = bottom_b - top_b + 1
                center = f"{left_b},{top_b} ({w}×{h})"

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
        self._update_terminal_title()

    def _update_terminal_title(self) -> None:
        """Write OSC 0 to the terminal so its title bar reflects the open file.

        Textual's ``App.title`` reactive only feeds the in-app ``Header``
        widget; without one mounted, the terminal title bar stays
        whatever the surrounding shell put there. We route the OSC
        through Textual's driver so it doesn't interleave with frame
        rendering (writing directly to sys.__stdout__ can corrupt ANSI
        sequences on Windows where output goes through a WriterThread).
        """
        from pathlib import Path
        if self._file_path:
            name = Path(self._file_path).name
        else:
            name = "[new]"
        dirty = "● " if self.history.is_dirty else ""
        try:
            if self._driver is not None:
                self._driver.write(f"\x1b]0;{dirty}palaterm — {name}\x07")
            else:
                sys.__stdout__.write(f"\x1b]0;{dirty}palaterm — {name}\x07")
                sys.__stdout__.flush()
        except (OSError, ValueError):
            pass

    def on_unmount(self) -> None:
        """Reset the terminal title to a sensible default on exit."""
        try:
            if self._driver is not None:
                self._driver.write("\x1b]0;\x07")
            else:
                sys.__stdout__.write("\x1b]0;\x07")
                sys.__stdout__.flush()
        except (OSError, ValueError):
            pass


def main() -> None:
    try:
        from importlib.metadata import version as _pkg_version
        version = _pkg_version("palaterm")
    except Exception:
        version = "unknown"

    parser = argparse.ArgumentParser(
        prog="palaterm",
        description="A TUI drawing application.",
    )
    parser.add_argument(
        "file", nargs="?",
        help="path to a .palaterm file to open at startup",
    )
    parser.add_argument(
        "--version", "-V", action="version", version=f"palaterm {version}",
    )
    args = parser.parse_args()

    app = PalatermApp(initial_file=args.file)
    app.run()


if __name__ == "__main__":
    main()
