"""End-to-end smoke test for the spaceship generator.

Covers every palette, every HullStyle/EngineStyle/WingStyle (plus None),
and three pinned combos. Verifies each .litematic is >0 bytes and loads
via :class:`litemapy.Schematic`. Stdlib + existing deps only.

Usage::

    .venv/Scripts/python scripts/smoke_e2e.py              # full sweep
    .venv/Scripts/python scripts/smoke_e2e.py --sample 3   # first 3 palettes

Exit: 0 = all pass, 1 = any fail (table names the offenders).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from litemapy import Schematic  # noqa: E402

from spaceship_generator.engine_styles import EngineStyle  # noqa: E402
from spaceship_generator.generator import generate  # noqa: E402
from spaceship_generator.shape import ShapeParams  # noqa: E402
from spaceship_generator.structure_styles import HullStyle  # noqa: E402
from spaceship_generator.wing_styles import WingStyle  # noqa: E402

PALETTES_DIR = REPO_ROOT / "palettes"

#: Pinned combos. Stable across runs — changing these is a smoke-scope change.
PINNED_COMBOS: list[dict] = [
    {
        "palette": "sci_fi_industrial",
        "hull_style": HullStyle.ARROW,
        "engine_style": EngineStyle.TWIN_NACELLE,
        "wing_style": WingStyle.SWEPT,
        "greeble_density": 0.15,
    },
    {
        "palette": "stealth_black",
        "hull_style": HullStyle.DAGGER,
        "engine_style": EngineStyle.ION_ARRAY,
        "wing_style": WingStyle.DELTA,
        "greeble_density": 0.0,
    },
    {
        "palette": "nordic_scout",
        "hull_style": HullStyle.BLOCKY_FREIGHTER,
        "engine_style": EngineStyle.QUAD_CLUSTER,
        "wing_style": WingStyle.GULL,
        "greeble_density": 0.25,
    },
]


@dataclass
class Result:
    name: str
    ok: bool
    elapsed_s: float
    detail: str = ""


def list_palettes() -> list[str]:
    return sorted(p.stem for p in PALETTES_DIR.glob("*.yaml"))


def _verify_litematic(path: Path) -> None:
    """Raise if the file is missing, empty, or unreadable by litemapy."""
    if not path.is_file():
        raise AssertionError(f"output not created: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise AssertionError(f"output is empty: {path} ({size} bytes)")
    schem = Schematic.load(str(path))
    regions = list(schem.regions.values())
    if not regions:
        raise AssertionError(f"{path}: loaded schematic has no regions")


def _run_case(name: str, fn: Callable[[Path], Path]) -> Result:
    """Run one case, verify the .litematic, and capture timing + errors."""
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="smoke_e2e_") as tmp:
        try:
            _verify_litematic(fn(Path(tmp)))
        except Exception as exc:  # pragma: no cover - captured in the table
            tb = traceback.format_exc(limit=2).strip().splitlines()[-1]
            return Result(
                name=name,
                ok=False,
                elapsed_s=time.perf_counter() - t0,
                detail=f"{type(exc).__name__}: {exc} | {tb}",
            )
    return Result(name=name, ok=True, elapsed_s=time.perf_counter() - t0)


def _palette_case(palette: str) -> Callable[[Path], Path]:
    def _run(tmp_dir: Path) -> Path:
        return generate(seed=42, palette=palette, out_dir=str(tmp_dir)).litematic_path
    return _run


def _combo_case(combo: dict) -> Callable[[Path], Path]:
    def _run(tmp_dir: Path) -> Path:
        sp = ShapeParams(wing_style=combo["wing_style"])
        return generate(
            seed=42,
            palette=combo["palette"],
            shape_params=sp,
            hull_style=combo["hull_style"],
            engine_style=combo["engine_style"],
            greeble_density=combo["greeble_density"],
            out_dir=str(tmp_dir),
        ).litematic_path
    return _run


def _print_inventory() -> None:
    print("HullStyle:   ", ["None"] + [h.value for h in HullStyle])
    print("EngineStyle: ", ["None"] + [e.value for e in EngineStyle])
    print("WingStyle:   ", ["None"] + [w.value for w in WingStyle])


def _print_table(results: list[Result]) -> None:
    col = max((len(r.name) for r in results), default=10)
    width = col + 2 + 6 + 2 + 9
    print()
    print(f"{'case':<{col}}  {'status':>6}  {'elapsed':>9}")
    print("-" * width)
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        print(f"{r.name:<{col}}  {status:>6}  {r.elapsed_s:>8.2f}s")
        if not r.ok and r.detail:
            print(f"  -> {r.detail}")
    total = sum(r.elapsed_s for r in results)
    fails = sum(1 for r in results if not r.ok)
    print("-" * width)
    print(
        f"{'TOTAL':<{col}}  {'OK' if fails == 0 else f'{fails} FAIL':>6}  "
        f"{total:>8.2f}s  (n={len(results)})"
    )


def run(sample: int | None = None) -> int:
    """Execute the smoke sweep. Return 0 on success, 1 on any failure."""
    palettes = list_palettes()
    if not palettes:
        print("no palettes found in palettes/", file=sys.stderr)
        return 1
    if sample is not None and sample > 0:
        palettes = palettes[:sample]

    print(f"smoke_e2e: {len(palettes)} palettes, {len(PINNED_COMBOS)} pinned combos")
    _print_inventory()

    results: list[Result] = []
    for name in palettes:
        results.append(_run_case(f"palette:{name}", _palette_case(name)))
    for i, combo in enumerate(PINNED_COMBOS):
        tag = (
            f"combo{i}:{combo['palette']}|{combo['hull_style'].value}"
            f"|{combo['engine_style'].value}|{combo['wing_style'].value}"
            f"|g={combo['greeble_density']}"
        )
        results.append(_run_case(tag, _combo_case(combo)))

    _print_table(results)
    return 0 if all(r.ok for r in results) else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--sample",
        type=int,
        default=None,
        help="run against only the first N palettes (quick subset for CI)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return run(sample=parse_args(argv).sample)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
