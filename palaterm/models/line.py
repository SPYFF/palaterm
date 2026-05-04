"""Line shape with orthogonal and straight modes."""

from __future__ import annotations

from ..geometry import Point, Rect
from .base import Shape
from .charset import CharSet, to_ascii
from .enums import BORDER_CHARS, BorderStyle, LineStyle


_BRAILLE_DOTS = {
    (0, 0): 0, (1, 0): 3,
    (0, 1): 1, (1, 1): 4,
    (0, 2): 2, (1, 2): 5,
    (0, 3): 6, (1, 3): 7,
}


def _braille_line(start: Point, end: Point) -> dict[tuple[int, int], str]:
    """Render a straight line using braille sub-pixel resolution (2x4 per cell)."""
    x0, y0 = start.col * 2, start.row * 4
    x1, y1 = end.col * 2, end.row * 4
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

    def __init__(self, start: Point, end: Point, border: BorderStyle = BorderStyle.LIGHT,
                 line_style: LineStyle = LineStyle.ORTHOGONAL):
        super().__init__()
        self.start = start
        self.end = end
        self.border = border
        self.line_style = line_style
        self._joint_points: list[Point] = []
        self._recompute()

    def _recompute(self) -> None:
        s, e = self.start, self.end
        self._joint_points = [s]
        if s.col != e.col and s.row != e.row:
            self._joint_points.append(Point(e.col, s.row))
        self._joint_points.append(e)

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
                    return _ascii_line(self.start, self.end)
                # Orthogonal braille in ASCII: render each segment
                cells: dict[tuple[int, int], str] = {}
                for i in range(len(self._joint_points) - 1):
                    cells.update(_ascii_line(self._joint_points[i], self._joint_points[i + 1]))
                return cells
            if self.line_style == LineStyle.STRAIGHT:
                return _braille_line(self.start, self.end)
            # Orthogonal braille: render each segment
            cells = {}
            for i in range(len(self._joint_points) - 1):
                cells.update(_braille_line(self._joint_points[i], self._joint_points[i + 1]))
            return cells

        cells: dict[tuple[int, int], str] = {}
        points = self._joint_points
        tl, tr, bl, br, h, v = BORDER_CHARS[self.border]
        if charset == CharSet.ASCII:
            tl, tr, bl, br, h, v = (to_ascii(c) for c in (tl, tr, bl, br, h, v))

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
            cells[(points[0].col, points[0].row)] = self._endpoint_char(
                points[0], points[1] if len(points) > 1 else points[0], charset
            )
            cells[(points[-1].col, points[-1].row)] = self._endpoint_char(
                points[-1], points[-2] if len(points) > 1 else points[-1], charset, is_end=True
            )

        return cells

    def _endpoint_char(self, point: Point, adjacent: Point,
                       charset: CharSet = CharSet.UNICODE, is_end: bool = False) -> str:
        _, _, _, _, h, v = BORDER_CHARS[self.border]
        if charset == CharSet.ASCII:
            h, v = to_ascii(h), to_ascii(v)
        if point.col == adjacent.col and point.row == adjacent.row:
            return "*" if charset == CharSet.ASCII else "•"
        if point.row == adjacent.row:
            return h
        return v
