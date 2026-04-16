# Spaceship Generator

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
- Multiple block palettes: `sci_fi_industrial`, `sleek_modern`, `rustic_salvage`
- Seed-reproducible — same seed always produces the same ship
- CLI + Flask web UI with isometric preview
- `.litematic` output loads directly in the Litematica mod

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

Output: `out/ship_42.litematic`.

Load it in Minecraft:

1. Copy the file into `.minecraft/schematics/` (or wherever Litematica is configured to look).
2. In-game, open Litematica's `Load Schematic` menu and place the ship.

## Usage — Web UI

```bash
flask --app spaceship_generator.web.app run
```

Open `http://127.0.0.1:5000`, fill in the form, and download your ship.

## Palettes

Palettes live in `palettes/*.yaml`. Each palette maps semantic roles (e.g. `HULL`, `WINDOW`, `ENGINE_GLOW`) to Minecraft block IDs. Add a new palette by dropping a YAML file in that folder.

Example:

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

## License

MIT — see [LICENSE](LICENSE).

This project depends on [litemapy](https://github.com/SmylerMC/litemapy) (GPL-3.0) at runtime. Using a GPL library as a pip dependency does not force the dependent project to be GPL, but if you redistribute a bundle containing litemapy the GPL terms apply to that bundle.
