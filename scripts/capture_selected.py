"""Render a selected/hovered rectangle to plain text for visual review.

Mounts PalatermApp, programmatically adds a rectangle to the canvas,
selects it, and dumps the rendered canvas region cell-by-cell with
foreground+background style indicators per cell.

Run: ``.venv/bin/python scripts/capture_selected.py``
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from palaterm.app import PalatermApp  # noqa: E402
from palaterm.geometry import Rect  # noqa: E402
from palaterm.models.enums import BorderStyle, FillStyle  # noqa: E402
from palaterm.models.rectangle import RectangleShape  # noqa: E402
from palaterm.tools import SelectTool  # noqa: E402


async def main() -> None:
    app = PalatermApp()
    async with app.run_test(size=(40, 20)) as pilot:
        await pilot.pause()
        cw = app.canvas_widget
        rect = RectangleShape(Rect(5, 3, 8, 5), BorderStyle.LIGHT, FillStyle.NONE)
        cw.canvas.shapes.append(rect)
        # Select it
        cw.tool = SelectTool()
        cw.tool.selected = [rect]
        cw.refresh()
        await pilot.pause()
        await pilot.pause()

        # Sample cells from the canvas widget area
        compositor = app.screen._compositor  # type: ignore[attr-defined]
        # canvas widget begins at x=16 (sidebar=16) y=0
        for y in range(15):
            row_chars = []
            row_styles = []
            try:
                strips = compositor.render_strips()
                strip = strips[y] if y < len(strips) else None
            except Exception:
                strip = None
            if strip is None:
                continue
            for seg in strip._segments:
                if seg.text:
                    style_str = ""
                    if seg.style:
                        bg = seg.style.bgcolor
                        fg = seg.style.color
                        style_str = f"[fg={fg} bg={bg}]"
                    row_chars.append(seg.text)
                    row_styles.append(style_str)
            print(
                f"y={y}: {''.join(f'{c!r}{s}' for c, s in zip(row_chars, row_styles))}"
            )


if __name__ == "__main__":
    asyncio.run(main())
