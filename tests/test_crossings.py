"""Tests for box-drawing crossing resolution and connector bookkeeping."""

from __future__ import annotations

import pytest
from palaterm.connectors import Anchor, Connector, ConnectorManager, Side
from palaterm.crossings import (
    _SB,
    _SL,
    _SR,
    _ST,
    CHAR_TO_MASK,
    MASK_TO_CHAR,
    is_connectable,
    resolve_crossing,
    resolve_crossing_masked,
)

# --- is_connectable ------------------------------------------------------


def test_is_connectable_recognizes_box_chars() -> None:
    """Every char in CHAR_TO_MASK must be considered connectable."""
    for ch in CHAR_TO_MASK:
        assert is_connectable(ch), ch


@pytest.mark.parametrize("ch", ["a", "Z", "0", " ", "*", "█", "▒", "🙂"])
def test_is_connectable_rejects_non_box_chars(ch: str) -> None:
    assert not is_connectable(ch)


# --- resolve_crossing ----------------------------------------------------


@pytest.mark.parametrize(
    "a,b,expected",
    [
        # Horizontal × vertical = cross.
        ("─", "│", "┼"),
        # Heavy horizontal × heavy vertical = heavy cross.
        ("━", "┃", "╋"),
        # Light horizontal × light corner that already includes a vertical leg.
        ("─", "┌", "┬"),
        # Two corners that share a leg add up to a tee.
        ("┌", "┐", "┬"),
        # Two opposite corners → cross.
        ("┌", "┘", "┼"),
    ],
)
def test_resolve_crossing_known_pairs(a: str, b: str, expected: str) -> None:
    assert resolve_crossing(a, b) == expected


@pytest.mark.parametrize(
    "a,b,expected",
    [
        # Double horizontal × double vertical → double cross.
        ("═", "║", "╬"),
        # Double horizontal × double corners → double tees.
        ("═", "╔", "╦"),
        ("═", "╗", "╦"),
        ("═", "╚", "╩"),
        ("═", "╝", "╩"),
        # Double vertical × double corners → double tees.
        ("║", "╔", "╠"),
        ("║", "╗", "╣"),
        # Two double corners sharing a leg → double tee.
        ("╔", "╗", "╦"),
        ("╚", "╝", "╩"),
        ("╔", "╚", "╠"),
        ("╗", "╝", "╣"),
        # Two opposite double corners → double cross.
        ("╔", "╝", "╬"),
        ("╗", "╚", "╬"),
        # Double tee × double opposing leg → double cross.
        ("╠", "╣", "╬"),
        ("╦", "╩", "╬"),
    ],
)
def test_resolve_crossing_double_lines(a: str, b: str, expected: str) -> None:
    assert resolve_crossing(a, b) == expected


@pytest.mark.parametrize(
    "a,b,expected",
    [
        # Heavy horizontal × heavy corners → heavy tees.
        ("━", "┏", "┳"),
        ("━", "┓", "┳"),
        ("━", "┗", "┻"),
        ("━", "┛", "┻"),
        # Heavy vertical × heavy corners → heavy tees.
        ("┃", "┏", "┣"),
        ("┃", "┓", "┫"),
        ("┃", "┗", "┣"),
        ("┃", "┛", "┫"),
        # Two heavy corners sharing a leg → heavy tee.
        ("┏", "┓", "┳"),
        ("┗", "┛", "┻"),
        ("┏", "┗", "┣"),
        ("┓", "┛", "┫"),
        # Two opposite heavy corners → heavy cross.
        ("┏", "┛", "╋"),
        ("┓", "┗", "╋"),
        # Heavy tees combining → heavy cross.
        ("┣", "┫", "╋"),
        ("┳", "┻", "╋"),
    ],
)
def test_resolve_crossing_heavy_lines(a: str, b: str, expected: str) -> None:
    assert resolve_crossing(a, b) == expected


@pytest.mark.parametrize(
    "a,b,expected",
    [
        # Light horizontal × heavy vertical → mixed cross (light h, heavy v).
        ("─", "┃", "╂"),
        # Heavy horizontal × light vertical → mixed cross (heavy h, light v).
        ("━", "│", "┿"),
        # Light horizontal × heavy half-down → mixed T-tee (light h, heavy down).
        ("─", "╻", "┰"),
        # Light horizontal × heavy half-up → mixed ⊥-tee.
        ("─", "╹", "┸"),
        # Heavy horizontal × light half-down → mixed tee.
        ("━", "╷", "┯"),
        # Heavy horizontal × light half-up → mixed tee.
        ("━", "╵", "┷"),
        # Light vertical × heavy half-right → mixed tee (light v, heavy right).
        ("│", "╺", "┝"),
        # Light vertical × heavy half-left → mixed tee.
        ("│", "╸", "┥"),
        # Half-line combos: light-left + heavy-right → ╼ (LIGHT LEFT AND HEAVY RIGHT).
        ("╴", "╺", "╼"),
        # Heavy-left + light-right → ╾ (HEAVY LEFT AND LIGHT RIGHT).
        ("╸", "╶", "╾"),
        # Light-top + heavy-bottom → ╽ (LIGHT UP AND HEAVY DOWN).
        ("╵", "╻", "╽"),
        # Heavy-top + light-bottom → ╿ (HEAVY UP AND LIGHT DOWN).
        ("╹", "╷", "╿"),
    ],
)
def test_resolve_crossing_mixed_light_heavy(a: str, b: str, expected: str) -> None:
    assert resolve_crossing(a, b) == expected


@pytest.mark.parametrize(
    "a,b,expected",
    [
        # Light horizontal × double vertical → mixed cross (light h, double v).
        ("─", "║", "╫"),
        # Double horizontal × light vertical → mixed cross (double h, light v).
        ("═", "│", "╪"),
        # Double horizontal × light half-down → double-top mixed tee.
        ("═", "╷", "╤"),
        # Double horizontal × light half-up → double-bottom mixed tee.
        ("═", "╵", "╧"),
        # Light horizontal × double half-down — only the bottom-leg, no half-line
        # char for double exists, so we use the corners' canonical pieces.
        ("─", "╥", "╥"),  # ╥ already has _SH|_DB; horizontal contributes nothing new.
        # Double vertical × light half-right → mixed tee (light right, double v).
        ("║", "╶", "╟"),
        # Double vertical × light half-left → mixed tee (light left, double v).
        ("║", "╴", "╢"),
        # Light vertical already in ╞ (= _DR|_SV) — overlay is a no-op.
        ("│", "╞", "╞"),
    ],
)
def test_resolve_crossing_mixed_light_double(a: str, b: str, expected: str) -> None:
    assert resolve_crossing(a, b) == expected


@pytest.mark.parametrize(
    "a,b,expected",
    [
        # Rounded corners share masks with light corners — output prefers light.
        ("─", "╭", "┬"),
        ("─", "╮", "┬"),
        ("─", "╰", "┴"),
        ("─", "╯", "┴"),
        ("│", "╭", "├"),
        ("│", "╮", "┤"),
        ("╭", "╯", "┼"),
        ("╮", "╰", "┼"),
    ],
)
def test_resolve_crossing_rounded_corners(a: str, b: str, expected: str) -> None:
    assert resolve_crossing(a, b) == expected


@pytest.mark.parametrize(
    "a,b",
    [
        # Double-line crossings.
        ("═", "║"),
        ("╔", "╝"),
        ("╠", "╣"),
        ("╦", "╩"),
        # Heavy-line crossings.
        ("┏", "┛"),
        ("┣", "┫"),
        # Mixed light/heavy crossings.
        ("─", "┃"),
        ("━", "│"),
        ("╴", "╺"),
        # Mixed light/double crossings.
        ("─", "║"),
        ("═", "│"),
    ],
)
def test_resolve_crossing_is_symmetric_extended(a: str, b: str) -> None:
    """Crossings must commute across all line styles."""
    assert resolve_crossing(a, b) == resolve_crossing(b, a)


@pytest.mark.parametrize(
    "ch",
    [
        # Light, heavy, double, mixed, half-line, rounded — overlaying with
        # itself must not change the character.
        "─",
        "│",
        "┼",
        "┌",
        "├",
        "┬",
        "━",
        "┃",
        "╋",
        "┏",
        "┣",
        "┳",
        "═",
        "║",
        "╬",
        "╔",
        "╠",
        "╦",
        "╼",
        "╾",
        "╽",
        "╿",
        "╴",
        "╶",
        "╵",
        "╷",
        "╸",
        "╺",
        "╹",
        "╻",
        "╭",
        "╮",
        "╰",
        "╯",
    ],
)
def test_resolve_crossing_idempotent(ch: str) -> None:
    """Overlaying a char with itself yields its canonical form."""
    expected = MASK_TO_CHAR[CHAR_TO_MASK[ch]]
    assert resolve_crossing(ch, ch) == expected


@pytest.mark.parametrize(
    "a,b",
    [
        ("─", "│"),
        ("━", "┃"),
        ("┌", "┘"),
        ("├", "┤"),
    ],
)
def test_resolve_crossing_is_symmetric(a: str, b: str) -> None:
    """The order of inputs must not matter — crossings commute."""
    assert resolve_crossing(a, b) == resolve_crossing(b, a)


def test_resolve_crossing_with_non_box_char() -> None:
    """A non-box second char contributes 0 to the mask, so the first wins."""
    assert resolve_crossing("─", "x") == "─"
    assert resolve_crossing("x", "─") == "─"


# --- resolve_crossing_masked ----------------------------------------------


@pytest.mark.parametrize(
    "existing,new,blocked,expected",
    [
        # Block bottom arm of │ when merging with ─ → ┴ (left+right+up)
        ("│", "─", _SB, "┴"),
        # Block top arm of │ when merging with ─ → ┬ (left+right+down)
        ("│", "─", _ST, "┬"),
        # Block left arm of ─ when merging with │ → ├ (right+up+down)
        ("─", "│", _SL, "├"),
        # Block right arm of ─ when merging with │ → ┤ (left+up+down)
        ("─", "│", _SR, "┤"),
        # Block both vertical arms of │ → only new char's mask survives
        ("│", "─", _ST | _SB, "─"),
        # No blocked arms → normal crossing
        ("│", "─", 0, "┼"),
    ],
)
def test_resolve_crossing_masked_t_junctions(
    existing: str, new: str, blocked: int, expected: str
) -> None:
    assert resolve_crossing_masked(existing, new, blocked) == expected


# --- ConnectorManager ----------------------------------------------------


def _conn(
    line_id: str,
    anchor: Anchor,
    target_id: str = "tgt",
    side: Side = Side.LEFT,
    ratio: float = 0.5,
) -> Connector:
    return Connector(
        line_id=line_id, anchor=anchor, target_id=target_id, side=side, ratio=ratio
    )


def test_connector_add_and_get() -> None:
    mgr = ConnectorManager()
    c = _conn("L1", Anchor.START)
    mgr.add(c)
    assert mgr.connectors == [c]
    assert mgr.get_by_line_anchor("L1", Anchor.START) is c
    assert mgr.get_by_line("L1") == [c]


def test_connector_add_dedupes_same_line_and_anchor() -> None:
    """Adding a second connector for the same (line, anchor) replaces the first."""
    mgr = ConnectorManager()
    first = _conn("L1", Anchor.START, target_id="A")
    second = _conn("L1", Anchor.START, target_id="B")
    mgr.add(first)
    mgr.add(second)
    assert len(mgr.connectors) == 1
    assert mgr.connectors[0].target_id == "B"


def test_connector_add_keeps_distinct_anchors() -> None:
    mgr = ConnectorManager()
    start = _conn("L1", Anchor.START, target_id="A")
    end = _conn("L1", Anchor.END, target_id="B")
    mgr.add(start)
    mgr.add(end)
    assert len(mgr.connectors) == 2
    assert mgr.get_by_line_anchor("L1", Anchor.START) is start
    assert mgr.get_by_line_anchor("L1", Anchor.END) is end


def _ids(conns: list[Connector]) -> set[tuple[str, str]]:
    """Identify connectors by (line_id, anchor.name); Connector isn't hashable."""
    return {(c.line_id, c.anchor.name) for c in conns}


def test_connector_remove_by_target_returns_removed() -> None:
    mgr = ConnectorManager()
    a = _conn("L1", Anchor.START, target_id="X")
    b = _conn("L2", Anchor.END, target_id="X")
    c = _conn("L3", Anchor.START, target_id="Y")
    mgr.add(a)
    mgr.add(b)
    mgr.add(c)
    removed = mgr.remove_by_target("X")
    assert _ids(removed) == _ids([a, b])
    assert _ids(mgr.connectors) == _ids([c])


def test_connector_remove_by_line() -> None:
    mgr = ConnectorManager()
    a = _conn("L1", Anchor.START)
    b = _conn("L1", Anchor.END)
    c = _conn("L2", Anchor.START)
    mgr.add(a)
    mgr.add(b)
    mgr.add(c)
    removed = mgr.remove_by_line("L1")
    assert _ids(removed) == _ids([a, b])
    assert _ids(mgr.connectors) == _ids([c])


def test_connector_get_by_target_filters() -> None:
    mgr = ConnectorManager()
    a = _conn("L1", Anchor.START, target_id="X")
    b = _conn("L2", Anchor.START, target_id="X")
    c = _conn("L3", Anchor.START, target_id="Y")
    mgr.add(a)
    mgr.add(b)
    mgr.add(c)
    assert _ids(mgr.get_by_target("X")) == _ids([a, b])
    assert mgr.get_by_target("Z") == []


def test_connector_clear_empties_manager() -> None:
    mgr = ConnectorManager()
    mgr.add(_conn("L1", Anchor.START))
    mgr.add(_conn("L2", Anchor.END))
    mgr.clear()
    assert mgr.connectors == []
