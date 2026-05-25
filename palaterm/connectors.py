"""Connector model: tracks line-to-shape connections."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .geometry import Point, Rect


class Side(Enum):
    LEFT = auto()
    TOP = auto()
    RIGHT = auto()
    BOTTOM = auto()


class Anchor(Enum):
    START = auto()
    END = auto()


@dataclass
class Connector:
    """A connection between a line endpoint and a shape edge."""

    line_id: str
    anchor: Anchor
    target_id: str
    side: Side
    ratio: float  # 0.0–1.0 position along the edge


class ConnectorManager:
    """Manages bidirectional lookup of connectors."""

    def __init__(self) -> None:
        self._connectors: list[Connector] = []

    @property
    def connectors(self) -> list[Connector]:
        return self._connectors

    def add(self, connector: Connector) -> None:
        # Remove existing connector for same line+anchor
        self.remove_by_line_anchor(connector.line_id, connector.anchor)
        self._connectors.append(connector)

    def remove_by_line_anchor(self, line_id: str, anchor: Anchor) -> Connector | None:
        for c in self._connectors:
            if c.line_id == line_id and c.anchor == anchor:
                self._connectors.remove(c)
                return c
        return None

    def remove_by_target(self, target_id: str) -> list[Connector]:
        removed = [c for c in self._connectors if c.target_id == target_id]
        self._connectors = [c for c in self._connectors if c.target_id != target_id]
        return removed

    def remove_by_line(self, line_id: str) -> list[Connector]:
        removed = [c for c in self._connectors if c.line_id == line_id]
        self._connectors = [c for c in self._connectors if c.line_id != line_id]
        return removed

    def get_by_target(self, target_id: str) -> list[Connector]:
        return [c for c in self._connectors if c.target_id == target_id]

    def get_by_line_anchor(self, line_id: str, anchor: Anchor) -> Connector | None:
        for c in self._connectors:
            if c.line_id == line_id and c.anchor == anchor:
                return c
        return None

    def get_by_line(self, line_id: str) -> list[Connector]:
        return [c for c in self._connectors if c.line_id == line_id]

    def clear(self) -> None:
        self._connectors.clear()


def point_on_edge(bound: Rect, side: Side, ratio: float) -> Point:
    """Calculate the absolute point on a shape's edge given side and ratio."""
    match side:
        case Side.LEFT:
            row = bound.top + round(ratio * max(bound.height - 1, 0))
            return Point(bound.left, row)
        case Side.RIGHT:
            row = bound.top + round(ratio * max(bound.height - 1, 0))
            return Point(bound.right, row)
        case Side.TOP:
            col = bound.left + round(ratio * max(bound.width - 1, 0))
            return Point(col, bound.top)
        case Side.BOTTOM:
            col = bound.left + round(ratio * max(bound.width - 1, 0))
            return Point(col, bound.bottom)


@dataclass
class SnapResult:
    """Result of snap detection."""

    target_id: str
    side: Side
    ratio: float
    point: Point  # the exact point on the edge


def find_snap(
    col: int, row: int, shapes: list, exclude_id: str | None = None, max_dist: int = 0
) -> SnapResult | None:
    """Find the nearest connectable shape edge within max_dist cells.

    Only Rectangle and Text shapes are connectable.
    Returns None if no snap target found.
    """
    from .models import BoxShape

    best: SnapResult | None = None
    best_dist = max_dist + 1

    for shape in shapes:
        if not isinstance(shape, BoxShape):
            continue
        if exclude_id and shape.id == exclude_id:
            continue

        b = shape.bound
        # Check each side
        for side, dist, ratio in _edge_candidates(col, row, b):
            if dist < best_dist:
                best_dist = dist
                pt = point_on_edge(b, side, ratio)
                best = SnapResult(target_id=shape.id, side=side, ratio=ratio, point=pt)

    return best if best_dist <= max_dist else None


def _edge_candidates(col: int, row: int, b: Rect):
    """Yield (side, distance, ratio) for each edge if the point is within range."""
    # LEFT edge: col near b.left, row within [b.top, b.bottom]
    if b.top <= row <= b.bottom:
        d = abs(col - b.left)
        r = (row - b.top) / max(b.height - 1, 1)
        yield Side.LEFT, d, r
    if b.top <= row <= b.bottom:
        d = abs(col - b.right)
        r = (row - b.top) / max(b.height - 1, 1)
        yield Side.RIGHT, d, r
    # TOP edge: row near b.top, col within [b.left, b.right]
    if b.left <= col <= b.right:
        d = abs(row - b.top)
        r = (col - b.left) / max(b.width - 1, 1)
        yield Side.TOP, d, r
    if b.left <= col <= b.right:
        d = abs(row - b.bottom)
        r = (col - b.left) / max(b.width - 1, 1)
        yield Side.BOTTOM, d, r
