"""Visual overlays a tool wants the renderer to paint.

The renderer used to introspect tools with ``hasattr(tool, 'snap_target')``
and bespoke field checks on ``SelectTool``. This module makes that interface
explicit: each tool returns a typed list via ``overlays()``, and the renderer
dispatches on overlay type.

Two adapters live on this seam today (``DrawTool`` / ``LineTool`` and
``SelectTool``), so the interface is real, not speculative.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..connectors import Side
from ..models import LineShape


@dataclass(frozen=True)
class SnapHighlight:
    """Highlight a snap target's edge on the canvas (line tool / line drag)."""

    target_id: str
    side: Side


@dataclass(frozen=True)
class EdgeHover:
    """Highlight a hovered orthogonal-line edge.

    ``edge_index`` selects an interior segment; ``whole`` (when ``True``)
    means the whole line is highlighted because the user is hovering a
    joint rather than an edge interior.
    """

    line: LineShape
    edge_index: int | None
    whole: bool


Overlay = SnapHighlight | EdgeHover
