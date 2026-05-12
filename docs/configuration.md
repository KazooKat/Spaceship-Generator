# Configuration

A category-first index of every knob that controls ship generation across
the CLI, the Flask web form, and the `generate(...)` / `ShapeParams(...)`
Python API. For the per-flag CLI reference see [cli.md](cli.md); for the
web form + HTTP API see [web_ui.md](web_ui.md); for pipeline diagrams see
[architecture.md](architecture.md).

## Shape

Geometric dials that control the ship's silhouette and parts layout.

| CLI flag | Web form field | `generate()` / `ShapeParams` kwarg | Notes |
|---|---|---|---|
| `--length` | `length` | `ShapeParams.length` | Z-axis (nose-to-tail), default 40, min 8 |
| `--width` | `width` | `ShapeParams.width_max` | X-axis (mirror axis), default 20, min 4 |
| `--height` | `height` | `ShapeParams.height_max` | Y-axis (Minecraft Y-up), default 12, min 4 |
| `--ship-size WxHxL` | — | (overrides above three) | CLI shortcut for all three dims |
| `--engines` | `engines` | `ShapeParams.engine_count` | 0..6, default 2 |
| `--wing-prob` | `wing_prob` | `ShapeParams.wing_prob` | 0..1, default 0.75 |
| `--hull-style` | `hull_style` | `generate(hull_style=...)` | `HullStyle` enum or `None` (legacy) |
| `--hull-style-front` | — | `generate(hull_style_front=...)` | Z-axis blend (paired with `--hull-style-rear`) |
| `--hull-style-rear` | — | `generate(hull_style_rear=...)` | Z-axis blend (paired with `--hull-style-front`) |
| `--engine-style` | `engine_style` | `generate(engine_style=...)` | `EngineStyle` enum or `None` |
| `--wing-style` | `wing_style` | `ShapeParams.wing_style` | `WingStyle` enum, default `straight` |
| `--cockpit` | `cockpit` | `ShapeParams.cockpit_style` | `CockpitStyle`, default `bubble` |
| `--cockpit-style` | `cockpit_style` | `generate(cockpit_style=...)` | Override of `--cockpit` legacy selection |
| `--structure-style` | `structure_style` | `ShapeParams.structure_style` | `StructureStyle`, default `frigate` |
| `--hull-noise` | — | `ShapeParams.hull_noise` | 0..1, hull-membrane noise displacement |

## Palette

Block-palette selection and palette tooling.

| CLI flag | Web form field | `generate()` kwarg | Notes |
|---|---|---|---|
| `--palette NAME` | `palette` | `generate(palette=...)` | Palette name or `random` for seed-deterministic pick |
| `--list-palettes` | — (`/api/palettes`) | — | Lists palettes and exits |
| `--list-palettes-json` | — | — | Machine-readable variant |
| `--palette-info NAME` | — | — | Prints role → block ID + hex preview |
| `--validate-palette PATH` | — | — | Strict palette-lint against a YAML file |

## Greebles

Surface detail scatter (turrets, dishes, vents, ...).

| CLI flag | Web form field | `generate()` / `ShapeParams` kwarg | Notes |
|---|---|---|---|
| `--greeble-density` | `greeble_density` | `generate(greeble_density=...)` | 0..1 (scatter); `ShapeParams.greeble_density` capped at 0.5 |
| `--no-greebles` | (`greeble_density=0`) | `generate(greeble_density=0)` | Shortcut, mutually exclusive with `--greeble-density` |
| `--greeble-style TYPE` | — | `generate(greeble_types=[...])` | Restrict to one `GreebleType` |
| `--list-greeble-types` | — (`/api/greeble-types`) | — | List enum members and exit |
| `--list-greeble-types-json` | — | — | Machine-readable variant |

## Weapons

Top-facing weapon emplacement scatter.

| CLI flag | Web form field | `generate()` kwarg | Notes |
|---|---|---|---|
| `--weapon-count N` | `weapon_count` | `generate(weapon_count=...)` | 0..8 (web clamped); 0 disables |
| `--no-weapons` | (`weapon_count=0`) | `generate(weapon_count=0)` | Shortcut, mutually exclusive with `--weapon-count` |
| `--weapon-types A,B` | `weapon_types` | `generate(weapon_types=[...])` | Restrict allow-list; default = all `WeaponType` |
| `--list-weapon-types` | — (`/api/weapon-types`) | — | List enum members and exit |
| `--list-weapon-types-json` | — | — | Machine-readable variant |

## Output

File output, sidecars, and machine-readable summaries.

| CLI flag | Web form field | `generate()` kwarg | Notes |
|---|---|---|---|
| `--out DIR` | (server-managed) | `generate(out_dir=...)` | `.litematic` output directory |
| `--filename NAME` | — | `generate(filename=...)` | Default `ship_<seed>.litematic` |
| `--output -` | — | — | Stream `.litematic` bytes to stdout |
| `--author TEXT` | — | `generate(author=...)` | Schematic author metadata |
| `--name TEXT` | — | `generate(name=...)` | Schematic display name |
| `--preview` / `--preview-size WxH` | (WebGL canvas + `/preview/`) | `generate(with_preview=True, preview_size=...)` | PNG preview, default 800×800 |
| `--preview-azimuth` / `--preview-elevation` | (`elev`/`azim` query) | — | Camera angles in degrees |
| `--output-json` | — | — | NDJSON summary per ship to stdout |
| `--output-json-schema` | — | — | JSON Schema for the `--output-json` payload |
| `--stats` / `--stats-json` | — | — | Per-role block-count tally |
| `--block-summary` | — | — | `block_id,count` CSV (survival mode) |
| `--export-manifest` | — | — | Write `<name>.json` sidecar |
| `--from-manifest FILE` | — | — | Reproduce a prior run from manifest |
| (`scripts/gen_gallery.py`) | — | — | Standalone gallery renderer |

## Determinism / seeding

Same inputs → same ship. Seed plumbing is shared across CLI / web / API.

| CLI flag | Web form field | `generate()` kwarg | Notes |
|---|---|---|---|
| `--seed N` | `seed` | `generate(seed=...)` | Integer seed; default = random |
| `--seeds A,B,C` or `A-B` | — | (loop in caller) | Bulk; mutually exclusive with `--seed` / `--repeat` |
| `--seed-phrase TEXT` | `seed_phrase` | (caller hashes) | SHA-256 mod 2^31-1, overrides `seed` when non-empty |
| `--repeat N` | — | (loop in caller) | Generate N consecutive seeds |

## Performance / runtime

CLI verbosity, batching, and bench tooling.

| CLI flag | Web form field | `generate()` kwarg | Notes |
|---|---|---|---|
| `--quiet` / `-q` | — | — | Suppress success-path stdout (errors still go to stderr) |
| `--verbose` | — | — | Per-seed timings; mutually exclusive with `--quiet` |
| `--repeat N` | — | — | Batch N consecutive seeds in one process |
| `--fleet-count N` | (`/download-fleet?count=N`) | (uses `fleet` module) | Coherent fleet of N ships |
| `--fleet-size-tier` | (`size_tier`) | — | `small` / `mid` / `large` / `capital` / `mixed` |
| `--fleet-style-coherence` | (`style_coherence` / `coherence`) | — | 0..1, default 0.7 |
| `--dry-run` | — | — | Resolve params + emit JSON without writing; see [bench.md](bench.md) for `scripts/bench_*.py` |

## Capturing the effective config via `--config-dump`

`--config-dump` emits the resolved generator-relevant args (the values
that `generate()` would actually receive) as a single JSON document
`{"effective_config":{...}}` to stdout, then exits 0 without producing a
ship. The dump runs AFTER `--preset` resolution AND `--palette random`
resolution, so it reflects the final merged values — useful for
debugging "what did I actually run". NOT silenced by `--quiet` (same
carve-out as `--stats-json` / `--list-presets-json`); mutex with
`--output`, `--output-json`, `--output-json-schema`, `--meta-json`.

```bash
$ python -m spaceship_generator --config-dump --preset corvette --seed 42 --palette desert_oasis
{"effective_config": {"cockpit_style": "fighter", "engine_style": "twin",
 "engines": 2, "greeble_density": 0.15, "hull_style": "wedge",
 "length": 36, "palette": "desert_oasis", "preset": "corvette",
 "seed": 42, "width": 18, "weapon_count": 2, ...}}
```

## Replaying / reproducing a captured run

There is no symmetric `--config-load` / `--config-file` flag (yet) — the
JSON dumped by `--config-dump` is for inspection, not direct re-feed.
To reproduce a previous run today:

- **Same ship, byte-identical**: pass `--export-manifest` on the original
  run to drop a `<name>.json` sidecar, then replay via
  `--from-manifest <FILE>` (reads `seed`, `palette`, and dims from the
  sidecar; mutex with `--seed` / `--seeds` / `--seed-phrase` / `--repeat`
  / `--fleet-count`). See the [Output](#output) table above.
- **Same flags, scripted**: extract the keys you care about from the
  `--config-dump` JSON and re-emit them as flags, e.g.
  `python -m spaceship_generator $(python -m spaceship_generator --config-dump ... | jq -r '.effective_config | "--seed \(.seed) --palette \(.palette) --preset \(.preset)"')`.

## Override precedence (preset → flag)

When `--preset` and an individual flag both touch the same field, the
explicit CLI flag wins. The merge order is:

1. `argparse` defaults (the column-3 values in the tables above)
2. `--preset NAME` overlays its kwargs onto fields the user did NOT pass
   explicitly (per-field check against the parsed argv: `--hull-style`,
   `--engine-style`, `--wing-style`, `--cockpit-style`,
   `--greeble-density`, `--weapon-count`, `--weapon-types`,
   `--length` / `--width` / `--height`)
3. Explicit CLI flag values override any preset value for the same field

`--config-dump` is the canonical way to verify which value actually won
end-to-end — the JSON reflects step 3:

```bash
$ python -m spaceship_generator --config-dump --preset corvette --hull-style needle --seed 7     | jq '.effective_config | {preset, hull_style, engine_style}'
{"preset": "corvette", "hull_style": "needle", "engine_style": "twin"}
```

Here `hull_style` came from the explicit `--hull-style needle` flag
(beating the preset's value), while `engine_style` was filled in by the
`corvette` preset (no explicit `--engine-style` was passed).

## Related documentation

- [cli.md](cli.md) — per-flag CLI reference
- [web_ui.md](web_ui.md) — web form + `/api/*` reference
- [architecture.md](architecture.md) — pipeline diagrams
- [quickstart.md](quickstart.md) — 5-minute walkthrough
- [troubleshooting.md](troubleshooting.md) — common failures + fixes
- [faq.md](faq.md) — "how do I...?" reference
