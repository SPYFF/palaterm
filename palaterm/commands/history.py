"""Undo/redo history stack."""

from __future__ import annotations

from .base import Command


class CommandHistory:
    """Manages undo/redo stacks."""

    def __init__(self) -> None:
        self._undo: list[Command] = []
        self._redo: list[Command] = []
        self._save_point: int = 0

    def mark_saved(self) -> None:
        self._save_point = len(self._undo)

    @property
    def is_dirty(self) -> bool:
        return len(self._undo) != self._save_point

    def execute(self, cmd: Command) -> None:
        cmd.execute()
        self._undo.append(cmd)
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        cmd = self._undo.pop()
        cmd.undo()
        self._redo.append(cmd)
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        cmd = self._redo.pop()
        cmd.execute()
        self._undo.append(cmd)
        return True

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)
