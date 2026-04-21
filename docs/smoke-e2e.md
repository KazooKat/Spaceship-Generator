# End-to-End Smoke Test

`scripts/smoke_e2e.py` is a manual / nightly sanity sweep that exercises
every palette and every style value of the public generator surface.

## When to run

- Before cutting a release.
- After touching `generator.py`, `palette.py`, `shape/`, `export.py`,
  `structure_styles.py`, `engine_styles.py`, or `wing_styles.py`.
- After adding a new palette YAML or a new enum member.
- On a nightly CI job (not per-PR — too slow).

Per-PR CI runs the smaller wrapper in `tests/test_smoke_e2e.py`
automatically.

## How to run

Full sweep (all palettes + all pinned combos):

```bash
.venv/Scripts/python scripts/smoke_e2e.py
```

Quick subset (first N palettes + all pinned combos — useful locally):

```bash
.venv/Scripts/python scripts/smoke_e2e.py --sample 3
```

## What it covers

- Lists every palette YAML in `palettes/`, and every value of
  `HullStyle`, `EngineStyle`, `WingStyle` plus `None` (legacy path).
- For each palette: `generate(seed=42, palette=<name>)` with defaults.
- For three pinned `(palette, hull_style, engine_style, wing_style,
  greeble_density)` combos: a full generate.
- Every generated `.litematic` is checked for size > 0 and is loaded via
  `litemapy.Schematic.load` to catch corrupt NBT / encoding regressions.
- Output goes to a per-case temp dir and is cleaned up on exit.

## Exit codes

- `0` — every case passed.
- `1` — at least one case failed (the printed table shows which).

## Expected runtime

Roughly 15-40 s full sweep on a modern laptop (~1-2 s per case, 21
palettes + 3 combos). `--sample 3` runs in ~5-8 s.
