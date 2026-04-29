# CLI reference

Full flag catalog for `spaceship-generator` (`python -m spaceship_generator`),
in `argparse.add_argument` declaration order from
`src/spaceship_generator/cli.py`. Run `spaceship-generator --help` for the
authoritative one-shot dump; this page is a stable, link-friendly mirror.

For the palette catalog see [palettes.md](palettes.md).

## Identity

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--version`, `-V` | flag | — | Print package version (`spaceship_generator <ver>`) and exit 0. |

## Seed & seed selection

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--seed` | int | random | Integer seed. Mutually exclusive with `--seeds` and `--seed-phrase`. |
| `--seeds` | `A,B,C` or `A-B` (comma+range mix) | None | Bulk mode seed list. Mutually exclusive with `--seed`, `--repeat`. |
| `--seed-phrase` | TEXT | None | Hash TEXT to a deterministic seed (SHA-256 mod 2^31-1). Mutually exclusive with `--seed` / `--seeds`. |

## Palette selection

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--palette` | str (palette name or `random`) | `sci_fi_industrial` | Palette name. `random` picks one at generation time. |
| `--list-palettes` | flag | — | List available palettes and exit 0. |
| `--palette-info` | NAME | — | Print role -> block ID + hex preview color for NAME and exit (1 on unknown name). |

## Style discovery

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--list-styles` | flag | — | List hull / engine / wing / cockpit styles + weapon types and exit. |
| `--list-shape-styles` | flag | — | List `HullStyle` / `EngineStyle` / `WingStyle` only (narrower than `--list-styles`) and exit. |

## Presets

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--preset` | one of `battlecruiser`, `capital_carrier`, `corvette`, `dropship`, `freighter_heavy`, `gunship`, `interceptor`, `science_vessel`, `scout` | None | Named ship archetype. Individual style flags override preset values when explicitly set. |
| `--list-presets` | flag | — | List available preset names and exit. |
| `--list-weapon-types` | flag | — | Print all available weapon types and exit. |

## Shape parameters

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--length` | int | `40` | Ship length in blocks (Z axis). |
| `--width` | int | `20` | Ship max width in blocks (X axis). |
| `--height` | int | `12` | Ship max height in blocks (Y axis). |
| `--engines` | int | `2` | Number of engines (0..6). |
| `--wing-prob` | float | `0.75` | Probability of wings (0..1). |
| `--greeble-density` | float in `[0.0, 1.0]` | None (legacy default) | Surface greeble density. None preserves legacy `ShapeParams` defaults; mutually exclusive with `--no-greebles`. |
| `--no-greebles` | flag | off | Shortcut for `--greeble-density 0`. Mutually exclusive with `--greeble-density`. |
| `--greeble-style` | one of `turret`, `dish`, `vent`, `antenna`, `panel_line`, `sensor_pod`, `circuit_board`, `battle_damage`, `pipe_cluster`, `organic_growth`, `nano_mesh` | all types | Restrict greeble scatter to one type. |
| `--cockpit` | one of `bubble`, `pointed`, `integrated`, `canopy_dome`, `wrap_bridge`, `offset_turret` | `bubble` | Cockpit style (legacy auto-selection driver). |
| `--cockpit-style` | same choices as `--cockpit` | None | Cockpit archetype override. When omitted, `--cockpit` legacy selection is used. |
| `--structure-style` | one of `frigate`, `fighter`, `dreadnought`, `shuttle`, `hammerhead`, `carrier` | `frigate` | Ship archetype. |
| `--wing-style` | one of `straight`, `swept`, `delta`, `tapered`, `gull`, `split` | `straight` | Wing silhouette. |
| `--hull-style` | one of `arrow`, `saucer`, `whale`, `dagger`, `blocky_freighter`, `organic_bio`, `hexagonal_lattice`, `asymmetric_scavenger`, `modular_block`, `sleek_racing` | None (legacy hull) | Hull silhouette archetype. |
| `--hull-style-front` | same choices as `--hull-style` | None | Front hull profile for Z-axis blend (paired with `--hull-style-rear`; both required to engage; overrides `--hull-style`). |
| `--hull-style-rear` | same choices as `--hull-style` | None | Rear hull profile for Z-axis blend (paired with `--hull-style-front`). |
| `--engine-style` | one of `single_core`, `twin_nacelle`, `quad_cluster`, `ring`, `ion_array`, `plasma_pulse`, `magnetic_rail`, `bio_organic`, `retro_rocket_cluster` | None (legacy engines) | Engine archetype. |
| `--hull-noise` | float `AMPLITUDE` in `[0.0, 1.0]` | `0.0` | Procedural-noise hull distortion (asteroid-pitted look). 0.0 is byte-identical to legacy. Clamped to ±2 cells. Deterministic per seed. |

## Texture parameters

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--window-period` | int | `4` | Window every N cells along Z. |
| `--stripe-period` | int | `8` | Accent stripe every N cells along Z. |
| `--engine-glow-depth` | int | `1` | Engine-glow core thickness in cells. |
| `--hull-noise-ratio` | float | `0.0` | Fraction of HULL surface cells to darken (0.3 recommended for 60-30-10 palette effect). |
| `--panel-bands` | int | `1` | Number of HULL_DARK panel-line bands (1..3). |
| `--rivet-period` | int | `0` | HULL_DARK rivet dots every N cells on upper hull (0 disables). |
| `--engine-glow-ring` | flag | off | Wrap ENGINE_GLOW cells with a HULL_DARK ring. |

## Weapons

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--weapon-count` | int >= 0 | `0` | Number of weapons to scatter (0 disables). Requires the optional `weapon_styles` module. |
| `--weapon-types` | comma list (e.g. `turret_large,missile_pod`) | all types | Restrict weapon placement to listed types. |

## Repeat & fleet modes

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--repeat` | int >= 1 | `1` | Generate N ships with consecutive seeds. With `--seed S` -> seeds `S..S+N-1`. Mutually exclusive with `--seeds`. |
| `--fleet-count` | int >= 1 | `1` | Generate a coherent fleet of N ships. Each ship written as `ship_<seed>_<i>.litematic`. Requires the optional `fleet` module. |
| `--fleet-size-tier` | one of `small`, `mid`, `large`, `capital`, `mixed` | `mixed` | Fleet size tier (only used when `--fleet-count > 1`). |
| `--fleet-style-coherence` | float in `[0.0, 1.0]` | `0.7` | Fleet style coherence (only used when `--fleet-count > 1`). |

## Dry-run

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--dry-run` | flag | off | Resolve generation params, print as JSON, write nothing, exit 0. |

## Output

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--out` | Path | `./out` | Output directory. |
| `--filename` | str | `ship_<seed>.litematic` | Output filename. Ignored in `--seeds` bulk mode. |
| `--author` | str | `spaceship-generator` | Schematic author metadata. |
| `--name` | str | `Ship <seed>` | Schematic name metadata. |

## Preview

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--preview` | flag | off | Also save a PNG preview alongside the `.litematic` (same stem). |
| `--preview-size` | `WxH` (positive ints) | `800x800` | Preview size in pixels. |
| `--ship-size` | `WxHxL` (W>=4, H>=4, L>=8) | None | Override ship dimensions; overrides `--length`/`--width`/`--height` and any preset size. |
| `--preview-azimuth` | float (degrees) | `45` | Camera azimuth angle for preview. |
| `--preview-elevation` | float (degrees) | `30` | Camera elevation angle for preview. |

## Verbosity

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--verbose` | flag | off | Print per-seed timings. Mutually exclusive with `--quiet`. |
| `--quiet`, `-q` | flag | off | Suppress stdout on the success path (success lines, `--list-*`, `--dry-run` JSON, `--stats`, `--block-summary`, `--palette-info`). `--output-json` is exempt. Errors still flow through stderr. Mutually exclusive with `--verbose`. |

## Diagnostics & manifests

| Flag | Type / Value | Default | Description |
|---|---|---|---|
| `--stats` | flag | off | After each ship, print role -> cell-count table + total + density. |
| `--output-json` | flag | off | Print one-line NDJSON summary per ship to stdout (kept on under `--quiet`). |
| `--export-manifest` | flag | off | Write `<name>.json` sidecar (seed, palette, shape, block count, UTC timestamp) alongside each `.litematic`. |
| `--from-manifest` | FILE (path to manifest JSON) | None | Reproduce a ship from a prior `--export-manifest` sidecar. Mutually exclusive with `--seed` / `--seeds` / `--seed-phrase` / `--repeat` / `--fleet-count`. |
| `--block-summary` | flag | off | Print `block_id,count` CSV (sorted desc) after generation; useful for survival mode resource planning. |
