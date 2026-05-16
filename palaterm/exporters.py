"""SVG and HTML exporters for palaterm canvases.

Both formats consume the per-cell ``(char, fg, bg)`` grid produced by
:meth:`palaterm.canvas.Canvas.render_styled` and emit a styled
single-document string ready to copy to the clipboard.

Color names: shapes carry Rich-style names (``"red"``, ``"bright_cyan"``).
:func:`to_css` translates them to CSS color names — the standard 8 pass
through verbatim, the 8 ``bright_*`` variants get a hand-rolled
CSS-name approximation. Unknown values pass through unchanged so a
future hex/RGB color makes it to the output unchanged.
"""

from __future__ import annotations

from typing import Iterator

from .canvas import Canvas
from .geometry import Rect
from .models import CharSet, Shape


_RICH_TO_CSS: dict[str, str] = {
    # Standard 8 — CSS recognizes these names.
    "black":   "black",
    "red":     "red",
    "green":   "green",
    "yellow":  "yellow",
    "blue":    "blue",
    "magenta": "magenta",
    "cyan":    "cyan",
    "white":   "white",
    # Bright 8 — CSS-name approximations. CSS has no `bright_*` palette,
    # so each variant maps to the visually-closest CSS named color.
    "bright_black":   "gray",
    "bright_red":     "tomato",
    "bright_green":   "limegreen",
    "bright_yellow":  "gold",
    "bright_blue":    "royalblue",
    "bright_magenta": "violet",
    "bright_cyan":    "turquoise",
    "bright_white":   "white",
}


_RICH_TO_PRESENTERM: dict[str, str] = {
    "black":          "black",
    "red":            "dark_red",
    "green":          "dark_green",
    "yellow":         "dark_yellow",
    "blue":           "dark_blue",
    "magenta":        "dark_magenta",
    "cyan":           "dark_cyan",
    "white":          "white",
    "bright_black":   "grey",
    "bright_red":     "red",
    "bright_green":   "green",
    "bright_yellow":  "yellow",
    "bright_blue":    "blue",
    "bright_magenta": "magenta",
    "bright_cyan":    "cyan",
    "bright_white":   "white",
}


def to_presenterm(rich_name: str | None) -> str | None:
    """Translate a Rich color name to a presenterm color name, or pass through."""
    if rich_name is None:
        return None
    return _RICH_TO_PRESENTERM.get(rich_name, rich_name)


def to_css(rich_name: str | None) -> str | None:
    """Translate a Rich color name to a CSS color, or pass through unchanged."""
    if rich_name is None:
        return None
    return _RICH_TO_CSS.get(rich_name, rich_name)


def _escape(text: str) -> str:
    """Escape XML/HTML special characters."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def _runs_for_row(
    cells: dict[tuple[int, int], tuple[str, str | None, str | None]],
    row: int,
    left: int,
    right: int,
) -> Iterator[tuple[int, str, str | None, str | None]]:
    """Yield ``(start_col, text, fg, bg)`` runs for one row.

    A run is a maximal sequence of adjacent cells sharing the same
    ``(fg, bg)`` style. Empty cells (no shape paints them) become a
    single-space run with no style and are emitted so absolute
    columns line up; HTML/SVG callers may choose to elide them.
    """
    col = left
    while col <= right:
        ch, fg, bg = cells.get((col, row), (" ", None, None))
        run_text = [ch]
        run_start = col
        col += 1
        while col <= right:
            nch, nfg, nbg = cells.get((col, row), (" ", None, None))
            if (nfg, nbg) != (fg, bg):
                break
            run_text.append(nch)
            col += 1
        yield run_start, "".join(run_text), fg, bg


def _bounded_grid(
    canvas: Canvas, charset: CharSet, shapes: list[Shape] | None,
) -> tuple[Rect, dict[tuple[int, int], tuple[str, str | None, str | None]]]:
    bound, cells = canvas.render_styled(shapes, charset)
    return bound, cells


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------

# Pixel sizes for the SVG cell grid. To make box-drawing characters tile
# edge-to-edge in pure SVG (no <foreignObject>), the renderer needs two
# guarantees:
#
#   * Horizontal: every character is rendered with its own ``<text>``
#     element carrying ``textLength="<cell_w>" lengthAdjust="spacingAndGlyphs"``.
#     Per-cell (not per-run) stretching forces each glyph to exactly fill
#     ``_SVG_CELL_W`` regardless of the font's natural advance — this is
#     what closes the gaps between, e.g., two consecutive ``─``.
#   * Vertical: cell height equals font-size (1.0em line-height) and the
#     baseline is set with ``dominant-baseline="text-before-edge"`` so the
#     glyph occupies the row from y=0 down. Otherwise vertical bars like
#     ``│`` don't span the full cell and leave gaps between rows.
_SVG_FONT_SIZE = 14
_SVG_CELL_W = 8.4    # ~0.6em — matches "0" advance in typical monospace
_SVG_CELL_H = 14     # 1.0em — rows abut so vertical glyphs connect


def _styled_pre_body(
    cells: dict[tuple[int, int], tuple[str, str | None, str | None]],
    bound: Rect,
) -> str:
    """Build the inner content of a styled ``<pre>`` block.

    Each row becomes a single line of bare text + ``<span>`` runs.
    Adjacent cells sharing the same ``(fg, bg)`` collapse to one span.
    """
    line_strs: list[str] = []
    for row in range(bound.top, bound.bottom + 1):
        chunks: list[str] = []
        # The run's start column is implicit in concatenation order — only
        # text/fg/bg matter for sequential <pre> output.
        for _, run_text, fg, bg in _runs_for_row(
            cells, row, bound.left, bound.right
        ):
            escaped = _escape(run_text)
            css_fg = to_css(fg)
            css_bg = to_css(bg)
            if css_fg is None and css_bg is None:
                chunks.append(escaped)
            else:
                style_parts = []
                if css_fg is not None:
                    style_parts.append(f"color:{css_fg}")
                if css_bg is not None:
                    style_parts.append(f"background:{css_bg}")
                chunks.append(
                    f'<span style="{";".join(style_parts)}">{escaped}</span>'
                )
        line_strs.append("".join(chunks).rstrip())
    return "\n".join(line_strs)


def export_svg(canvas: Canvas, charset: CharSet = CharSet.UNICODE,
               shapes: list[Shape] | None = None) -> str:
    """Render the canvas (or selected ``shapes``) to a pure SVG document.

    Each character is emitted as its own ``<text>`` element with
    ``textLength`` and ``lengthAdjust="spacingAndGlyphs"`` set to the
    cell width, which forces every glyph to exactly fill its cell so
    box-drawing characters tile without gaps. Backgrounds are emitted
    as run-grouped ``<rect>`` elements painted before the text.

    Output is conformant SVG 1.1 — no ``<foreignObject>``, no embedded
    HTML — so it renders consistently across browsers, Inkscape,
    Illustrator, ImageMagick, and other SVG tooling.

    Returns an empty string when there is nothing to render.
    """
    bound, cells = _bounded_grid(canvas, charset, shapes)
    if not cells:
        return ""

    width_px = bound.width * _SVG_CELL_W
    height_px = bound.height * _SVG_CELL_H

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width_px:g} {height_px:g}" '
        f'width="{width_px:g}" height="{height_px:g}" '
        f'font-family="monospace" font-size="{_SVG_FONT_SIZE}px">',
    ]

    # Pass 1 — backgrounds. Run-grouped because adjacent solid fills with
    # the same color trivially merge into one rect, and rect tiling is
    # gap-free in any conformant renderer.
    for row in range(bound.top, bound.bottom + 1):
        rel_row = row - bound.top
        for start_col, run_text, _fg, bg in _runs_for_row(
            cells, row, bound.left, bound.right
        ):
            if bg is None:
                continue
            rel_col = start_col - bound.left
            parts.append(
                f'<rect x="{rel_col * _SVG_CELL_W:g}" '
                f'y="{rel_row * _SVG_CELL_H:g}" '
                f'width="{len(run_text) * _SVG_CELL_W:g}" '
                f'height="{_SVG_CELL_H:g}" fill="{to_css(bg)}"/>'
            )

    # Pass 2 — foreground glyphs. *Per-cell* (not per-run) emission with
    # textLength forces each character to exactly fill its cell width.
    # Per-run emission would let the font's natural advance leave
    # sub-pixel gaps between adjacent box-drawing chars; per-cell
    # stretching defeats that.
    for (col, row), (ch, fg, _bg) in cells.items():
        if ch == " ":
            continue
        rel_col = col - bound.left
        rel_row = row - bound.top
        fill_attr = f' fill="{to_css(fg)}"' if fg else ""
        parts.append(
            f'<text x="{rel_col * _SVG_CELL_W:g}" '
            f'y="{rel_row * _SVG_CELL_H:g}" '
            f'textLength="{_SVG_CELL_W:g}" lengthAdjust="spacingAndGlyphs" '
            f'dominant-baseline="text-before-edge"'
            f'{fill_attr}>{_escape(ch)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """<!doctype html>
<meta charset="utf-8">
<title>palaterm export</title>
<style>
  body {{ margin: 0; }}
  pre.palaterm {{ margin: 0; padding: 1ch; font-family: monospace; line-height: 1.2; }}
  pre.palaterm span {{ white-space: pre; }}
</style>
<pre class="palaterm">{body}</pre>
"""


def export_html(canvas: Canvas, charset: CharSet = CharSet.UNICODE,
                shapes: list[Shape] | None = None) -> str:
    """Render the canvas (or selected ``shapes``) to a complete HTML document.

    Returns an empty string when there is nothing to render.
    """
    bound, cells = _bounded_grid(canvas, charset, shapes)
    if not cells:
        return ""
    return _HTML_TEMPLATE.format(body=_styled_pre_body(cells, bound))


# ---------------------------------------------------------------------------
# Presenterm
# ---------------------------------------------------------------------------


def export_presenterm(canvas: Canvas, charset: CharSet = CharSet.UNICODE,
                      shapes: list[Shape] | None = None) -> str:
    """Render the canvas (or selected ``shapes``) to presenterm-compatible markdown.

    Output uses HTML ``<span>`` tags with inline ``color`` / ``background-color``
    CSS properties. Leading whitespace on each line is wrapped in an unstyled
    ``<span>`` to prevent CommonMark from trimming it. Lines are joined with
    backslash hard-breaks.

    Returns an empty string when there is nothing to render.
    """
    bound, cells = _bounded_grid(canvas, charset, shapes)
    if not cells:
        return ""

    line_strs: list[str] = []
    for row in range(bound.top, bound.bottom + 1):
        chunks: list[str] = []
        leading = True
        for _, run_text, fg, bg in _runs_for_row(cells, row, bound.left, bound.right):
            escaped = _escape(run_text)
            pt_fg = to_presenterm(fg)
            pt_bg = to_presenterm(bg)
            if leading and pt_fg is None and pt_bg is None and run_text.strip() == "":
                # Wrap leading whitespace in unstyled span
                chunks.append(f"<span>{escaped}</span>")
            elif pt_fg is None and pt_bg is None:
                leading = False
                chunks.append(escaped)
            else:
                leading = False
                style_parts = []
                if pt_fg is not None:
                    style_parts.append(f"color: {pt_fg}")
                if pt_bg is not None:
                    style_parts.append(f"background-color: {pt_bg}")
                chunks.append(
                    f'<span style="{"; ".join(style_parts)}">{escaped}</span>'
                )
        line_strs.append("".join(chunks))

    return "\\\n".join(line_strs) + "\n"
