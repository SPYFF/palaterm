"""Render benchmark + regression guard for the palaterm canvas.

Measures the cost of the hot rendering paths against the shared
:func:`tests.fixtures.build_fixed_canvas` fixture (the "fixed-50" canvas
also used by ``bench_serialize.py`` and the test suite), so the benches,
the tests, and any regression baseline all describe the same scene.

Scenarios
---------
* ``composite_region`` — raw ``Canvas.composite`` over the whole viewport
  (the compositing hotspot underneath the renderer; no caching involved).
* ``cache_build`` — cold ``FrameRenderer`` cache build for the viewport.
* ``render_one_line`` — one ``render_line`` strip emission with a warm cache.
* ``full_frame`` — invalidate + render every visible line (cost of a full
  ``self.refresh()`` repaint).
* ``partial_hover`` — invalidate + render only the rows covering two shapes,
  modelling a hover swap after the region-scoped ``refresh`` optimization.
* ``drag_step`` — move a shape one column and repaint the union of its old +
  new bounds, modelling ``on_mouse_move`` during a drag.

Regression guard
----------------
Each run reports ``best`` and ``median`` µs/op. To catch rendering
regressions, persist a baseline and compare later runs against it:

    uv run python scripts/bench_render.py --save-baseline  # record baseline
    uv run python scripts/bench_render.py --check          # compare; exit 1 on regress

``--check`` fails (exit code 1) when any benchmark's median is slower than
its baseline median by more than ``--tolerance`` (default 0.25 = 25%).
Timing is noisy, so keep the tolerance generous; the baseline is meant to
catch structural regressions (an O(n) path going O(n²)), not single-digit
percent drift. The baseline is a small JSON file (default
``scripts/bench_render_baseline.json``). Render timings are wall-clock and
machine-specific, so this file is gitignored: record it once per machine
(or CI runner) and compare later runs on the *same* machine against it.

Run from repo root:
    uv run python scripts/bench_render.py
"""

from __future__ import annotations

import argparse
import gc
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Repo root on the import path so we can pull the shared canvas builder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from palaterm.geometry import Rect
from palaterm.models import BoxShape, CharSet
from palaterm.rendering import FrameRenderer
from palaterm.tools import SelectTool
from rich.style import Style as RichStyle
from tests.fixtures import build_fixed_canvas

VIEWPORT = Rect(0, 0, 200, 60)
BASE_STYLE = RichStyle.null()
DEFAULT_BASELINE = Path(__file__).with_name("bench_render_baseline.json")
DEFAULT_TOLERANCE = 0.25


@dataclass
class Result:
    name: str
    runs: int
    samples: list[float]

    @property
    def best_us(self) -> float:
        return min(self.samples) * 1e6 / self.runs

    @property
    def median_us(self) -> float:
        return statistics.median(self.samples) * 1e6 / self.runs

    def line(self) -> str:
        return (
            f"{self.name:<42} best={self.best_us:8.1f}µs/op "
            f"median={self.median_us:8.1f}µs/op  "
            f"({self.runs} ops × {len(self.samples)} samples)"
        )


def time_it(name: str, fn, *, runs: int, samples: int = 5, warmup: int = 1) -> Result:
    for _ in range(warmup):
        fn()
    gc.collect()
    gc.disable()
    try:
        out: list[float] = []
        for _ in range(samples):
            t0 = time.perf_counter()
            for _ in range(runs):
                fn()
            out.append(time.perf_counter() - t0)
    finally:
        gc.enable()
    return Result(name=name, runs=runs, samples=out)


def collect_results() -> list[Result]:
    """Run every benchmark scenario against the fixed-50 canvas."""
    results: list[Result] = []

    # 0) Raw compositing over the viewport — the hotspot underneath the
    #    renderer. Rebuild a fresh canvas per timing group so there is no
    #    hidden per-shape caching in play.
    composite_canvas = build_fixed_canvas()

    def composite_region():
        composite_canvas.composite(VIEWPORT, CharSet.UNICODE)

    results.append(time_it("composite_region", composite_region, runs=200))

    canvas = build_fixed_canvas()
    renderer = FrameRenderer(canvas)

    # 1) Cold cache build (FrameRenderer._ensure_cache).
    def cache_build():
        renderer.invalidate()
        renderer._ensure_cache(VIEWPORT, None, BASE_STYLE, CharSet.UNICODE)

    results.append(time_it("cache_build", cache_build, runs=200))

    # 2) Per-line strip emission with a warm cache.
    renderer.invalidate()
    renderer._ensure_cache(VIEWPORT, None, BASE_STYLE, CharSet.UNICODE)

    def render_one_line():
        renderer.render_line(0, VIEWPORT, None, BASE_STYLE, CharSet.UNICODE)

    results.append(time_it("render_one_line", render_one_line, runs=2000))

    # 3) Full-frame refresh: invalidate + render every visible line.
    #    This is what runs on a `self.refresh()` call today.
    def full_frame():
        renderer.invalidate()
        for y in range(VIEWPORT.height):
            renderer.render_line(y, VIEWPORT, None, BASE_STYLE, CharSet.UNICODE)

    results.append(time_it("full_frame (all 60 lines)", full_frame, runs=100))

    # 4) Hover-swap partial refresh: invalidate + render only the rows
    #    covering the union of two shape bounds. Models a hover swap where
    #    Textual's StylesCache only calls render_line for these rows.
    a = canvas.shapes[5]
    b = canvas.shapes[7]
    union_top = min(a.bound.top, b.bound.top)
    union_bottom = max(a.bound.bottom, b.bound.bottom)
    affected_rows = list(
        range(max(union_top, VIEWPORT.top), min(union_bottom, VIEWPORT.bottom) + 1)
    )
    tool = SelectTool()
    tool.hover_shape = b

    def partial_hover():
        renderer.invalidate()
        for row in affected_rows:
            y = row - VIEWPORT.top
            renderer.render_line(y, VIEWPORT, tool, BASE_STYLE, CharSet.UNICODE)

    results.append(
        time_it(f"partial_hover ({len(affected_rows)} lines)", partial_hover, runs=200)
    )

    # 5) Drag step: move a shape one column, then partial-refresh the union of
    #    its old + new bound. Models on_mouse_move during a drag.
    drag_target = next(
        s for s in canvas.shapes if isinstance(s, BoxShape) and not s.text
    )
    drag_tool = SelectTool()
    drag_tool.selected = [drag_target]

    def drag_step():
        before = drag_target.bound
        drag_target.move(1, 0)
        after = drag_target.bound
        union = Rect(
            min(before.left, after.left),
            min(before.top, after.top),
            max(before.right, after.right) - min(before.left, after.left) + 1,
            max(before.bottom, after.bottom) - min(before.top, after.top) + 1,
        )
        renderer.invalidate()
        for row in range(
            max(union.top, VIEWPORT.top), min(union.bottom, VIEWPORT.bottom) + 1
        ):
            y = row - VIEWPORT.top
            renderer.render_line(y, VIEWPORT, drag_tool, BASE_STYLE, CharSet.UNICODE)
        drag_target.move(-1, 0)  # restore for repeatable runs

    results.append(time_it("drag_step (move 1 col + repaint)", drag_step, runs=200))

    return results


# --- baseline persistence / regression check -------------------------------


def _base_name(name: str) -> str:
    """Strip the trailing ``(... lines)`` count so baselines stay stable
    even if the fixture geometry shifts the affected-row count slightly."""
    return name.split(" (")[0]


def save_baseline(results: list[Result], path: Path) -> None:
    payload = {
        "viewport": [VIEWPORT.width, VIEWPORT.height],
        "benchmarks": {_base_name(r.name): round(r.median_us, 2) for r in results},
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Baseline written to {path} ({len(results)} benchmarks).")


def check_baseline(results: list[Result], path: Path, tolerance: float) -> int:
    """Compare results against the baseline. Return process exit code."""
    if not path.exists():
        print(f"No baseline at {path}. Run with --save-baseline first.")
        return 1
    try:
        baseline = json.loads(path.read_text()).get("benchmarks", {})
    except (OSError, ValueError) as exc:
        print(f"Could not read baseline {path}: {exc}")
        return 1

    print(f"\nRegression check (tolerance {tolerance:.0%}) against {path.name}:")
    print("-" * 80)
    regressed: list[str] = []
    for r in results:
        key = _base_name(r.name)
        base = baseline.get(key)
        if base is None:
            print(f"  {key:<40} (no baseline entry — skipped)")
            continue
        delta = (r.median_us - base) / base
        limit = base * (1 + tolerance)
        if r.median_us > limit:
            mark = "REGRESSION"
            regressed.append(key)
        elif delta < -tolerance:
            mark = "improved  "
        else:
            mark = "ok        "
        print(
            f"  {mark} {key:<30} {r.median_us:8.1f}µs vs {base:8.1f}µs  ({delta:+.1%})"
        )

    stale = set(baseline) - set(map(_base_name, [r.name for r in results]))
    if stale:
        print(f"\n  note: baseline has entries no longer benchmarked: {sorted(stale)}")

    if regressed:
        print(f"\nFAILED: {len(regressed)} benchmark(s) regressed: {sorted(regressed)}")
        return 1
    print("\nPASS: no regressions beyond tolerance.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Record current medians as the regression baseline.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare against the baseline; exit 1 on regression.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help=f"Baseline JSON path (default: {DEFAULT_BASELINE.name}).",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE,
        help=f"Slowdown fraction that trips --check (default: {DEFAULT_TOLERANCE}).",
    )
    args = parser.parse_args()

    canvas = build_fixed_canvas()
    n_shapes = len(canvas.shapes)
    print(
        f"Canvas: fixed-50 fixture, {n_shapes} shapes, "
        f"viewport {VIEWPORT.width}x{VIEWPORT.height}"
    )
    print()

    results = collect_results()

    print(f"{'benchmark':<42} {'best':>16} {'median':>16}")
    print("-" * 80)
    for r in results:
        print(r.line())
    print()
    print("Notes:")
    print("- 'composite_region' is the raw compositing cost with no caching.")
    print("- 'full_frame' is the cost paid on any self.refresh() (full repaint).")
    print("- 'partial_hover' is what hover-swap costs after the optimization:")
    print("  same cache rebuild, but only a fraction of lines actually rendered.")

    if args.save_baseline:
        save_baseline(results, args.baseline)
    if args.check:
        return check_baseline(results, args.baseline, args.tolerance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
