# Spaceship Generator

[![CI](https://github.com/KazooKat/Spaceship-Generator/actions/workflows/ci.yml/badge.svg)](https://github.com/KazooKat/Spaceship-Generator/actions/workflows/ci.yml)

Procedurally generate Minecraft spaceships and export them as Litematica schematic (`.litematic`) files.

Pick a seed, pick a block palette, get a ship you can paste into your world with the [Litematica mod](https://www.curseforge.com/minecraft/mc-mods/litematica).

## Pipeline

```
seed + params  →  3D voxel shape  →  role assignment  →  palette lookup  →  .litematic
                  (parts + mirror     (hull / window /    (YAML config)
                   symmetry)           engine / etc.)
```

## Features

- Parts-based procedural generation (hull, cockpit, engines, wings, greebles)
- Bilateral symmetry for recognisable ship silhouettes
- Seed-reproducible — same seed always produces the same ship
- 10 hull silhouettes, 9 engine styles, 6 wing silhouettes (see [Styles](#styles))
- Greeble library — 6 surface-detail types (turret, dish, vent, antenna, panel line, sensor pod)
- 40 block palettes spanning sci-fi, industrial, biome, and novelty themes
- CLI + Flask web UI with isometric preview, sci-fi console theme, light/dark toggle, keyboard shortcuts
- `.litematic` output loads directly in the Litematica mod
- Property-based tests and CI on Python 3.11/3.12/3.13 across Ubuntu + Windows

## Requirements

- Python 3.11+
- Minecraft Java Edition 1.20+ with the Litematica mod installed (for loading the output)

## Install

```bash
git clone https://github.com/KazooKat/Spaceship-Generator.git
cd Spaceship-Generator
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e .
```

For development:

```bash
pip install -e .[dev]
pytest
```

## Usage — CLI

```bash
spaceship-generator --seed 42 --palette sci_fi_industrial \
    --length 40 --width 20 --height 12 --out ./out
```

### Key flags

- `--preset <role>` — apply a named archetype (corvette, scout, battlecruiser, …); run `--list-presets` to list all
- `--repeat N` — generate N ships with consecutive seeds
- `--seeds A,B,C` or `--seeds A-Z` — generate from a list or range of seeds
- `--palette random` — pick a random palette at generation time
- `--output-json` — emit NDJSON summary per ship to stdout
- `--block-summary` — print block-count CSV for survival resource planning
- `--preview-azimuth DEG` / `--preview-elevation DEG` — control isometric camera angle
- `--fleet-count N` — generate a coherent fleet of N ships
- `--ship-size WxHxL` — override ship dimensions (width × height × length); validates W≥4, H≥4, L≥8
- `--seed-phrase TEXT` — hash memorable text to a deterministic seed (SHA-256)
- `--export-manifest` — write `<name>.json` sidecar alongside each .litematic
- `--palette-info NAME` — print role → block ID and hex preview color for a palette

Output: `out/ship_42.litematic`.

Load it in Minecraft:

1. Copy the file into `.minecraft/schematics/` (or wherever Litematica is configured to look).
2. In-game, open Litematica's `Load Schematic` menu and place the ship.

## Usage — Web UI

```bash
flask --app spaceship_generator.web.app run
```

Open `http://127.0.0.1:5000`, fill in the form, and download your ship. The UI ships with a sci-fi console theme, a light/dark toggle, and keyboard shortcuts for generate / randomize.

## Styles

Three independent dials shape the silhouette. Mix and match freely.

**HullStyle** — hull-only profile + X/Y scaling.

- `arrow` — long pointed front, chunky rear
- `saucer` — wide flat disc, squashed Y
- `whale` — fat rounded body, peak volume mid-ship
- `dagger` — narrow slim blade, tapered both ends
- `blocky_freighter` — boxy crate silhouette
- `organic_bio` — rounded organic curves, puffy and wide
- `hexagonal_lattice` — rippled hex-cell profile
- `asymmetric_scavenger` — lopsided scavenged-parts look
- `modular_block` — stepped rectangular modules
- `sleek_racing` — narrow needle silhouette, low height

**EngineStyle** — rear-engine archetype.

- `single_core` — one large central thruster
- `twin_nacelle` — two side nacelles, classic sci-fi
- `quad_cluster` — four small engines in a 2×2
- `ring` — hollow annular torus thruster
- `ion_array` — horizontal row of small glow blocks
- `plasma_pulse` — alternating disk/annulus slabs, pulsed look
- `magnetic_rail` — two elongated rail bars offset vertically
- `bio_organic` — rng-seeded irregular blob clusters
- `retro_rocket_cluster` — triangle of three compact round nozzles

**WingStyle** — planform archetype.

- `straight` — rectangular slab (legacy default)
- `swept` — parallelogram, tip shifted rearward
- `delta` — triangular planform
- `tapered` — straight leading edge, chord shrinks outboard
- `gull` — stepped dihedral, outer section rises
- `split` — two thinner wings stacked biplane-style

## Palettes

Palettes live in `palettes/*.yaml`. Each palette maps semantic roles (e.g. `HULL`, `WINDOW`, `ENGINE_GLOW`) to Minecraft block IDs. Add a new palette by dropping a YAML file in that folder.

See [docs/palettes.md](docs/palettes.md) for the full catalog.

| | | |
|---|---|---|
| `abyss_deep` | `alien_bio` | `amethyst_crystal` |
| `ancient_ruin` | `autumn_harvest` | `badlands_mesa` |
| `biopunk_fungal` | `candy_pop` | `cherry_blossom` |
| `circus_bigtop` | `coral_reef` | `crimson_nether` |
| `cyberpunk_neon` | `deepslate_drone` | `desert_sandstone` |
| `diamond_tech` | `end_city` | `end_void` |
| `forest_camouflage` | `frozen_tundra` | `gold_imperial` |
| `ice_crystal` | `jungle_canopy` | `lava_forge` |
| `mushroom_islands` | `nebula_drift` | `neon_arcade` |
| `nordic_scout` | `prismarine_sea` | `quantum_chrome` |
| `rustic_salvage` | `sci_fi_industrial` | `sleek_modern` |
| `solar_flare` | `stealth_black` | `steampunk_brass` |
| `swamp_bog` | `void_walker` | `volcanic_ash` |
| `wooden_frigate` | | |

Example palette file:

```yaml
name: sci_fi_industrial
blocks:
  HULL:          minecraft:light_gray_concrete
  WINDOW:        minecraft:light_blue_stained_glass
  ENGINE_GLOW:   minecraft:sea_lantern
  # ...
preview_colors:
  HULL:          "#c0c0c0"
  WINDOW:        "#70b0ff"
  # ...
```

## Development

```bash
pytest                               # run tests (includes property tests)
ruff check .                         # lint
python scripts/bench.py              # perf benchmark
python scripts/render_gallery.py     # regenerate palette/style gallery
```

See [docs/](docs/) for architecture notes, release notes ([docs/release.md](docs/release.md)), and deeper design docs.

## License

MIT — see [LICENSE](LICENSE).

This project depends on [litemapy](https://github.com/SmylerMC/litemapy) (GPL-3.0) at runtime. Using a GPL library as a pip dependency does not force the dependent project to be GPL, but if you redistribute a bundle containing litemapy the GPL terms apply to that bundle.
