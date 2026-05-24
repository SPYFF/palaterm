"""Select tool: click, drag-move, resize, and rectangle-select.

The select tool routes mouse events through a single in-flight ``Gesture``
(see ``gestures.py``) — one gesture per drag, owning its own before-state and
emitting a typed commit on mouse-up. Persistent state stays here: the
selection itself, hover info, the visible rubber-band rect.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Any

from ..geometry import Point, Rect
from ..models import BorderStyle, BoxShape, LineShape, Shape
from .gestures import (
    EdgeDragGesture, Gesture, GestureCommit, LineHandleGesture,
    MoveGesture, RectSelectGesture, ResizeGesture,
)


class SelectMode(Enum):
    FULL = auto()
    PARTIAL = auto()


class SelectTool:
    """Select, move, and resize shapes."""

    def __init__(self) -> None:
        self.selected: list[Shape] = []
        self.hover_shape: Shape | None = None
        self.mode: SelectMode = SelectMode.FULL
        # Rubber-band overlay state — read by the renderer.
        self.selection_rect: Rect | None = None
        self.selection_rect_f: tuple[float, float, float, float] | None = None
        self.selection_anchor: Point | None = None  # mouse-down cell for the band
        self.selection_modifier: str = "none"  # "none" | "add" | "remove"
        # Active drag, or None when no mouse button is held.
        self.gesture: Gesture | None = None
        # Hover state for edge highlighting (rendering reads these).
        self.hover_edge_line: LineShape | None = None
        self.hover_edge_index: int | None = None
        self.hover_edge_whole: bool = False  # corner hover → highlight whole line
        self.hover_handle = None  # Handle enum value when hovering a handle

    # ---- Renderer compatibility shims --------------------------------------
    #
    # The renderer was written against the pre-gesture flag layout. These
    # properties keep the existing reads working while the underlying state
    # moved into Gesture instances.

    @property
    def snap_target(self) -> Any:
        gesture = self.gesture
        if isinstance(gesture, LineHandleGesture):
            return gesture.snap_target
        return None

    @property
    def _drag_start(self) -> Point | None:
        return self.selection_anchor if isinstance(self.gesture, RectSelectGesture) else None

    @property
    def _modifier(self) -> str:
        return self.selection_modifier

    # ---- Mouse handling ----------------------------------------------------

    def on_mouse_down(self, col: int, row: int, canvas, *, ctrl: bool = False, alt: bool = False,
                      pointer_x: float | None = None, pointer_y: float | None = None) -> Shape | None:
        from . import handle_at

        # Resize handle on a selected shape.
        for shape in self.selected:
            h = handle_at(shape, col, row, pointer_x, pointer_y)
            if h is not None:
                self.gesture = self._make_resize_gesture(shape, h)
                return shape

        # Edge-drag: clicking on the interior of a selected multi-segment
        # orthogonal line's edge starts a perpendicular slide of that segment.
        # Joint cells of selected lines fall through to whole-line move below.
        for shape in self.selected:
            if isinstance(shape, LineShape):
                edge_idx = shape.edge_at(col, row)
                if edge_idx is not None:
                    self.gesture = EdgeDragGesture(shape, edge_idx, shape.routing)
                    return shape

        hit = canvas.shape_at(col, row)
        if hit and ctrl:
            if hit not in self.selected:
                self.selected.append(hit)
            return hit
        if hit and alt:
            if hit in self.selected:
                self.selected.remove(hit)
            return None
        if hit and hit in self.selected:
            self.gesture = MoveGesture(list(self.selected), Point(col, row))
            return hit
        if hit:
            self.selected = [hit]
            self.gesture = MoveGesture(list(self.selected), Point(col, row))
            return hit

        if not ctrl and not alt:
            self.selected = []
        modifier = "add" if ctrl else "remove" if alt else "none"
        self.selection_anchor = Point(col, row)
        self.selection_modifier = modifier
        self.selection_rect = None
        self.selection_rect_f = None
        start_f = (pointer_x, pointer_y) if pointer_x is not None and pointer_y is not None else None
        self.gesture = RectSelectGesture(self, Point(col, row), start_f, modifier)
        return self.selected[0] if self.selected else None

    def _make_resize_gesture(self, shape: Shape, handle: Any) -> Gesture:
        from . import Handle

        if isinstance(shape, LineShape):
            old_attrs = {"start": shape.start, "end": shape.end, "routing": shape.routing}
            return LineHandleGesture(shape, handle, old_attrs)

        b = shape.bound
        anchor_map = {
            Handle.TOP_LEFT: Point(b.right, b.bottom),
            Handle.TOP_MID: Point(b.left, b.bottom),
            Handle.TOP_RIGHT: Point(b.left, b.bottom),
            Handle.MID_LEFT: Point(b.right, b.top),
            Handle.MID_RIGHT: Point(b.left, b.top),
            Handle.BOT_LEFT: Point(b.right, b.top),
            Handle.BOT_MID: Point(b.left, b.top),
            Handle.BOT_RIGHT: Point(b.left, b.top),
        }
        anchor = anchor_map.get(handle)

        anchor_f: tuple[float, float] | None = None
        if (isinstance(shape, BoxShape) and shape.border == BorderStyle.BRAILLE
                and shape.rect_f is not None):
            lf, tf, rf, bf = shape.rect_f
            anchor_f_map = {
                Handle.TOP_LEFT: (rf, bf), Handle.TOP_MID: (lf, bf), Handle.TOP_RIGHT: (lf, bf),
                Handle.MID_LEFT: (rf, tf), Handle.MID_RIGHT: (lf, tf),
                Handle.BOT_LEFT: (rf, tf), Handle.BOT_MID: (lf, tf), Handle.BOT_RIGHT: (lf, tf),
            }
            anchor_f = anchor_f_map.get(handle)

        old_attrs = {"rect": shape.rect}  # type: ignore[attr-defined]
        return ResizeGesture(shape, handle, anchor, anchor_f, old_attrs)

    def update_hover(self, col: int, row: int,
                     pointer_x: float | None = None,
                     pointer_y: float | None = None) -> tuple[LineShape | None, int | None, bool]:
        """Recompute edge-hover state for selected lines.

        Returns (line, edge_index, whole_line) tuple matching the new state.
        ``edge_index`` is set when an edge interior is hovered; ``whole_line``
        is True when a corner joint is hovered (whole-line move target).
        """
        from . import handle_at

        new_line: LineShape | None = None
        new_index: int | None = None
        new_whole = False
        new_handle = None
        for shape in self.selected:
            h = handle_at(shape, col, row, pointer_x, pointer_y)
            if h is not None:
                new_handle = h
                break
            if not isinstance(shape, LineShape):
                continue
            edge_idx = shape.edge_at(col, row)
            if edge_idx is not None:
                new_line = shape
                new_index = edge_idx
                break
            joint_idx = shape.joint_at(col, row)
            if joint_idx is not None:
                new_line = shape
                new_whole = True
                break
        self.hover_handle = new_handle
        self.hover_edge_line = new_line
        self.hover_edge_index = new_index
        self.hover_edge_whole = new_whole
        return new_line, new_index, new_whole

    def on_mouse_drag(self, col: int, row: int, canvas, *,
                      pointer_x: float | None = None, pointer_y: float | None = None) -> None:
        if self.gesture is not None:
            self.gesture.update(col, row, canvas,
                                pointer_x=pointer_x, pointer_y=pointer_y)

    def on_mouse_up(self, col: int, row: int, canvas, *, ctrl: bool = False, alt: bool = False,
                    pointer_x: float | None = None, pointer_y: float | None = None) -> GestureCommit | None:
        from .gestures import RectSelectCommit

        gesture = self.gesture
        self.gesture = None
        if gesture is None:
            return None
        commit = gesture.commit(col, row, canvas,
                                pointer_x=pointer_x, pointer_y=pointer_y)
        if isinstance(commit, RectSelectCommit):
            self._apply_rect_select(commit, canvas, ctrl=ctrl, alt=alt)
            self.selection_rect = None
            self.selection_rect_f = None
            self.selection_anchor = None
            self.selection_modifier = "none"
            return None
        return commit

    def _apply_rect_select(self, commit: Any, canvas: Any, *,
                           ctrl: bool, alt: bool) -> None:
        rect = commit.rect
        if rect is None:
            return
        if self.mode == SelectMode.FULL:
            shapes = canvas.shapes_fully_in(rect)
        else:
            shapes = canvas.shapes_partially_in(rect)
        if ctrl:
            for s in shapes:
                if s not in self.selected:
                    self.selected.append(s)
        elif alt:
            for s in shapes:
                if s in self.selected:
                    self.selected.remove(s)
        else:
            self.selected = shapes

    # ---- Bounds for partial repaint ----------------------------------------

    def gesture_dirty_bounds(self, canvas: Any) -> list[Rect]:
        """Bounds the active gesture is currently painting (empty if idle)."""
        return self.gesture.dirty_bounds(canvas) if self.gesture is not None else []
