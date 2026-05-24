"""Apply a Panel-driven attribute change to a selection.

The Sidebar's Panels (border, fill, line endings, line style, color, …) all
emit a ``StyleChanged``-flavoured message when the user clicks a button. The
work that follows is identical for every Panel: pick the shapes the change
applies to, snapshot the affected attributes, mutate, push a ``TransformShapes``
command, and refresh.

This module is the single place that does that work. App-level handlers
collapse to "filter targets, call ``apply_attribute_change``."
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from .commands import CommandHistory, TransformShapes
from .models.base import Shape


def apply_attribute_change(
    history: CommandHistory,
    targets: Sequence[Shape],
    attr: str,
    new_value: Any,
    *,
    extra_snapshot_attrs: Sequence[str] = (),
    after_set: Callable[[Shape], None] | None = None,
) -> bool:
    """Snapshot, mutate, and push an undoable attribute change.

    ``extra_snapshot_attrs`` lets the caller capture additional state that
    should round-trip with ``attr`` on undo (e.g. line ``routing`` is
    snapshotted alongside ``line_style`` because changing the style
    invalidates the user's edge edits).

    ``after_set`` runs once per shape after ``attr`` is assigned — used for
    secondary mutations like ``LineShape.clear_custom_routing()`` that have
    to happen post-assignment but pre-history-push.

    Returns ``True`` if anything was applied (``targets`` non-empty), else
    ``False`` so callers can branch on whether to refresh the canvas.
    """
    if not targets:
        return False
    snapshots: list[tuple[Shape, dict[str, Any]]] = []
    for shape in targets:
        snap: dict[str, Any] = {attr: getattr(shape, attr)}
        for extra in extra_snapshot_attrs:
            snap[extra] = getattr(shape, extra)
        snapshots.append((shape, snap))
    for shape in targets:
        setattr(shape, attr, new_value)
        if after_set is not None:
            after_set(shape)
    history.push(TransformShapes(snapshots))
    return True
