# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Palaterm is a Textual-based TUI drawing app: rectangles, text boxes, and lines composited from Unicode box-drawing (and braille sub-pixel) characters on an infinite scrolling canvas. Inspired by MonoSketch. Python 3.11+, managed with `uv`.

## Commands

**Before running anything in this repo, ensure the dev environment is initialized.** Run `uv sync` first if `.venv/` is missing or `uv.lock` has changed. Every command that touches Python — the app, tests, type checking, scripts — must go through `uv run …`. Never invoke `python`, `pytest`, `pyright`, or `palaterm` from the host shell directly; they will resolve to the system interpreter (or fail outright) and miss the project's pinned `textual`, `rich`, `pyright`, `pytest`, etc. Treat "ran it outside the venv" as a bug, not a fallback.

```bash
uv sync                                # install deps (incl. dev group) — run first
uv run palaterm                        # launch the app
uv run palaterm path/to/file.palaterm  # open a file at startup

uv run pytest                          # run all tests (asyncio_mode=auto)
uv run pytest tests/test_models.py::test_name  # single test
uv run pytest --cov                    # coverage (branch, src=palaterm/)

uv run pyright                         # type check

uv run python scripts/bench_render.py     # render benchmark on the fixed-50 canvas
uv run python scripts/bench_serialize.py  # serialization benchmark
```

`uv run palaterm` requires a real TTY — run it in a terminal, not piped. It probes the terminal via `OSC 11` to auto-pick a light/dark theme.

### Type checking with pyright

Always run pyright via `uv run pyright`. The editor/IDE pyright integration (which feeds the `<new-diagnostics>` system reminders during a Claude Code session) runs *outside* the `uv`-managed venv and reports spurious `Import "textual.…" could not be resolved` errors for every panel/widget file. **Ignore those.** They do not reflect real type problems — the code imports fine.

To validate correctness, run `uv run pyright` once at the end of a change and compare the error count against the `main` baseline (currently 21 pre-existing errors). New errors introduced by your change will be visible at the bottom of the output. The baseline errors live in `app.py`, `controllers.py`, `serialization.py`, `widgets/canvas.py`, `scripts/`, and `tests/test_commands.py` — leave them alone unless the task is specifically to fix them.

There is no `pyrightconfig.json`. Pyright picks up the `.venv` (created by `uv sync`) automatically when invoked through `uv run`.

## Architecture

The app is a single Textual `App` with one big custom `CanvasWidget`. Mouse/keyboard events flow through controllers that own state, mutate the `Canvas` model via undoable `Command`s, and trigger a re-render via `FrameRenderer`.

### Layers (read in this order to onboard)

1. **`models/`** — pure data: `Shape` base + `BoxShape` (rectangle/text — same class) and `LineShape`. Enums for border/line/ending/align styles live in `models/enums.py`. `charset.py` provides Unicode→ASCII fallback and braille sub-pixel helpers. `models/__init__.py` aliases `RectangleShape` and `TextShape` to `BoxShape` (transitional — they are the same type).
2. **`geometry.py`** — `Point` and `Rect` primitives used everywhere.
3. **`canvas.py`** — `Canvas` owns `shapes: list[Shape]` (z-order = list order; last = topmost). Hit-testing, region queries, layer reorder, and `render_region(viewport, charset)` which composites cells. Holds a `ConnectorManager` (`connectors.py`) so lines can anchor to box edges and follow them when boxes move.
4. **`crossings.py`** — when two line segments cross while compositing, this picks the right glyph (T/cross/etc.) based on adjacent border styles.
5. **`commands.py`** — every mutation that should be undoable is a `Command` (`AddShape`, `AddShapes`, `RemoveShapes`, `MoveShapes`, `TransformShapes`, …). `CommandHistory` tracks undo/redo and a `_save_point` for dirty-tracking. Don't mutate shapes directly from app/tool code — go through a command pushed via `history.execute(...)` or `history.push(...)`.
6. **`tools/`** — `DrawTool` subclasses (`RectangleTool`, `TextTool`, `LineTool`) and `SelectTool`. Tools translate mouse events into provisional shapes/transforms; the `CanvasWidget` commits them as commands on mouse-up. Resize/move handles are defined in `tools/__init__.py` (`Handle`, `get_handles`, `handle_at`).
7. **`controllers.py`** — `ToolController` holds the persistent style state (current border style, line style, line endings) and constructs tools. `PanelController` is the single source of truth for which side panels are visible/active given the current tool and selection.
8. **`rendering.py`** — `FrameRenderer` caches per-frame compositing data and emits Textual `Strip`s line-by-line. It merges foreground-only highlight styles with the canvas widget's resolved base style so themed backgrounds don't bleed. Call `invalidate()` on any change.
9. **`widgets/`** — `CanvasWidget` (the big one: viewport, scroll, mouse routing, drag state, selection rectangle), plus `panels/` (toolbar, border/line/alignment/layer/export panels), `modals.py`, `status_bar.py`.
10. **`app.py`** — `PalatermApp`: keybindings, panel/tool wiring, file open/save, export. The Textual `CSS` lives inline here.
11. **`exporters.py`** — `export_html`, `export_svg`, `export_presenterm`. `serialization.py` is the JSON `.palaterm` format (load/save).

### Conventions worth knowing

- **Coords are character cells.** `col` = x, `row` = y. Lines additionally use braille sub-pixel positions inside `LineShape` for the "straight" style.
- **Z-order = list order.** `bring_to_front` / `send_to_back` reorder `canvas.shapes` in place.
- **`BoxShape` is both rectangles and text boxes** — they only differ by whether `text` is set and how the border/text alignment fields are used.
- **Coverage intentionally excludes UI surfaces** (`app.py`, `widgets/*`, `tools/*`, `controllers.py`) — those are exercised by manual UI testing. Keep core logic (`canvas`, `commands`, `models`, `crossings`, `connectors`, `serialization`, `exporters`, `rendering`) covered by `tests/`.
- **`tests/fixtures.py`** builds a deterministic 50-shape canvas (`build_fixed_canvas`) shared between tests and benchmarks — use the `fixed_canvas` / `empty_canvas` fixtures from `conftest.py` rather than constructing ad-hoc canvases.

## Keybindings

See README.md — the source of truth is `BINDINGS` in `palaterm/app.py`.
