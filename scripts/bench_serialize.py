"""Diff-noise diagnostic for the .palaterm save format.

Runs three checks against the current live serializer:

  * determinism — saving the same canvas twice produces byte-identical
    output (no random ordering, no random IDs in the bench's fixture).
  * in-place edits — moving / resizing / restyling existing shapes;
    expected to produce exactly N diff lines for N edits.
  * structural churn — deleting 25 shapes and adding 25 new ones
    interleaved; surfaces how add/remove sequences read in a diff.

For each scenario the bench reports git diff metrics plus a
``lines_moved_unchanged`` count: shape lines that exist in both the
before and after files but at different line numbers. This is the
metric that would spike if any reordering scheme failed to keep
untouched shapes pinned.

``git diff --no-index`` operates on arbitrary file paths (no repo state
touched), so this is safe to run anywhere.

Regression guard
----------------
Unlike the render bench, these metrics are deterministic (byte-identical
runs, exact diff-line counts), so the baseline can assert equality rather
than a fuzzy tolerance and is safe to commit:

    uv run python scripts/bench_serialize.py --save-baseline  # record baseline
    uv run python scripts/bench_serialize.py --check          # exit 1 on regression

``--check`` fails when determinism breaks or when any structural metric
(diff hunks / changed lines / lines-moved-unchanged) differs from the
baseline. Byte sizes are reported as informational drift, never a failure
(they legitimately move when format field names or whitespace change).

Run from repo root:
    uv run python scripts/bench_serialize.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
# Repo root on the import path so we can pull the shared canvas builder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from palaterm.canvas import Canvas
from palaterm.geometry import Rect
from palaterm.models import (
    BorderStyle,
    BoxShape,
    CharSet,
    EndingStyle,
    LineShape,
)
from palaterm.serialization import save_canvas
from tests.fixtures import build_fixed_canvas


def apply_in_place_edits(canvas: Canvas) -> None:
    """A fixed sequence of edits covering style/text/resize/movement."""
    shapes = {s.id: s for s in canvas.shapes}
    for sid in ("s00", "s05", "s10", "s15"):
        shapes[sid].move(2, 1)
    box = shapes["s01"]
    assert isinstance(box, BoxShape)
    box.rect = Rect(box.rect.left, box.rect.top, box.rect.width + 3, box.rect.height)
    box2 = shapes["s02"]
    assert isinstance(box2, BoxShape)
    box2.border = BorderStyle.HEAVY
    box3 = shapes["s03"]
    assert isinstance(box3, BoxShape)
    box3.text = "hello"
    shapes["s04"].fg = "red"
    line = shapes["s30"]
    assert isinstance(line, LineShape)
    line.end_ending = EndingStyle.ARROW


def apply_structural_churn(canvas: Canvas) -> None:
    """Delete 25 shapes and add 25 new shapes, interleaved one-for-one."""
    for i in range(0, 50, 2):
        sid = f"s{i:02}"
        shape = next((s for s in canvas.shapes if s.id == sid), None)
        if shape is not None:
            canvas.remove_shape(shape)

    for i in range(25):
        new = BoxShape(
            Rect(2 + i * 7, 50 + (i % 3) * 10, 6, 4),
            border=BorderStyle.LIGHT,
        )
        new.id = f"n{i:02}"
        canvas.add_shape(new)


# --- measurement -----------------------------------------------------------


@dataclass
class ScenarioStats:
    bytes_before: int
    bytes_after: int
    diff_changed_lines: int
    diff_hunks: int
    diff_bytes: int
    lines_moved_unchanged: int


def _diff_metrics(before: Path, after: Path) -> tuple[int, int, int]:
    """Return (changed_lines, hunks, bytes) from `git diff`."""
    proc = subprocess.run(
        ["git", "diff", "--no-index", "--no-color", str(before), str(after)],
        capture_output=True,
        text=True,
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"git diff failed ({proc.returncode}): {proc.stderr}")
    out = proc.stdout
    changed, hunks = 0, 0
    for line in out.splitlines():
        if line.startswith("@@"):
            hunks += 1
        elif line.startswith("+++") or line.startswith("---"):
            continue
        elif line.startswith("+") or line.startswith("-"):
            changed += 1
    return changed, hunks, len(out)


def _shape_lines(path: Path) -> list[str]:
    """Return only the per-shape JSON lines (skip skeleton + brackets)."""
    lines = []
    for raw in path.read_text().splitlines():
        s = raw.strip().rstrip(",")
        if s.startswith('{"t":') or s.startswith('{"lid":'):
            lines.append(s)
    return lines


def _lines_moved_unchanged(before: Path, after: Path) -> int:
    """Count shape lines that exist in both files but at different positions."""
    before_lines = _shape_lines(before)
    after_lines = _shape_lines(after)
    before_pos = {line: i for i, line in enumerate(before_lines)}
    after_pos = {line: i for i, line in enumerate(after_lines)}
    moved = 0
    for line, b_idx in before_pos.items():
        a_idx = after_pos.get(line)
        if a_idx is not None and a_idx != b_idx:
            moved += 1
    return moved


def measure_scenario(label: str, mutate_fn, tmpdir: Path) -> ScenarioStats:
    canvas = build_fixed_canvas()
    before = tmpdir / f"{label}_before.palaterm"
    after = tmpdir / f"{label}_after.palaterm"

    save_canvas(canvas, before, CharSet.UNICODE)
    mutate_fn(canvas)
    save_canvas(canvas, after, CharSet.UNICODE)

    changed, hunks, dbytes = _diff_metrics(before, after)
    return ScenarioStats(
        bytes_before=before.stat().st_size,
        bytes_after=after.stat().st_size,
        diff_changed_lines=changed,
        diff_hunks=hunks,
        diff_bytes=dbytes,
        lines_moved_unchanged=_lines_moved_unchanged(before, after),
    )


def check_determinism(tmpdir: Path) -> tuple[bool, int]:
    canvas = build_fixed_canvas()
    a = tmpdir / "det_a.palaterm"
    b = tmpdir / "det_b.palaterm"
    save_canvas(canvas, a, CharSet.UNICODE)
    save_canvas(canvas, b, CharSet.UNICODE)
    return a.read_bytes() == b.read_bytes(), a.stat().st_size


def _print_table(title: str, stats: ScenarioStats) -> None:
    print(title)
    print("-" * len(title))
    rows = [
        ("file size before", stats.bytes_before),
        ("file size after", stats.bytes_after),
        ("diff hunks", stats.diff_hunks),
        ("diff +/- lines", stats.diff_changed_lines),
        ("diff bytes", stats.diff_bytes),
        ("lines moved unchanged", stats.lines_moved_unchanged),
    ]
    for name, v in rows:
        print(f"  {name:<24}{v:>10,}")
    print()


# --- baseline persistence / regression check -------------------------------

DEFAULT_BASELINE = Path(__file__).with_name("bench_serialize_baseline.json")

# Metrics that must match the baseline exactly. Byte sizes are excluded from
# the equality check (they legitimately shift when the format's field names or
# whitespace change); the structural metrics are what guard against churn
# regressions. Byte sizes are still recorded and shown as drift.
_EXACT_KEYS = (
    "diff_hunks",
    "diff_changed_lines",
    "lines_moved_unchanged",
)


def collect_results(tmpdir: Path) -> dict:
    """Run every scenario and return a JSON-serializable result dict."""
    determinism_ok, det_bytes = check_determinism(tmpdir)
    return {
        "determinism_ok": determinism_ok,
        "determinism_bytes": det_bytes,
        "in_place": asdict(measure_scenario("ip", apply_in_place_edits, tmpdir)),
        "structural_churn": asdict(
            measure_scenario("ch", apply_structural_churn, tmpdir)
        ),
    }


def save_baseline(results: dict, path: Path) -> None:
    path.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nBaseline written to {path}.")


def check_baseline(results: dict, path: Path) -> int:
    """Compare deterministic metrics against the baseline. Return exit code."""
    if not path.exists():
        print(f"\nNo baseline at {path}. Run with --save-baseline first.")
        return 1
    try:
        base = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        print(f"\nCould not read baseline {path}: {exc}")
        return 1

    print(f"\nRegression check against {path.name}:")
    print("-" * 60)
    failures: list[str] = []

    if not results["determinism_ok"]:
        failures.append("determinism (two saves not byte-identical)")
        print("  REGRESSION determinism: saves are no longer byte-identical")
    else:
        print("  ok         determinism: saves byte-identical")

    for scenario in ("in_place", "structural_churn"):
        cur = results[scenario]
        ref = base.get(scenario, {})
        for key in _EXACT_KEYS:
            cv, rv = cur.get(key), ref.get(key)
            if rv is None:
                print(f"  {scenario}.{key}: no baseline entry — skipped")
                continue
            if cv != rv:
                failures.append(f"{scenario}.{key}: {rv} -> {cv}")
                print(f"  REGRESSION {scenario}.{key}: {rv} -> {cv}")
            else:
                print(f"  ok         {scenario}.{key}: {cv}")
        # Byte sizes: informational drift only, never a failure.
        for bkey in ("bytes_before", "bytes_after"):
            cv, rv = cur.get(bkey), ref.get(bkey)
            if rv is not None and cv != rv:
                print(f"  note       {scenario}.{bkey}: {rv} -> {cv} (size drift)")

    if failures:
        print(f"\nFAILED: {len(failures)} regression(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nPASS: structural metrics match baseline.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Record current metrics as the regression baseline.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare structural metrics against the baseline; exit 1 on regression.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help=f"Baseline JSON path (default: {DEFAULT_BASELINE.name}).",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        results = collect_results(tmpdir)

        mark = "✓" if results["determinism_ok"] else "✗"
        print(
            "determinism: same canvas, two saves byte-identical: "
            f"{mark}  ({results['determinism_bytes']:,} B)"
        )
        print()

        _print_table(
            "in-place edits (style/text/resize/movement, no add/remove)",
            ScenarioStats(**results["in_place"]),
        )
        _print_table(
            "structural churn (delete 25, add 25, interleaved)",
            ScenarioStats(**results["structural_churn"]),
        )

        print("Reading the metrics:")
        print("- 'lines moved unchanged' counts shape lines that appear in")
        print("  both files but at different line numbers. Non-zero means")
        print("  some untouched shapes shifted on disk; git diff still")
        print("  reports them correctly (unchanged lines aren't shown), but")
        print("  the count quantifies the underlying churn.")
        print("- 'diff hunks' is what a reviewer actually scans. One hunk")
        print("  means git groups all the edits together; more hunks means")
        print("  separated regions in the file.")

        if args.save_baseline:
            save_baseline(results, args.baseline)
        if args.check:
            return check_baseline(results, args.baseline)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
