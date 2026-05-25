"""Pure state derivation for the Sidebar.

Given the active tool and persistent style state (``ToolController``), produce a
``SidebarState`` describing each Panel's visibility and active value(s). The
view layer (``SidebarView``) consumes the snapshot and applies it to widgets;
this module makes no Textual calls and can be unit-tested directly.

Splitting the computation from the application gives us a real seam — the
test surface is the ``SidebarState`` value, not Textual queries.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import BoxShape, EndingStyle, HAlign, LineShape, VAlign
from .tools import LineTool, RectangleTool, SelectTool, TextTool, ToolType


@dataclass(frozen=True)
class PanelState:
    """Visibility-only Panel state (the active value is implicit)."""

    visible: bool


@dataclass(frozen=True)
class ActivePanelState:
    """Panel with a single ``active`` selection. ``active`` is ``None`` when
    the panel is hidden or no consistent value exists across the selection."""

    visible: bool
    active: object | None = None


@dataclass(frozen=True)
class LineEndingsState:
    visible: bool
    start: EndingStyle | None = None
    end: EndingStyle | None = None


@dataclass(frozen=True)
class TextAlignState:
    visible: bool
    halign: HAlign | None = None
    valign: VAlign | None = None


@dataclass(frozen=True)
class SidebarState:
    tool_picker_active: ToolType
    select_mode: ActivePanelState
    border: ActivePanelState
    fill: ActivePanelState
    line_style: ActivePanelState
    line_endings: LineEndingsState
    text_align: TextAlignState
    shape_align: PanelState
    layer: PanelState


def _common(values: list[object]) -> object | None:
    """Return the unique value if all entries are equal, else ``None``."""
    if not values:
        return None
    first = values[0]
    return first if all(v == first for v in values) else None


def compute_sidebar_state(tool, tool_ctrl) -> SidebarState:
    is_select = isinstance(tool, SelectTool)
    selected = list(tool.selected) if is_select else []

    # Select mode
    if is_select:
        select_mode = ActivePanelState(visible=True, active=tool.mode)
    else:
        select_mode = ActivePanelState(visible=False)

    # Border
    bordered = [s for s in selected if hasattr(s, "border")]
    show_border = isinstance(tool, (RectangleTool, TextTool, LineTool)) or bool(
        bordered
    )
    if isinstance(tool, (RectangleTool, TextTool, LineTool)):
        border_active: object | None = tool_ctrl.border_style
    elif is_select and bordered:
        border_active = _common([s.border for s in bordered])  # type: ignore[attr-defined]
    else:
        border_active = None
    border = ActivePanelState(visible=show_border, active=border_active)

    # Fill
    boxes = [s for s in selected if isinstance(s, BoxShape)]
    show_fill = isinstance(tool, (RectangleTool, TextTool)) or bool(boxes)
    if isinstance(tool, (RectangleTool, TextTool)):
        fill_active: object | None = tool_ctrl.fill
    elif is_select and boxes:
        fill_active = _common([s.fill for s in boxes])
    else:
        fill_active = None
    fill = ActivePanelState(visible=show_fill, active=fill_active)

    # Line style + endings
    lines = [s for s in selected if isinstance(s, LineShape)]
    show_line = isinstance(tool, LineTool) or bool(lines)
    if isinstance(tool, LineTool):
        line_active: object | None = tool_ctrl.line_style
        endings = LineEndingsState(
            visible=True, start=tool_ctrl.start_ending, end=tool_ctrl.end_ending
        )
    elif is_select and lines:
        line_active = lines[0].line_style
        endings = LineEndingsState(
            visible=True, start=lines[0].start_ending, end=lines[0].end_ending
        )
    else:
        line_active = None
        endings = LineEndingsState(visible=show_line)
    line_style = ActivePanelState(visible=show_line, active=line_active)

    # Text align
    text_shapes = [s for s in selected if isinstance(s, BoxShape) and s.text]
    if text_shapes:
        text_align = TextAlignState(
            visible=True, halign=text_shapes[0].halign, valign=text_shapes[0].valign
        )
    else:
        text_align = TextAlignState(visible=False)

    return SidebarState(
        tool_picker_active=tool_ctrl.active_tool_type,
        select_mode=select_mode,
        border=border,
        fill=fill,
        line_style=line_style,
        line_endings=endings,
        text_align=text_align,
        shape_align=PanelState(visible=len(selected) >= 2),
        layer=PanelState(visible=bool(selected)),
    )
