# Palette Authoring Guide

A *palette* maps the generator's 10 semantic roles (HULL, WINDOW, ENGINE_GLOW, …) to real Minecraft block IDs and a preview color per role. Palettes are plain YAML files under `palettes/` and are auto-discovered — drop a new file in and it shows up in the CLI (`--list-palettes`) and the web UI dropdown without any code changes.

## Schema

Top-level keys (`src/spaceship_generator/palette.py`):

| Key              | Required | Type            | Notes                                                                  |
| ---------------- | -------- | --------------- | ---------------------------------------------------------------------- |
| `name`           | yes      | string          | Display name. By convention, matches the filename stem.                |
| `description`    | no       | string          | One-line blurb. Shown in UI tooltips / listings. Strongly recommended. |
| `blocks`         | yes      | mapping         | Role → Minecraft block-state string. All 10 roles required.            |
| `preview_colors` | no\*     | mapping         | Role → color. Missing roles fall back to mid-gray, but the linter warns — always provide. |

\* Technically optional at the parser level, but `validate_palette_file()` flags missing entries and the shipped test suite (`test_validate_builtin_palettes_clean`) requires zero warnings for every palette in the directory.

Any key outside `{name, description, blocks, preview_colors}` triggers an `unknown top-level key` lint warning.

### `blocks` format

Each value is a Minecraft block-state string: `minecraft:<id>` optionally followed by `[prop=val,prop=val,...]`.

```yaml
blocks:
  HULL:          minecraft:light_gray_concrete
  LIGHT:         minecraft:redstone_lamp[lit=true]
  ENGINE_GLOW:   minecraft:sea_lantern
```

Only real 1.20+ block IDs survive export. The palette loader validates the *syntax* of the string; invalid block IDs are only detected when Minecraft/Litematica loads the file.

### `preview_colors` format

Either `"#rrggbb"` / `"#rrggbbaa"` hex strings or 3/4-element float lists (`[r, g, b]` or `[r, g, b, a]` with values in 0..1).

```yaml
preview_colors:
  HULL:          "#c0c0c0"
  ENGINE_GLOW:   [0.94, 0.88, 0.38]
```

These feed the 3D preview renderer when the live-texture mode is off or offline.

## The 10 Roles

Every palette must define all 10 (order doesn't matter). Leaving one out raises `ValueError: Palette 'X' missing block roles: [...]`.

| Role            | What it represents                                                                           | Typical block choices                            |
| --------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `HULL`          | Primary exterior plating — the dominant surface color.                                       | concrete, planks, copper, prismarine             |
| `HULL_DARK`     | Secondary plating used for stripes/accents by the texture pass. Should contrast with `HULL`. | dark concrete, hyphae, smooth basalt             |
| `WINDOW`        | Side viewport glass. Often stained glass; slime/ice work for stylized looks.                 | `*_stained_glass`, slime_block, ice              |
| `ENGINE`        | Engine nacelle body around the glow core. Usually dense, inert-looking.                      | polished_blackstone, magma_block, nether_bricks  |
| `ENGINE_GLOW`   | The hot thruster face. Almost always a light-emitting block.                                 | sea_lantern, shroomlight, glowstone, froglights  |
| `COCKPIT_GLASS` | The frontal canopy. Distinct from `WINDOW` so the cockpit can be tinted differently.         | tinted_glass, colored stained glass              |
| `WING`          | Wing surface blocks. Often a lighter/shinier variant of `HULL`.                              | iron_block, glazed_terracotta, calcite           |
| `GREEBLE`       | Small surface detail sprinkled onto the hull by the greeble pass.                            | polished_andesite, nylium, nether_bricks         |
| `LIGHT`         | Running lights (wingtips, spine). Expected to read as "on" — prefer lit/emissive blocks.     | redstone_lamp[lit=true], glowstone, soul_lantern |
| `INTERIOR`      | Infill for internal voxels (rarely seen externally). Any neutral block is fine.              | smooth_stone, black_wool, warped_planks          |

The source of truth is the `Role` enum in `src/spaceship_generator/palette.py` — `EMPTY` (value 0) is *not* a palette role, it represents "no block".

## Picking harmonious preview colors

The preview colors don't have to be photorealistic — they're stylized swatches. A few rules that work:

1. **Anchor on the block's real vanilla color.** Peek at `src/spaceship_generator/data/block_colors.json` (machine-sampled averages from the `misode/mcmeta` asset mirror). Those values are the exact tones the live-texture preview renders, so matching them in `preview_colors` keeps the stylized mode visually consistent.
2. **Contrast `HULL` vs `HULL_DARK`.** The texture pass stripes `HULL_DARK` across `HULL` — if they're the same lightness, the banding vanishes. Aim for at least a 25–40% luminosity delta.
3. **Make `ENGINE_GLOW` and `LIGHT` pop.** These are emissive by convention. Saturated warm (orange/yellow) or cool (cyan/white) hues read as "hot" against a muted hull.
4. **Don't neon-stack everything.** If `HULL` is saturated, keep `GREEBLE` and `WING` muted, otherwise the silhouette gets lost.
5. **`COCKPIT_GLASS` should read as tinted glass**, not as a separate material — darken the window color by ~30% and nudge hue slightly.

When in doubt, eyeball the shipped palettes (`sci_fi_industrial.yaml`, `amethyst_crystal.yaml`, `crimson_nether.yaml`) — they span a wide range of hue/contrast combos.

Additional reference palettes added in the themed batch:

| File | Theme | Distinguishing technique |
|------|-------|--------------------------|
| `void_walker.yaml` | Deep-space dark | Near-black obsidian hull; `crying_obsidian` greebles for purple flecks; `end_rod` glow reads as cold white |
| `lava_forge.yaml` | Volcanic | `magma_block` ENGINE + `shroomlight` glow; warm amber `ENGINE_GLOW`/`LIGHT` contrast sharply against near-black hull |
| `forest_camouflage.yaml` | Woodland recon | Earthy greens/browns; `ochre_froglight` ENGINE_GLOW adds warm accent without being neon |
| `quantum_chrome.yaml` | Iridescent silver | White quartz hull vs pale `smooth_quartz` HULL_DARK keeps a subtle sheen; `prismarine` WINDOW adds the iridescent teal pop |
| `ancient_ruin.yaml` | Weathered stone | Cracked/mossy stone variants; `soul_lantern` dual-use for ENGINE_GLOW and LIGHT gives a haunting teal cast |

## Schema tips and common patterns

### Reusing a block across roles

The schema does **not** require unique blocks per role. If your theme calls for it, the same block ID may appear in multiple roles (e.g. `ancient_ruin.yaml` uses `minecraft:soul_lantern` for both `ENGINE_GLOW` and `LIGHT`). The validator does not warn on this.

### Dual-use emissive blocks

Blocks like `sea_lantern`, `shroomlight`, `soul_lantern`, `ochre_froglight`, `verdant_froglight`, and `pearlescent_froglight` are all light-emitting and look good for `ENGINE_GLOW`, `LIGHT`, or even `ENGINE`. Pick based on color temperature:

| Block | Approximate color | Good for |
|-------|-------------------|----------|
| `sea_lantern` | Cool cyan-white | sci-fi `LIGHT`, chrome `ENGINE_GLOW` |
| `shroomlight` | Warm amber | volcanic, nether `ENGINE_GLOW` |
| `soul_lantern` | Teal/mint | horror, void, ruin themes |
| `ochre_froglight` | Golden yellow | woodland, earthy `ENGINE_GLOW` |
| `pearlescent_froglight` | Soft purple | arcane, crystal themes |
| `verdant_froglight` | Soft green | biopunk, alien themes |
| `glowstone` | Warm white | classic sci-fi, gold themes |

### Block-state strings

Append `[prop=val]` only when the game requires it for the visual you want. Most blocks don't need it. The one common exception is `minecraft:redstone_lamp[lit=true]` — without `[lit=true]` the lamp renders unlit.

## Minimal example

```yaml
name: my_palette
description: Short one-line description shown in UI tooltips.

blocks:
  HULL:          minecraft:white_concrete
  HULL_DARK:     minecraft:gray_concrete
  WINDOW:        minecraft:light_blue_stained_glass
  ENGINE:        minecraft:polished_blackstone
  ENGINE_GLOW:   minecraft:sea_lantern
  COCKPIT_GLASS: minecraft:tinted_glass
  WING:          minecraft:iron_block
  GREEBLE:       minecraft:polished_andesite
  LIGHT:         minecraft:redstone_lamp[lit=true]
  INTERIOR:      minecraft:smooth_stone

preview_colors:
  HULL:          "#e6e6e6"
  HULL_DARK:     "#6a6a6a"
  WINDOW:        "#70b0ff"
  ENGINE:        "#353038"
  ENGINE_GLOW:   "#acc8be"
  COCKPIT_GLASS: "#3a2a5a"
  WING:          "#dcdcdc"
  GREEBLE:       "#9a9a9a"
  LIGHT:         "#8e653c"
  INTERIOR:      "#b0b0b0"
```

## Testing a new palette

Drop the file in `palettes/` then run any of:

### 1. Programmatic load

```bash
.venv/Scripts/python -c "from spaceship_generator.palette import load_palette; load_palette('my_palette')"
```

This exercises `Palette.load()` and will raise on missing roles or malformed block states.

### 2. Lint with the validator

```bash
.venv/Scripts/python -c "from spaceship_generator.palette import validate_palette_file, palettes_dir; print(validate_palette_file(palettes_dir() / 'my_palette.yaml'))"
```

An empty list means clean. Any warning must be resolved — `test_validate_builtin_palettes_clean` enforces this for every shipped palette.

### 3. CLI end-to-end

```bash
.venv/Scripts/python -m spaceship_generator --list-palettes
.venv/Scripts/python -m spaceship_generator --seed 42 --palette my_palette --preview --out out/
```

The `--preview` flag renders a PNG using the palette's `preview_colors` (or live textures if network is available).

### 4. Web UI

```bash
.venv/Scripts/python -m flask --app spaceship_generator.web.app run
```

Open the shown URL, expand **Palette**, and your new palette appears in the dropdown. Hit **Generate** and confirm the 3D preview looks right.

### 5. Pytest suite

```bash
.venv/Scripts/python -m pytest tests/test_palette.py
```

New palettes in `palettes/` automatically get covered by:
- `test_validate_builtin_palettes_clean` — zero lint warnings.
- `test_generate_palette_x_structure_style_cross` — generates with every `StructureStyle`.

If you want a new palette covered by the textured-generation check (`test_new_palette_textures_all_fine_roles`), add its name to the `NEW_PALETTES` tuple at the top of `tests/test_palette.py`.
