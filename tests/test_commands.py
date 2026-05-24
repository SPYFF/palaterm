"""Tests for the undo/redo command stack and shape commands.

Note on usage patterns:
  * ``AddShape`` and ``RemoveShapes`` are typically wired through
    ``CommandHistory.execute(cmd)``: the command applies its mutation,
    history records it.
  * ``MoveShapes`` and ``TransformShapes`` are constructed *after* the
    user has already mutated the shapes (during a drag, etc.) and are
    pushed via ``CommandHistory.push(cmd)``. Their ``execute`` re-applies
    the recorded change after a redo.
"""

from __future__ import annotations

from palaterm.canvas import Canvas
from palaterm.commands import (
    AddShape, AddShapes, CommandHistory, MoveShapes, RemoveShapes,
    TransformShapes,
)
from palaterm.connectors import Anchor, Connector, Side
from palaterm.geometry import Point, Rect
from palaterm.models import BorderStyle, BoxShape, LineShape


# --- helpers -------------------------------------------------------------

def _make_box(canvas_id: str = "b0", x: int = 0, y: int = 0) -> BoxShape:
    box = BoxShape(Rect(x, y, 4, 3), border=BorderStyle.LIGHT)
    box.id = canvas_id
    return box


# --- AddShape ------------------------------------------------------------

def test_add_shape_undo_redo() -> None:
    canvas = Canvas()
    history = CommandHistory()
    box = _make_box()

    history.execute(AddShape(canvas, box))
    assert canvas.shapes == [box]
    assert history.can_undo
    assert not history.can_redo

    history.undo()
    assert canvas.shapes == []
    assert not history.can_undo
    assert history.can_redo

    history.redo()
    assert canvas.shapes == [box]


# --- RemoveShapes --------------------------------------------------------

def test_remove_shapes_undo_restores_position() -> None:
    """After undo, the removed shape lives at its original list index."""
    canvas = Canvas()
    a = _make_box("a", 0, 0)
    b = _make_box("b", 5, 0)
    c = _make_box("c", 10, 0)
    canvas.shapes = [a, b, c]

    history = CommandHistory()
    history.execute(RemoveShapes(canvas, [b]))
    assert [s.id for s in canvas.shapes] == ["a", "c"]

    history.undo()
    # ``b`` must be back at index 1 (between ``a`` and ``c``).
    assert [s.id for s in canvas.shapes] == ["a", "b", "c"]


def test_remove_shapes_undo_restores_connectors() -> None:
    """When a connected shape is removed and undone, its connectors return."""
    canvas = Canvas()
    box = _make_box("box", 0, 0)
    line = LineShape(Point(10, 0), Point(20, 5))
    line.id = "line"
    canvas.shapes = [box, line]
    canvas.connector_mgr.add(Connector(
        line_id="line", anchor=Anchor.START, target_id="box",
        side=Side.RIGHT, ratio=0.5,
    ))

    history = CommandHistory()
    history.execute(RemoveShapes(canvas, [box]))
    assert canvas.connector_mgr.connectors == []

    history.undo()
    assert len(canvas.connector_mgr.connectors) == 1
    conn = canvas.connector_mgr.connectors[0]
    assert conn.line_id == "line"
    assert conn.target_id == "box"


def test_remove_line_undo_restores_line_connectors() -> None:
    """Removing a *line* also removes its anchor connectors; undo restores them."""
    canvas = Canvas()
    box = _make_box("box", 0, 0)
    line = LineShape(Point(10, 0), Point(20, 5))
    line.id = "line"
    canvas.shapes = [box, line]
    canvas.connector_mgr.add(Connector(
        line_id="line", anchor=Anchor.START, target_id="box",
        side=Side.RIGHT, ratio=0.5,
    ))

    history = CommandHistory()
    history.execute(RemoveShapes(canvas, [line]))
    assert canvas.connector_mgr.connectors == []

    history.undo()
    assert len(canvas.connector_mgr.connectors) == 1


# --- MoveShapes ----------------------------------------------------------

def test_move_shapes_undo_restores_position() -> None:
    canvas = Canvas()
    box = _make_box("box", 5, 7)
    canvas.shapes = [box]

    # Tool already moved the shape by (3, 2); now record it.
    box.move(3, 2)
    cmd = MoveShapes([box], 3, 2, canvas)
    history = CommandHistory()
    history.push(cmd)
    assert box.rect.left == 8
    assert box.rect.top == 9

    history.undo()
    assert box.rect.left == 5
    assert box.rect.top == 7

    history.redo()
    assert box.rect.left == 8
    assert box.rect.top == 9


def test_move_shapes_resets_connected_line_to_derived() -> None:
    """Moving a connected box drops the line's user edge edits."""
    from palaterm.geometry import Point as P
    from palaterm.models import LineStyle

    canvas = Canvas()
    box = _make_box("box", 0, 0)
    line = LineShape(P(4, 1), P(20, 5), line_style=LineStyle.ORTHOGONAL)
    line.id = "L"
    line.start_side = "right"
    line.end_side = "left"
    line._recompute()
    line.move_edge(1, P(8, 3))
    assert line.edges_modified
    canvas.shapes = [box, line]
    canvas.connector_mgr.add(Connector(line_id="L", anchor=Anchor.START,
                                       target_id="box", side=Side.RIGHT, ratio=0.5))

    box.move(2, 0)
    cmd = MoveShapes([box], 2, 0, canvas)
    cmd.execute()

    assert not line.edges_modified
    assert line.start.col == 6  # 4 + 2


def test_move_shapes_undo_translates_connected_line_back() -> None:
    """Undo restores box position; connected line follows back via the same reset path.

    Connector-follow is destructive (drops user edge edits); undo does not
    resurrect them — it just runs the reverse translate so the line stays
    glued to the restored box.
    """
    from palaterm.geometry import Point as P
    from palaterm.models import LineStyle

    canvas = Canvas()
    box = _make_box("box", 0, 0)
    line = LineShape(P(4, 1), P(20, 5), line_style=LineStyle.ORTHOGONAL)
    line.id = "L"
    line.start_side = "right"
    line.end_side = "left"
    line._recompute()
    canvas.shapes = [box, line]
    canvas.connector_mgr.add(Connector(line_id="L", anchor=Anchor.START,
                                       target_id="box", side=Side.RIGHT, ratio=0.5))

    box.move(2, 0)
    cmd = MoveShapes([box], 2, 0, canvas)
    cmd.execute()
    assert line.start.col == 6
    history = CommandHistory()
    history.push(cmd)

    history.undo()
    assert line.start == P(4, 1)
    assert not line.edges_modified


# --- TransformShapes -----------------------------------------------------

def test_transform_shapes_undo_restores_attribute() -> None:
    canvas = Canvas()
    box = _make_box("box", 0, 0)
    canvas.shapes = [box]

    # Snapshot the original border, then mutate, then push.
    snapshot = [(box, {"border": BorderStyle.LIGHT})]
    box.border = BorderStyle.HEAVY
    history = CommandHistory()
    history.push(TransformShapes(snapshot))

    history.undo()
    assert box.border is BorderStyle.LIGHT

    history.redo()
    assert box.border is BorderStyle.HEAVY


# --- AddShapes -----------------------------------------------------------

def test_add_shapes_with_connectors() -> None:
    canvas = Canvas()
    box = _make_box("box", 0, 0)
    line = LineShape(Point(10, 0), Point(20, 5))
    line.id = "line"
    conn = Connector(line_id="line", anchor=Anchor.START, target_id="box",
                     side=Side.RIGHT, ratio=0.5)

    history = CommandHistory()
    history.execute(AddShapes(canvas, [box, line], [conn]))
    assert {s.id for s in canvas.shapes} == {"box", "line"}
    assert len(canvas.connector_mgr.connectors) == 1

    history.undo()
    assert canvas.shapes == []
    assert canvas.connector_mgr.connectors == []


# --- CommandHistory plumbing --------------------------------------------

def test_history_dirty_flag_tracks_save_point() -> None:
    canvas = Canvas()
    history = CommandHistory()
    assert not history.is_dirty

    history.execute(AddShape(canvas, _make_box("b1")))
    assert history.is_dirty

    history.mark_saved()
    assert not history.is_dirty

    history.execute(AddShape(canvas, _make_box("b2")))
    assert history.is_dirty


def test_history_undo_returns_false_when_empty() -> None:
    history = CommandHistory()
    assert history.undo() is False
    assert history.redo() is False


def test_push_clears_redo_stack() -> None:
    """A new push after an undo invalidates the redo branch — standard editor behavior."""
    canvas = Canvas()
    history = CommandHistory()
    history.execute(AddShape(canvas, _make_box("a")))
    history.execute(AddShape(canvas, _make_box("b")))
    history.undo()  # `b` goes onto redo stack
    assert history.can_redo

    history.execute(AddShape(canvas, _make_box("c")))
    # The redo stack must be cleared by the new edit.
    assert not history.can_redo
