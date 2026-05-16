"""Tests for the text / HTML / SVG / presenterm exporters."""

from __future__ import annotations

import re

import pytest

from palaterm.canvas import Canvas
from palaterm.geometry import Rect
from palaterm.models import BorderStyle, BoxShape, CharSet, FillStyle
from palaterm.exporters import (
    _RICH_TO_CSS, export_html, export_presenterm, export_svg, to_css,
)


# --- shared helpers --------------------------------------------------------

def _three_box_canvas() -> Canvas:
    """A small canvas: a red box and a cyan-on-blue box side by side."""
    c = Canvas()
    a = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.LIGHT, text="hi")
    a.fg = "red"
    a.id = "a"
    c.add_shape(a)
    b = BoxShape(Rect(5, 0, 4, 3), border=BorderStyle.HEAVY)
    b.fg = "bright_cyan"
    b.bg = "blue"
    b.id = "b"
    c.add_shape(b)
    return c


# --- to_css ---------------------------------------------------------------

@pytest.mark.parametrize("rich,css", list(_RICH_TO_CSS.items()))
def test_to_css_known_names(rich: str, css: str) -> None:
    assert to_css(rich) == css


def test_to_css_none_passes_through() -> None:
    assert to_css(None) is None


def test_to_css_unknown_passes_through() -> None:
    """Forward-compat: hex / unknown values aren't translated, just emitted."""
    assert to_css("#ff8800") == "#ff8800"
    assert to_css("rebeccapurple") == "rebeccapurple"


# --- text export ---------------------------------------------------------

def test_text_export_basic() -> None:
    c = _three_box_canvas()
    text = c.export_to_text(charset=CharSet.UNICODE)
    # A 9-column-wide bounding box (cols 0..8) with 3 rows.
    assert text.splitlines() == [
        "┌──┐ ┏━━┓",
        "│hi│ ┃  ┃",
        "└──┘ ┗━━┛",
    ]


def test_text_export_strips_color() -> None:
    """Text export must not embed any color escape codes."""
    c = _three_box_canvas()
    text = c.export_to_text()
    # No ANSI escapes, no <span>, no fill="…".
    assert "\x1b[" not in text
    assert "<span" not in text


def test_text_export_empty_canvas(empty_canvas: Canvas) -> None:
    assert empty_canvas.export_to_text() == ""


def test_text_export_selected_only() -> None:
    """Passing a subset of shapes restricts the output."""
    c = _three_box_canvas()
    only_a = [s for s in c.shapes if s.id == "a"]
    text = c.export_to_text(only_a)
    # Should be just the first box; no "hi" -side neighbor.
    assert "┃" not in text
    assert "hi" in text


# --- HTML export ---------------------------------------------------------

def test_html_export_runs_combine_adjacent_same_style() -> None:
    """Ten adjacent solid-fill cells of one color produce one span, not ten."""
    c = Canvas()
    box = BoxShape(Rect(0, 0, 10, 1), border=BorderStyle.NONE,
                   fill=FillStyle.FULL)
    box.fg = "red"
    box.id = "b0"
    c.add_shape(box)
    html = export_html(c)
    span_count = html.count("<span")
    assert span_count == 1, f"expected 1 span, got {span_count}\n{html}"


def test_html_export_run_grouping_breaks_on_color_change() -> None:
    """Two side-by-side fills of different color → exactly two spans."""
    c = Canvas()
    a = BoxShape(Rect(0, 0, 5, 1), border=BorderStyle.NONE,
                 fill=FillStyle.FULL)
    a.fg = "red"; a.id = "a"
    b = BoxShape(Rect(5, 0, 5, 1), border=BorderStyle.NONE,
                 fill=FillStyle.FULL)
    b.fg = "green"; b.id = "b"
    c.add_shape(a)
    c.add_shape(b)
    html = export_html(c)
    assert html.count("<span") == 2


def test_html_export_uses_css_color_names() -> None:
    """fg='bright_red' must come out as the cipher's CSS name (tomato)."""
    c = Canvas()
    box = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.LIGHT)
    box.fg = "bright_red"
    box.id = "b0"
    c.add_shape(box)
    html = export_html(c)
    assert "color:tomato" in html
    # The raw rich name must NOT leak through.
    assert "bright_red" not in html


def test_html_export_complete_document() -> None:
    """Output must be a self-contained HTML document, not a fragment."""
    c = _three_box_canvas()
    html = export_html(c)
    assert html.startswith("<!doctype html>")
    assert "<style>" in html
    assert "<pre" in html
    assert "</pre>" in html


def test_html_export_empty_canvas(empty_canvas: Canvas) -> None:
    """Empty canvas → empty output, so the caller's `if out:` guard works."""
    assert export_html(empty_canvas) == ""


def test_html_export_escapes_special_chars() -> None:
    """``<``, ``>``, ``&`` in shape text must be HTML-escaped."""
    c = Canvas()
    box = BoxShape(Rect(0, 0, 12, 3), border=BorderStyle.LIGHT,
                   text="<a&b>")
    box.id = "b0"
    c.add_shape(box)
    html = export_html(c)
    assert "&lt;a&amp;b&gt;" in html
    assert "<a&b>" not in html


# --- SVG export ----------------------------------------------------------

def test_svg_export_is_pure_svg_no_foreign_object() -> None:
    """Regression guard: SVG must not embed HTML via <foreignObject>."""
    c = _three_box_canvas()
    svg = export_svg(c)
    assert "<foreignObject" not in svg
    assert "<svg " in svg
    assert svg.rstrip().endswith("</svg>")


def test_svg_export_has_viewbox_and_dimensions() -> None:
    c = _three_box_canvas()
    svg = export_svg(c)
    # 9 cols × 3 rows ⇒ width = 9 * 8.4 = 75.6; height = 3 * 14 = 42.
    assert 'viewBox="0 0 75.6 42"' in svg
    assert 'width="75.6"' in svg
    assert 'height="42"' in svg


def test_svg_export_emits_text_per_glyph() -> None:
    """Each non-blank cell must get its own <text> with textLength."""
    c = _three_box_canvas()
    svg = export_svg(c)
    text_count = svg.count("<text ")
    # Each <text> carries the per-cell tile guarantee.
    assert text_count > 0
    # Spot-check the per-cell stretching attributes.
    sample = re.search(r'<text [^>]*>', svg)
    assert sample is not None
    attrs = sample.group(0)
    assert 'textLength="' in attrs
    assert 'lengthAdjust="spacingAndGlyphs"' in attrs


def test_svg_export_emits_background_rects() -> None:
    """A bg-styled run produces a <rect> ahead of the <text> in the same row."""
    c = Canvas()
    box = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.LIGHT)
    box.fg = "red"
    box.bg = "yellow"
    box.id = "b0"
    c.add_shape(box)
    svg = export_svg(c)
    assert '<rect ' in svg
    assert 'fill="yellow"' in svg


def test_svg_export_uses_css_color_names() -> None:
    c = Canvas()
    box = BoxShape(Rect(0, 0, 4, 3), border=BorderStyle.LIGHT)
    box.fg = "bright_red"
    box.id = "b0"
    c.add_shape(box)
    svg = export_svg(c)
    assert 'fill="tomato"' in svg
    assert "bright_red" not in svg


def test_svg_export_empty_canvas(empty_canvas: Canvas) -> None:
    assert export_svg(empty_canvas) == ""


def test_svg_export_escapes_special_chars() -> None:
    c = Canvas()
    box = BoxShape(Rect(0, 0, 12, 3), border=BorderStyle.LIGHT,
                   text="<a&b>")
    box.id = "b0"
    c.add_shape(box)
    svg = export_svg(c)
    # The escaped sequence must appear and the raw form must not.
    assert "&lt;" in svg
    assert "&amp;" in svg
    # `<a&b>` isn't valid SVG; if it shows up unescaped, parsing breaks.
    raw_text_chars = re.findall(r'>[^<]*<', svg)  # text between tags
    for chunk in raw_text_chars:
        assert "<a&b>" not in chunk


# --- Presenterm export ---------------------------------------------------

def test_presenterm_export_empty_canvas(empty_canvas: Canvas) -> None:
    assert export_presenterm(empty_canvas) == ""


def test_presenterm_export_lines_end_with_backslash() -> None:
    """All lines except the last must end with backslash."""
    c = _three_box_canvas()
    out = export_presenterm(c)
    lines = out.split("\n")
    # Last line is empty (trailing newline), second-to-last has no backslash
    for line in lines[:-2]:
        assert line.endswith("\\"), f"Line missing backslash: {line!r}"
    assert not lines[-2].endswith("\\")


def test_presenterm_export_leading_whitespace_wrapped() -> None:
    """Leading spaces must be wrapped in an unstyled <span>."""
    c = Canvas()
    # Two boxes: one at col 0, one at col 5. The second box's first row
    # starts at col 5, so rows where only the right box has content will
    # have leading whitespace from the bounding box left (col 0).
    a = BoxShape(Rect(0, 3, 3, 1), border=BorderStyle.NONE, fill=FillStyle.FULL)
    a.fg = "green"; a.id = "a"
    b = BoxShape(Rect(5, 0, 4, 1), border=BorderStyle.NONE, fill=FillStyle.FULL)
    b.fg = "red"; b.id = "b"
    c.add_shape(a)
    c.add_shape(b)
    out = export_presenterm(c)
    first_line = out.split("\n")[0].rstrip("\\")
    # 5 spaces of leading whitespace wrapped in unstyled span
    assert first_line.startswith("<span>     </span>")


def test_presenterm_export_uses_css_color_names() -> None:
    """Colors must be mapped to presenterm ANSI names."""
    c = Canvas()
    box = BoxShape(Rect(0, 0, 4, 1), border=BorderStyle.NONE, fill=FillStyle.FULL)
    box.fg = "bright_red"
    box.id = "b0"
    c.add_shape(box)
    out = export_presenterm(c)
    assert 'color: red' in out
    assert "bright_red" not in out


def test_presenterm_export_background_color() -> None:
    """bg must produce background-color in the style."""
    c = Canvas()
    box = BoxShape(Rect(0, 0, 4, 1), border=BorderStyle.NONE, fill=FillStyle.FULL)
    box.fg = "red"
    box.bg = "blue"
    box.id = "b0"
    c.add_shape(box)
    out = export_presenterm(c)
    assert 'color: dark_red; background-color: dark_blue' in out


def test_presenterm_export_escapes_special_chars() -> None:
    """<, >, & in shape text must be HTML-escaped."""
    c = Canvas()
    box = BoxShape(Rect(0, 0, 12, 3), border=BorderStyle.LIGHT, text="<a&b>")
    box.id = "b0"
    c.add_shape(box)
    out = export_presenterm(c)
    assert "&lt;a&amp;b&gt;" in out
    assert "<a&b>" not in out


def test_presenterm_export_unstyled_between_spans() -> None:
    """Unstyled content between styled runs is bare text (not wrapped)."""
    c = Canvas()
    a = BoxShape(Rect(0, 0, 3, 1), border=BorderStyle.NONE, fill=FillStyle.FULL)
    a.fg = "red"; a.id = "a"
    b = BoxShape(Rect(5, 0, 3, 1), border=BorderStyle.NONE, fill=FillStyle.FULL)
    b.fg = "green"; b.id = "b"
    c.add_shape(a)
    c.add_shape(b)
    out = export_presenterm(c)
    # The gap between the two boxes should be bare spaces, not in a span
    assert '</span>  <span' in out


def test_presenterm_export_trailing_newline() -> None:
    """Output must end with a newline."""
    c = _three_box_canvas()
    out = export_presenterm(c)
    assert out.endswith("\n")
