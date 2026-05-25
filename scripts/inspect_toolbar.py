"""Headless toolbar layout inspector.

Mounts PalatermApp via Textual's ``run_test`` harness, force-shows every
sidebar panel, and prints the resolved geometry (region, width, height) of
every ``Button`` plus the ``Horizontal`` rows that wrap them.

Useful for catching layout bugs that only show up after compose — e.g. a
``Button`` overflowing its row because Textual's default ``min-width: 16``
exceeds the available cell width, which silently hides later siblings off
the visible area. Run this whenever toolbar CSS changes to verify that
button widths sum to the sidebar width and heights stay at 1.

Run: ``.venv/bin/python scripts/inspect_toolbar.py``
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from palaterm.app import PalatermApp  # noqa: E402
from textual.widgets import Button  # noqa: E402


async def main() -> None:
    app = PalatermApp()
    async with app.run_test(size=(120, 40)) as pilot:
        # Force every panel visible by switching tools / forcing classes.
        await pilot.pause()
        # Show ALL panels, regardless of state, so we can inspect them all.
        from palaterm.widgets.panels import (
            BorderStylePanel,
            LayerPanel,
            LineEndingsPanel,
            LineStylePanel,
            SelectModePanel,
            ShapeAlignPanel,
            TextAlignPanel,
        )

        panel_classes = [
            SelectModePanel,
            BorderStylePanel,
            LineStylePanel,
            LineEndingsPanel,
            TextAlignPanel,
            ShapeAlignPanel,
            LayerPanel,
        ]
        for cls in panel_classes:
            try:
                p = app.query_one(cls)
                p.add_class("visible")
            except Exception as e:
                print(f"!! could not query {cls.__name__}: {e}")
        await pilot.pause()
        await pilot.pause()

        # Status bar
        from palaterm.widgets import StatusBar

        sb = app.query_one(StatusBar)
        print(f"=== StatusBar region: {sb.region} ===")
        for btn in sb.query(Button):
            print(
                f"   StatusBar Button id={btn.id!r:24} region={btn.region} label={btn.label!r}"  # noqa: E501
            )
        print()

        from textual.containers import Horizontal

        for h in app.query(Horizontal):
            print(
                f"Horizontal id={h.id} parent={type(h.parent).__name__} region={h.region} styles.width={h.styles.width}"  # noqa: E501
            )
        print()

        # Each panel
        for cls in [
            __import__("palaterm.widgets.panels", fromlist=["ToolPicker"]).ToolPicker,
            *panel_classes,
        ]:
            try:
                panel = app.query_one(cls)
            except Exception as e:
                print(f"!! could not query {cls.__name__}: {e}")
                continue
            display = panel.styles.display
            visible = "visible" in panel.classes
            print(
                f"=== {cls.__name__} region={panel.region} display={display} visible={visible} ==="  # noqa: E501
            )
            for btn in panel.query(Button):
                print(
                    f"   Button id={btn.id!r:30} region={btn.region} label={btn.label!r}"  # noqa: E501
                )
            print()


if __name__ == "__main__":
    asyncio.run(main())
