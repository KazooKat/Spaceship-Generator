"""Compare two bench_generator.py baselines and emit a markdown diff table.

Usage:
    python scripts/bench_compare.py <baseline.json> <current.json> [--threshold 0.10]

Both JSON files are expected to have the schema produced by
``bench_generator.py --save`` (a dict with ``wall`` and ``phases`` keys).

Exits 0 if no phase regressed by more than ``--threshold`` (default 10%),
else exits 1. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Markdown table uses non-ASCII status glyphs; force UTF-8 output so the
# script works on Windows consoles (cp1252) as well as Linux CI runners.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

PHASE_ORDER = ["shape_build", "role_assign", "palette_lookup", "export", "other", "total"]

OK = "\u2713"    # check mark
WARN = "\u26a0"  # warning sign
FAIL = "\u2717"  # cross mark


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("baseline", type=Path, help="baseline JSON (from bench --save)")
    p.add_argument("current", type=Path, help="current JSON (from bench --save)")
    p.add_argument(
        "--threshold",
        type=float,
        default=0.10,
        help="regression threshold as fraction (default 0.10 = 10%%)",
    )
    return p.parse_args()


def load_baseline(path: Path) -> dict[str, Any]:
    if not path.is_file():
        print(f"bench_compare: file not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        print(f"bench_compare: invalid JSON in {path}: {exc}", file=sys.stderr)
        raise SystemExit(2)


def get_phase_seconds(data: dict[str, Any], phase: str) -> float:
    """Return total_s for a given phase; ``total`` reads from ``wall``."""
    if phase == "total":
        return float(data.get("wall", {}).get("total_s", 0.0))
    phases = data.get("phases", {}) or {}
    entry = phases.get(phase, {}) or {}
    return float(entry.get("total_s", 0.0))


def classify(delta_pct: float, threshold_pct: float) -> str:
    """Map a delta percentage to a status glyph.

    Values near zero pass. Between 0 and threshold we warn. At/above
    threshold we fail. Negative deltas (speed-ups) always pass.
    """
    if delta_pct <= 0:
        return OK
    if delta_pct < threshold_pct * 0.5:
        return OK
    if delta_pct < threshold_pct:
        return WARN
    return FAIL


def compute_rows(
    baseline: dict[str, Any], current: dict[str, Any], threshold: float
) -> list[tuple[str, float, float, float, str]]:
    rows: list[tuple[str, float, float, float, str]] = []
    threshold_pct = threshold * 100.0
    for phase in PHASE_ORDER:
        b = get_phase_seconds(baseline, phase)
        c = get_phase_seconds(current, phase)
        if b <= 0 and c <= 0:
            continue
        if b > 0:
            delta_pct = (c - b) / b * 100.0
        else:
            # New phase time appearing where baseline was zero — always fail.
            delta_pct = float("inf")
        status = classify(delta_pct, threshold_pct)
        rows.append((phase, b, c, delta_pct, status))
    return rows


def render_markdown(
    rows: list[tuple[str, float, float, float, str]], threshold: float
) -> str:
    lines: list[str] = []
    lines.append(f"### Perf bench (threshold {threshold * 100:.0f}%)")
    lines.append("")
    lines.append("| phase | baseline_s | current_s | delta_% | status |")
    lines.append("|---|---:|---:|---:|:---:|")
    for phase, b, c, delta_pct, status in rows:
        if delta_pct == float("inf"):
            delta_str = "+inf"
        else:
            delta_str = f"{delta_pct:+.1f}%"
        lines.append(f"| {phase} | {b:.4f} | {c:.4f} | {delta_str} | {status} |")
    lines.append("")
    lines.append(
        f"Legend: {OK} within half-threshold, {WARN} between half- and full threshold, "
        f"{FAIL} regressed beyond {threshold * 100:.0f}%."
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    baseline = load_baseline(args.baseline)
    current = load_baseline(args.current)
    rows = compute_rows(baseline, current, args.threshold)
    print(render_markdown(rows, args.threshold))
    regressed = any(status == FAIL for _, _, _, _, status in rows)
    return 1 if regressed else 0


if __name__ == "__main__":
    raise SystemExit(main())
