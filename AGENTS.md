# AGENTS.md

This file provides guidance to AI agents working with code in this repository.

## What this is

Palaterm is a Textual-based TUI drawing app: rectangles, text boxes, and lines composited from Unicode box-drawing (and braille sub-pixel) characters on an infinite scrolling canvas. Inspired by MonoSketch. Python 3.11+, managed with `uv`.

## Commands

**Before running anything in this repo, ensure the dev environment is initialized.** Run `uv sync` first if `.venv/` is missing or `uv.lock` has changed. Every command that touches Python — the app, tests, linting, scripts — must go through `uv run …`. Never invoke `python`, `pytest`, `pyright`, `ruff`, or `palaterm` from the host shell directly; they will resolve to the system interpreter (or fail outright) and miss the project's pinned dependencies. Treat "ran it outside the venv" as a bug, not a fallback.

```bash
uv sync                                # install deps (incl. dev group) — run first
uv run palaterm                        # launch the app
uv run palaterm path/to/file.palaterm  # open a file at startup

uv run pytest                          # run all tests (asyncio_mode=auto)
uv run pytest tests/test_models.py::test_name  # single test
uv run pytest --cov                    # coverage (branch, src=palaterm/)

uv run ruff check                      # lint (errors, style, imports)
uv run ruff format --check             # check formatting without modifying
uv run ruff format                     # auto-format in place

uv run python scripts/bench_render.py           # render benchmark on the fixed-50 canvas
uv run python scripts/bench_render.py --save-baseline  # record a regression baseline
uv run python scripts/bench_render.py --check   # compare vs baseline, exit 1 on regression
uv run python scripts/bench_serialize.py     # serialization benchmark
uv run python scripts/bench_serialize.py --save-baseline  # record (committed) baseline
uv run python scripts/bench_serialize.py --check  # exit 1 if structural metrics regress
```

`uv run palaterm` requires a real TTY — run it in a terminal, not piped. It probes the terminal via `OSC 11` to auto-pick a light/dark theme.

### Linting with ruff

Ruff is the project linter. Run `uv run ruff check` to find errors (pyflakes `F`), style issues (`E`), and import ordering (`I`). Run `uv run ruff format --check` to verify formatting. Fix lint issues with `uv run ruff check --fix`; auto-format with `uv run ruff format`. Configuration lives in `[tool.ruff]` inside `pyproject.toml`.

### LSP (pyright)

Pyright serves as the LSP **only** — it provides completions, hover, go-to-definition, and rename. **Diagnostics are disabled** via `pyrightconfig.json` (`"typeCheckingMode": "off"`) and the LSP initialization options in `.kiro/settings/lsp.json`. Do not rely on pyright for error checking; use `uv run ruff check` instead.

The LSP **must** be initialized inside the `uv` venv:

```
uv run pyright-langserver --stdio
```

This is already configured in `.kiro/settings/lsp.json`. If you are an agent with LSP support, ensure you launch pyright via `uv run` — never the system-installed pyright. The venv provides the correct `textual`, `rich`, and other dependencies for import resolution.

## Architecture

The app is a single Textual `App` with one big custom `CanvasWidget`. Mouse/keyboard events flow through controllers that own state, mutate the `Canvas` model via undoable `Command`s, and trigger a re-render via `FrameRenderer`.

### Layers (read in this order to onboard)

1. **`models/`** — pure data: `Shape` base + `BoxShape` (rectangle/text — same class) and `LineShape`. Enums for border/line/ending/align styles live in `models/enums.py`. `charset.py` provides Unicode→ASCII fallback and braille sub-pixel helpers. `models/__init__.py` aliases `RectangleShape` and `TextShape` to `BoxShape` (transitional — they are the same type).
2. **`geometry.py`** — `Point` and `Rect` primitives used everywhere.
3. **`canvas.py`** — `Canvas` owns `shapes: list[Shape]` (z-order = list order; last = topmost). Hit-testing, region queries, layer reorder, and `render_region(viewport, charset)` which composites cells. Holds a `ConnectorManager` (`connectors.py`) so lines can anchor to box edges and follow them when boxes move.
4. **`crossings.py`** — when two line segments cross while compositing, this picks the right glyph (T/cross/etc.) based on adjacent border styles.
5. **`commands.py`** — every mutation that should be undoable is a `Command` (`AddShape`, `AddShapes`, `RemoveShapes`, `MoveShapes`, `TransformShapes`, `MoveLineEdge`, …). `CommandHistory` tracks undo/redo and a `_save_point` for dirty-tracking. Don't mutate shapes directly from app/tool code — go through a command pushed via `history.execute(...)` or `history.push(...)`. For Panel-driven attribute changes (border/fill/line-style/endings/color), funnel through `style_application.apply_attribute_change(history, targets, attr, new_value)` instead of hand-rolling the snapshot/mutate/push dance.
6. **`tools/`** — `DrawTool` subclasses (`RectangleTool`, `TextTool`, `LineTool`) and `SelectTool`. Tools translate mouse events into provisional shapes/transforms; the `CanvasWidget` commits them as commands on mouse-up. Resize/move handles are in `tools/__init__.py` (`Handle`, `get_handles`, `handle_at`). `SelectTool` drags route through one in-flight `Gesture` (`tools/gestures.py` — `MoveGesture`, `ResizeGesture`, `LineHandleGesture`, `EdgeDragGesture`, `RectSelectGesture`); each gesture owns its own before-snapshot and returns a typed `GestureCommit` on mouse-up. Tools also expose visual hints to the renderer via `overlays() -> list[Overlay]` (`tools/overlays.py` — `SnapHighlight`, `EdgeHover`); the renderer dispatches on overlay type rather than introspecting tool fields.
7. **`controllers.py`** + **`sidebar_state.py`** — `ToolController` holds the persistent style state (current border style, line style, line endings) and constructs tools. `compute_sidebar_state(tool, tool_ctrl) -> SidebarState` (in `sidebar_state.py`) is a pure function that derives each Panel's visibility and active value from the current tool and selection; `SidebarView.apply(state)` is a thin adapter that pushes that snapshot into Textual widgets. The pure function is the test surface — see `tests/test_sidebar_state.py`.
8. **`rendering.py`** — `FrameRenderer` caches per-frame compositing data and emits Textual `Strip`s line-by-line. It merges foreground-only highlight styles with the canvas widget's resolved base style so themed backgrounds don't bleed. Tool-driven highlights (snap edges, hovered line segments) come from `tool.overlays()`, not from ad-hoc `hasattr` introspection. Call `invalidate()` on any change.
9. **`widgets/`** — `CanvasWidget` (the big one: viewport, scroll, mouse routing, drag state, selection rectangle), plus `panels/` (toolbar, border/line/alignment/layer/export panels), `modals.py`, `status_bar.py`.
10. **`app.py`** — `PalatermApp`: keybindings, panel/tool wiring, file open/save, export. The Textual `CSS` lives inline here.
11. **`exporters.py`** — `export_html`, `export_svg`, `export_presenterm`. `serialization.py` is the JSON `.palaterm` format (load/save).

### Conventions worth knowing

- **Coords are character cells.** `col` = x, `row` = y. Lines additionally use braille sub-pixel positions inside `LineShape` for the "straight" style.
- **Z-order = list order.** `bring_to_front` / `send_to_back` reorder `canvas.shapes` in place.
- **`BoxShape` is both rectangles and text boxes** — they only differ by whether `text` is set and how the border/text alignment fields are used.
- **Coverage intentionally excludes UI surfaces** (`app.py`, `widgets/*`, `controllers.py`'s `SidebarView`) — those are exercised by manual UI testing. Keep core logic (`canvas`, `commands`, `models`, `crossings`, `connectors`, `serialization`, `exporters`, `rendering`, `sidebar_state`, `style_application`, `tools/overlays`, `tools/gestures`) covered by `tests/`.
- **`LineShape.routing`** is the atomic edge-routing snapshot (a frozen `LineRouting(joints, edges_modified)`). Snapshot `line.routing` and assign it back via the property setter; don't reach for `_joint_points` / `_edges_modified` directly. `MoveLineEdge` and the line-style branch of `apply_attribute_change` round-trip via this seam.
- **`tests/fixtures.py`** builds a deterministic 50-shape canvas (`build_fixed_canvas`) shared between tests and benchmarks — use the `fixed_canvas` / `empty_canvas` fixtures from `conftest.py` rather than constructing ad-hoc canvases.

## Keybindings

See README.md — the source of truth is `BINDINGS` in `palaterm/app.py`.
