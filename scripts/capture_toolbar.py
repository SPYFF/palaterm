"""Render the toolbar to plain text for visual review.

Mounts PalatermApp, force-shows every panel, then samples the composited
screen cell-by-cell and prints the visible characters. The first 20
columns (sidebar + a bit of canvas) are shown so you can eyeball the
sidebar layout without opening a terminal.

Run: ``.venv/bin/python scripts/capture_toolbar.py``
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from palaterm.app import PalatermApp  # noqa: E402


async def main() -> None:
    app = PalatermApp()
    async with app.run_test(size=(40, 42)) as pilot:
        await pilot.pause()
        from palaterm.widgets.panels import (
            BorderStylePanel,
            LayerPanel,
            LineEndingsPanel,
            LineStylePanel,
            SelectModePanel,
            ShapeAlignPanel,
            TextAlignPanel,
        )

        for cls in [
            SelectModePanel,
            BorderStylePanel,
            LineStylePanel,
            LineEndingsPanel,
            TextAlignPanel,
            ShapeAlignPanel,
            LayerPanel,
        ]:
            app.query_one(cls).add_class("visible")
        await pilot.pause()
        await pilot.pause()

        # Use compositor to read each cell.
        compositor = app.screen._compositor  # type: ignore[attr-defined]
        cols = 20  # sidebar (16) + a little gutter
        rows = app.size.height
        print("┌" + "─" * cols + "┐")
        for y in range(rows):
            line_chars = []
            try:
                strips = compositor.render_strips()
                strip = strips[y] if y < len(strips) else None
            except Exception:
                strip = None
            if strip is None:
                line_chars = [" "] * cols
            else:
                text = strip.text
                line_chars = list(text[:cols].ljust(cols))
            print("│" + "".join(line_chars) + "│")
        print("└" + "─" * cols + "┘")


if __name__ == "__main__":
    asyncio.run(main())
