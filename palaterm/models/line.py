"""Line shape with orthogonal and straight modes."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..geometry import Point, Rect
from .base import Shape
from .charset import CharSet
from .enums import (
    ARROW_CHARS,
    ARROW_CHARS_ASCII,
    BORDER_CHARS,
    ENDING_CHARS,
    BorderStyle,
    Direction,
    EndingStyle,
    LineStyle,
)


@dataclass(frozen=True)
class LineRouting:
    """Atomic snapshot of a LineShape's joint path.

    ``joints`` is the full joint sequence including endpoints. ``edges_modified``
    records whether the user has dragged an edge — when True the path is
    authoritative; when False the path was derived from endpoints + side hints
    and ``LineShape._recompute`` is free to regenerate it.

    Bundling the two together is the contract: every place that saves and
    restores a routing must do both at once, or the line ends up half-derived.
    """

    joints: tuple[Point, ...]
    edges_modified: bool


def _reduce_joints(joints: list[Point]) -> list[Point]:
    """Drop redundant joints: collinear triples and zero-length edges."""
    if len(joints) < 3:
        return list(joints)
    out = [joints[0]]
    for i in range(1, len(joints) - 1):
        prev = out[-1]
        curr = joints[i]
        nxt = joints[i + 1]
        if prev.col == curr.col and prev.row == curr.row:
            continue
        # Collinear: prev, curr, nxt all share a row or all share a column.
        if prev.row == curr.row == nxt.row:
            continue
        if prev.col == curr.col == nxt.col:
            continue
        out.append(curr)
    if joints[-1].col != out[-1].col or joints[-1].row != out[-1].row:
        out.append(joints[-1])
    return out


_BRAILLE_DOTS = {
    (0, 0): 0,
    (1, 0): 3,
    (0, 1): 1,
    (1, 1): 4,
    (0, 2): 2,
    (1, 2): 5,
    (0, 3): 6,
    (1, 3): 7,
}


def _braille_line(
    start: Point,
    end: Point,
    start_offset: tuple[int, int] | None = None,
    end_offset: tuple[int, int] | None = None,
) -> dict[tuple[int, int], str]:
    """Render a straight line using braille sub-pixel resolution (2x4 per cell).

    start_offset/end_offset: optional (sub_x, sub_y) offsets within the cell
    (sub_x: 0-1, sub_y: 0-3). If None, defaults to (0, 0).
    """
    sx_off, sy_off = start_offset or (0, 0)
    ex_off, ey_off = end_offset or (0, 0)
    x0, y0 = start.col * 2 + sx_off, start.row * 4 + sy_off
    x1, y1 = end.col * 2 + ex_off, end.row * 4 + ey_off
    cells: dict[tuple[int, int], int] = {}
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        cell_col, sub_x = divmod(x0, 2)
        cell_row, sub_y = divmod(y0, 4)
        bit = _BRAILLE_DOTS[(sub_x, sub_y)]
        key = (cell_col, cell_row)
        cells[key] = cells.get(key, 0) | (1 << bit)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
    return {pos: chr(0x2800 | bits) for pos, bits in cells.items()}


def _braille_offsets(
    start: Point, end: Point
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Compute sub-cell offsets for braille line endpoints based on direction.

    Returns (start_offset, end_offset) where each is (sub_x: 0-1, sub_y: 0-3).
    """
    if start.col == end.col and start.row == end.row:
        return (0, 0), (0, 0)
    dx = end.col - start.col
    dy = end.row - start.row
    # Start: offset toward the direction of travel
    if dx == 0:
        s_off = (0, 0 if dy > 0 else 3)
    elif dy == 0:
        s_off = (0 if dx > 0 else 1, 0)
    else:
        s_off = (0 if dx > 0 else 1, 0 if dy > 0 else 3)
    # End: offset from the direction of arrival
    if dx == 0:
        e_off = (0, 3 if dy > 0 else 0)
    elif dy == 0:
        e_off = (1 if dx > 0 else 0, 0)
    else:
        e_off = (1 if dx > 0 else 0, 3 if dy > 0 else 0)
    return s_off, e_off


def _ascii_slope_char(dxc: int, dyc: int) -> str:
    if dxc == 0 and dyc == 0:
        return "*"
    if dyc == 0:
        return "-"
    if dxc == 0:
        return "|"
    if (dxc > 0 and dyc > 0) or (dxc < 0 and dyc < 0):
        return "\\"
    return "/"


def _ascii_line(start: Point, end: Point) -> dict[tuple[int, int], str]:
    """Render a straight line using ASCII slope characters at cell resolution."""
    x0, y0 = start.col, start.row
    x1, y1 = end.col, end.row
    steps: list[tuple[int, int]] = [(x0, y0)]
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    cx, cy = x0, y0
    while (cx, cy) != (x1, y1):
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            cx += sx
        if e2 < dx:
            err += dx
            cy += sy
        steps.append((cx, cy))

    cells: dict[tuple[int, int], str] = {}
    for i, (x, y) in enumerate(steps):
        if len(steps) == 1:
            ch = "*"
        elif i == 0:
            nxt = steps[1]
            dxc, dyc = nxt[0] - x, nxt[1] - y
            ch = _ascii_slope_char(dxc, dyc)
        else:
            prev = steps[i - 1]
            dxc, dyc = x - prev[0], y - prev[1]
            ch = _ascii_slope_char(dxc, dyc)
        cells[(x, y)] = ch
    return cells


class LineShape(Shape):
    """A line connecting two points."""

    def __init__(
        self,
        start: Point,
        end: Point,
        border: BorderStyle = BorderStyle.LIGHT,
        line_style: LineStyle = LineStyle.ORTHOGONAL,
        start_ending: EndingStyle = EndingStyle.NONE,
        end_ending: EndingStyle = EndingStyle.NONE,
    ):
        super().__init__()
        self.start = start
        self.end = end
        self.border = border
        self.line_style = line_style
        self.start_ending = start_ending
        self.end_ending = end_ending
        self.start_side: str | None = None  # "left"/"right"/"top"/"bottom" or None
        self.end_side: str | None = None
        self.start_sub: tuple[int, int] | None = None  # (sub_x: 0-1, sub_y: 0-3)
        self.end_sub: tuple[int, int] | None = None
        self._joint_points: list[Point] = []
        # Once an edge has been dragged, the joint path becomes authoritative
        # and _recompute() must not rederive it. See docs/adr/0001.
        self._edges_modified: bool = False
        self._recompute()

    def _recompute(self) -> None:
        # Authoritative joints: keep the user's custom routing. Endpoint moves
        # are handled via move_anchor(); _recompute is a no-op past that point.
        if self._edges_modified and self._joint_points:
            self.start = self._joint_points[0]
            self.end = self._joint_points[-1]
            return

        s, e = self.start, self.end
        if s.col == e.col or s.row == e.row:
            # Straight line (single segment)
            self._joint_points = [s, e]
            return

        s_horiz = self._side_is_horizontal(self.start_side)
        e_horiz = self._side_is_horizontal(self.end_side)

        if s_horiz is None and e_horiz is None:
            # No connection info — default horizontal-first
            self._joint_points = [s, Point(e.col, s.row), e]
        elif s_horiz is not None and e_horiz is not None and s_horiz == e_horiz:
            # Same axis — need Z-shape (2 bends)
            if s_horiz:  # both horizontal
                mid_col = (s.col + e.col) // 2
                self._joint_points = [
                    s,
                    Point(mid_col, s.row),
                    Point(mid_col, e.row),
                    e,
                ]
            else:  # both vertical
                mid_row = (s.row + e.row) // 2
                self._joint_points = [
                    s,
                    Point(s.col, mid_row),
                    Point(e.col, mid_row),
                    e,
                ]
        elif s_horiz or (s_horiz is None and not e_horiz):
            # Start goes horizontal, end goes vertical
            # L-shape corner at (e.col, s.row)
            self._joint_points = [s, Point(e.col, s.row), e]
        else:
            # Start goes vertical, end goes horizontal
            # L-shape corner at (s.col, e.row)
            self._joint_points = [s, Point(s.col, e.row), e]

    @property
    def joint_points(self) -> list[Point]:
        return list(self._joint_points)

    @property
    def routing(self) -> LineRouting:
        """Snapshot the current joint path + authoritative-flag together."""
        return LineRouting(tuple(self._joint_points), self._edges_modified)

    @routing.setter
    def routing(self, value: LineRouting) -> None:
        """Restore a previously-snapshotted routing.

        Re-synchronises ``start``/``end`` from the joint sequence and triggers
        a derive pass when the routing isn't authoritative, so the line ends
        up in a valid state regardless of which mode the snapshot was taken in.
        """
        self._joint_points = [Point(p.col, p.row) for p in value.joints]
        self._edges_modified = value.edges_modified
        if self._joint_points:
            self.start = self._joint_points[0]
            self.end = self._joint_points[-1]
        if not self._edges_modified:
            self._recompute()

    def edge_at(self, col: int, row: int) -> int | None:
        """Return the edge index whose interior cell is (col, row), else None.

        Excludes joint cells (corners and endpoints): a corner shared between
        two edges returns None so callers can distinguish corners from edges.
        """
        if self.line_style != LineStyle.ORTHOGONAL or len(self._joint_points) < 3:
            return None
        for joint in self._joint_points:
            if joint.col == col and joint.row == row:
                return None
        for i in range(len(self._joint_points) - 1):
            p1, p2 = self._joint_points[i], self._joint_points[i + 1]
            if p1.row == p2.row == row and min(p1.col, p2.col) < col < max(
                p1.col, p2.col
            ):
                return i
            if p1.col == p2.col == col and min(p1.row, p2.row) < row < max(
                p1.row, p2.row
            ):
                return i
        return None

    def joint_at(self, col: int, row: int) -> int | None:
        """Return the index of the joint at (col, row), else None.

        Endpoints (index 0 and last) are excluded — they have their own handles.
        """
        if self.line_style != LineStyle.ORTHOGONAL or len(self._joint_points) < 3:
            return None
        for i in range(1, len(self._joint_points) - 1):
            p = self._joint_points[i]
            if p.col == col and p.row == row:
                return i
        return None

    def edge_is_horizontal(self, edge_index: int) -> bool:
        p1 = self._joint_points[edge_index]
        p2 = self._joint_points[edge_index + 1]
        return p1.row == p2.row

    def move_edge(self, edge_index: int, point: Point) -> None:
        """Slide an edge perpendicular to itself so it passes through ``point``.

        First/last edges insert a new joint at the anchored endpoint.
        Middle edges translate together with their two corner joints.
        Adjacent collinear edges are merged afterward (reduce pass).
        """
        if edge_index < 0 or edge_index >= len(self._joint_points) - 1:
            return
        joints = list(self._joint_points)
        last_edge = len(joints) - 2
        if edge_index == 0 and edge_index == last_edge:
            # Single-segment line: edge-drag would create a new joint on each
            # end. Out of scope — single-segment is whole-line move.
            return
        is_horiz = self.edge_is_horizontal(edge_index)
        p1 = joints[edge_index]
        p2 = joints[edge_index + 1]

        # Project a joint onto the dragged edge: keep its longitudinal axis,
        # take ``point``'s perpendicular axis. Applied to an endpoint this
        # produces the new corner joint; applied to a non-endpoint it slides
        # that joint onto the new edge line.
        def slide(j: Point) -> Point:
            return Point(j.col, point.row) if is_horiz else Point(point.col, j.row)

        if edge_index == 0:
            joints[1] = slide(p2)
            joints.insert(1, slide(p1))
        elif edge_index == last_edge:
            joints[edge_index] = slide(p1)
            joints.insert(edge_index + 1, slide(p2))
        else:
            joints[edge_index] = slide(p1)
            joints[edge_index + 1] = slide(p2)

        self._joint_points = _reduce_joints(joints)
        self._edges_modified = True
        self.start = self._joint_points[0]
        self.end = self._joint_points[-1]

    def move_anchor(self, anchor: str, new_point: Point) -> None:
        """Move start ('start') or end ('end') endpoint to ``new_point``.

        On unedited lines, falls through to derived recompute. On edited
        lines, slides the endpoint and adjusts the adjacent joint to keep the
        first/last edge straight; if ``new_point`` is off-axis, the reduce
        pass leaves the anchor and a new corner joint as separate points.
        """
        if anchor == "start":
            self.start = new_point
        elif anchor == "end":
            self.end = new_point
        else:
            return
        if not self._edges_modified or len(self._joint_points) < 3:
            self._recompute()
            return

        joints = list(self._joint_points)
        anchor_idx, adj_idx = (0, 1) if anchor == "start" else (-1, -2)
        anchor_pt = joints[anchor_idx]
        adj = joints[adj_idx]
        joints[anchor_idx] = new_point
        # Adjacent joint slides along whichever axis the connecting edge used,
        # keeping that edge straight. If new_point is off-axis the adjacent
        # joint is now the corner.
        if adj.col == anchor_pt.col:
            joints[adj_idx] = Point(new_point.col, adj.row)
        else:
            joints[adj_idx] = Point(adj.col, new_point.row)

        self._joint_points = _reduce_joints(joints)
        self._edges_modified = True
        self.start = self._joint_points[0]
        self.end = self._joint_points[-1]

    def follow_anchor(self, anchor: str, new_point: Point) -> None:
        """Move an endpoint to ``new_point`` and drop any user edge edits.

        Used for connector-follow: when a connected box moves, the line is
        treated like a freshly-routed line — derived joints recomputed from
        scratch using the stored ``start_side``/``end_side`` hints. Any
        user-applied edge customizations are intentionally discarded.
        """
        if anchor == "start":
            self.start = new_point
        elif anchor == "end":
            self.end = new_point
        else:
            return
        self.clear_custom_routing()

    def clear_custom_routing(self) -> None:
        """Discard any user edge edits and re-derive joints from endpoints.

        After this returns the line is in derived mode: subsequent endpoint
        moves rebuild the path, and the joint list is whatever the canonical
        L/Z routing produces from ``start``/``end``/``start_side``/``end_side``.
        """
        self._edges_modified = False
        self._joint_points = []
        self._recompute()

    @staticmethod
    def _side_is_horizontal(side: str | None) -> bool | None:
        """Returns True if side implies horizontal exit,
        False for vertical, None if unset."""
        if side in ("left", "right"):
            return True
        if side in ("top", "bottom"):
            return False
        return None

    @property
    def bound(self) -> Rect:
        if self.line_style == LineStyle.STRAIGHT:
            left = min(self.start.col, self.end.col)
            right = max(self.start.col, self.end.col)
            top = min(self.start.row, self.end.row)
            bottom = max(self.start.row, self.end.row)
            return Rect(left, top, right - left + 1, bottom - top + 1)
        cols = [p.col for p in self._joint_points]
        rows = [p.row for p in self._joint_points]
        left, right = min(cols), max(cols)
        top, bottom = min(rows), max(rows)
        return Rect(left, top, right - left + 1, bottom - top + 1)

    def move(self, dcol: int, drow: int) -> None:
        self.start = Point(self.start.col + dcol, self.start.row + drow)
        self.end = Point(self.end.col + dcol, self.end.row + drow)
        if self._edges_modified:
            self._joint_points = [
                Point(p.col + dcol, p.row + drow) for p in self._joint_points
            ]
        self._recompute()

    def hit_test(self, col: int, row: int) -> bool:
        if self.line_style == LineStyle.STRAIGHT:
            # Cell-resolution traversal makes a stable hit-test
            return (col, row) in _ascii_line(self.start, self.end)
        for i in range(len(self._joint_points) - 1):
            p1 = self._joint_points[i]
            p2 = self._joint_points[i + 1]
            if p1.row == p2.row:
                if row == p1.row and min(p1.col, p2.col) <= col <= max(p1.col, p2.col):
                    return True
            else:
                if col == p1.col and min(p1.row, p2.row) <= row <= max(p1.row, p2.row):
                    return True
        return False

    def render(self, charset: CharSet = CharSet.UNICODE) -> dict[tuple[int, int], str]:
        if self.line_style == LineStyle.STRAIGHT or self.border == BorderStyle.BRAILLE:
            if charset == CharSet.ASCII:
                if self.line_style == LineStyle.STRAIGHT:
                    cells = _ascii_line(self.start, self.end)
                else:
                    cells: dict[tuple[int, int], str] = {}
                    for i in range(len(self._joint_points) - 1):
                        cells.update(
                            _ascii_line(
                                self._joint_points[i], self._joint_points[i + 1]
                            )
                        )
            else:
                if self.line_style == LineStyle.STRAIGHT:
                    default_s, default_e = _braille_offsets(self.start, self.end)
                    s_off = self.start_sub or default_s
                    e_off = self.end_sub or default_e
                    cells = _braille_line(self.start, self.end, s_off, e_off)
                else:
                    # For orthogonal lines we ignore start_sub/end_sub: corners
                    # are integer-cell joints, and per-segment directional
                    # offsets are required at *both* ends of every segment to
                    # avoid sparse dots in the middle of the path.
                    cells = {}
                    pts = self._joint_points
                    for i in range(len(pts) - 1):
                        s_off, e_off = _braille_offsets(pts[i], pts[i + 1])
                        cells.update(_braille_line(pts[i], pts[i + 1], s_off, e_off))
            self._apply_endings(cells, charset)
            return cells

        cells: dict[tuple[int, int], str] = {}
        points = self._joint_points
        tl, tr, bl, br, h, v = BORDER_CHARS[self.border]

        for i in range(len(points) - 1):
            p1, p2 = points[i], points[i + 1]
            if p1.row == p2.row:
                c1, c2 = min(p1.col, p2.col), max(p1.col, p2.col)
                for col in range(c1, c2 + 1):
                    cells[(col, p1.row)] = h
            else:
                r1, r2 = min(p1.row, p2.row), max(p1.row, p2.row)
                for row in range(r1, r2 + 1):
                    cells[(p1.col, row)] = v

        for i in range(1, len(points) - 1):
            p = points[i]
            prev, nxt = points[i - 1], points[i + 1]
            from_left = prev.col < p.col
            from_right = prev.col > p.col
            from_top = prev.row < p.row
            from_bottom = prev.row > p.row
            to_left = nxt.col < p.col
            to_right = nxt.col > p.col
            to_top = nxt.row < p.row
            to_bottom = nxt.row > p.row

            if (from_left or to_left) and (from_bottom or to_bottom):
                cells[(p.col, p.row)] = tr
            elif (from_left or to_left) and (from_top or to_top):
                cells[(p.col, p.row)] = br
            elif (from_right or to_right) and (from_bottom or to_bottom):
                cells[(p.col, p.row)] = tl
            elif (from_right or to_right) and (from_top or to_top):
                cells[(p.col, p.row)] = bl

        if points:
            adj_start = points[1] if len(points) > 1 else points[0]
            adj_end = points[-2] if len(points) > 1 else points[-1]
            if self.start_ending != EndingStyle.NONE:
                direction = self._direction_from_points(adj_start, points[0])
                cells[(points[0].col, points[0].row)] = self._ending_char(
                    self.start_ending, direction, charset
                )
            else:
                cells[(points[0].col, points[0].row)] = self._endpoint_char(
                    points[0], adj_start
                )
            if self.end_ending != EndingStyle.NONE:
                direction = self._direction_from_points(adj_end, points[-1])
                cells[(points[-1].col, points[-1].row)] = self._ending_char(
                    self.end_ending, direction, charset
                )
            else:
                cells[(points[-1].col, points[-1].row)] = self._endpoint_char(
                    points[-1], adj_end, is_end=True
                )

        return cells

    def _apply_endings(
        self, cells: dict[tuple[int, int], str], charset: CharSet
    ) -> None:
        """Apply endpoint styles to straight/braille line cells."""
        if self.line_style == LineStyle.STRAIGHT:
            pts = [self.start, self.end]
        else:
            pts = self._joint_points
        if len(pts) < 2:
            return
        if self.start_ending != EndingStyle.NONE:
            direction = self._direction_from_points(pts[1], pts[0])
            cells[(pts[0].col, pts[0].row)] = self._ending_char(
                self.start_ending, direction, charset
            )
        if self.end_ending != EndingStyle.NONE:
            direction = self._direction_from_points(pts[-2], pts[-1])
            cells[(pts[-1].col, pts[-1].row)] = self._ending_char(
                self.end_ending, direction, charset
            )

    def _endpoint_char(
        self, point: Point, adjacent: Point, is_end: bool = False
    ) -> str:
        if point.col == adjacent.col and point.row == adjacent.row:
            return "•"
        if point.row == adjacent.row:
            if self.border == BorderStyle.HEAVY:
                return "╺" if adjacent.col > point.col else "╸"
            return "╶" if adjacent.col > point.col else "╴"
        if self.border == BorderStyle.HEAVY:
            return "╻" if adjacent.row > point.row else "╹"
        return "╷" if adjacent.row > point.row else "╵"

    def _ending_char(
        self, style: EndingStyle, direction: Direction, charset: CharSet
    ) -> str:
        """Get the character for a given ending style and direction."""
        if style == EndingStyle.ARROW:
            if charset == CharSet.ASCII:
                return ARROW_CHARS_ASCII[direction]
            return ARROW_CHARS[direction]
        if charset == CharSet.ASCII:
            return ENDING_CHARS[style][1]
        return ENDING_CHARS[style][0]

    @staticmethod
    def _direction_from_points(frm: Point, to: Point) -> Direction:
        """Determine compass direction from frm toward to."""
        dc = to.col - frm.col
        dr = to.row - frm.row
        if dc == 0 and dr == 0:
            return Direction.E
        angle = math.atan2(-dr, dc)  # y-axis inverted in terminal
        # Quantize to 8 sectors (each 45°)
        idx = round(angle / (math.pi / 4)) % 8
        return [
            Direction.E,
            Direction.NE,
            Direction.N,
            Direction.NW,
            Direction.W,
            Direction.SW,
            Direction.S,
            Direction.SE,
        ][idx]
