# Architecture Overview

## Overview

Spaceship Generator turns an integer seed plus a handful of tunable knobs into
a procedurally built Minecraft spaceship, serialized as a `.litematic` schematic
with an optional isometric PNG preview. The pipeline is one-way:
**seed + `ShapeParams` → coarse voxel shape → optional parts (engines,
greebles, weapons) → role refinement via `TextureParams` → palette-driven
block assignment → `.litematic` on disk (+ optional preview PNG)**. Every stage
is deterministic given its inputs, so the same seed + params reproduce the
same ship byte-for-byte.

## Module map

```mermaid
flowchart LR
  cli[cli.py]
  gen[generator.py]
  fleet[fleet.py]
  preview[preview.py]
  export[export.py]
  texture[texture.py]
  palette[palette.py]
  block_colors[block_colors.py]

  subgraph style_libs[Style libraries]
    engine_styles[engine_styles.py]
    greeble_styles[greeble_styles.py]
    weapon_styles[weapon_styles.py]
    structure_styles[structure_styles.py]
    wing_styles[wing_styles.py]
  end

  subgraph shape_pkg[shape/]
    shape_core[core.py]
    shape_hull[hull.py]
    shape_cockpit[cockpit.py]
    shape_engines[engines.py]
    shape_wings[wings.py]
    shape_greebles[greebles.py]
    shape_assembly[assembly.py]
  end

  subgraph web_pkg[web/]
    web_app[app.py]
    bp_ship[blueprints/ship.py]
    bp_support[blueprints/ship_support.py]
    bp_static[blueprints/static_ext.py]
    bp_rate[blueprints/ratelimit.py]
    bp_errors[blueprints/errors.py]
  end

  cli --> gen
  cli --> fleet
  cli --> style_libs
  cli --> shape_pkg
  cli --> texture
  cli --> palette

  gen --> shape_pkg
  gen --> style_libs
  gen --> texture
  gen --> palette
  gen --> export
  gen --> preview

  shape_core --> structure_styles
  shape_core --> wing_styles
  shape_hull --> structure_styles
  shape_cockpit --> structure_styles
  shape_engines --> structure_styles
  shape_wings --> structure_styles
  shape_wings --> wing_styles
  shape_pkg --> palette
  shape_assembly --> palette

  texture --> palette
  texture --> shape_pkg
  export --> palette
  preview --> palette
  style_libs --> palette
  fleet --> structure_styles
  fleet --> engine_styles
  fleet --> wing_styles

  web_app --> bp_ship
  web_app --> bp_static
  web_app --> bp_rate
  web_app --> bp_errors
  bp_ship --> bp_support
  bp_ship --> gen
  bp_ship --> shape_pkg
  bp_ship --> texture
  bp_ship --> palette
  bp_ship --> style_libs
  bp_ship --> block_colors
  bp_support --> preview
  bp_support --> palette
  bp_static --> block_colors
```

## Bounded contexts

- **`shape/` (voxel geometry).** Builds a `(W, H, L)` int8 grid of coarse
  roles (`HULL`, `COCKPIT_GLASS`, `ENGINE`, `WING`, `GREEBLE`). Split into
  `core` (orchestrator + `ShapeParams`/`CockpitStyle`), `hull`, `cockpit`,
  `engines`, `wings`, `greebles`, and `assembly` (X-mirror +
  connected-component floater bridging).
- **`palette` (block/role mapping).** Defines the `Role` IntEnum and the
  `Palette` dataclass that maps roles to `litemapy.BlockState`s and RGBA
  preview colors. Loads + validates YAML palettes from the repo-level
  `palettes/` directory.
- **`texture` (role painting).** Refines the coarse shape grid: interior
  fill, windows, accent stripes, panel bands, hull noise, rivets, engine
  glow, wing-tip / belly / nose-tip lights. Every pass is deterministic in
  cell coordinates.
- **`export` (.litematic serialization).** `export_litematic` pre-seeds the
  `litemapy.Region` palette in first-encounter order, then vectorizes the
  role-to-palette-index write through a LUT — bypasses litemapy's
  per-write palette scan.
- **`preview` (isometric PNG).** Matplotlib `Agg` voxel renderer with
  optional specular top-face boost, antialiased 2x downsample, and a solid
  or transparent backdrop. Exposed via `render_preview`.
- **`web/` (Flask blueprints).** `create_app()` in `app.py` composes four
  blueprints: `ship` (generate/result/preview/voxels/JSON API),
  `static_ext` (cached block-texture PNGs + `.litematic` downloads),
  `ratelimit` (per-IP fixed-window, loopback-exempt), and `errors`
  (JSON-aware 404). `ship_support` holds shared helpers and the LRU store.
- **`cli` (argparse entrypoint).** `python -m spaceship_generator` /
  `spaceship-generator`. Wires flags to `generator.generate`, supports
  `--seeds` bulk mode and `--fleet-count > 1` fleet mode, gracefully
  degrading when `weapon_styles` or `fleet` fail to import.
- **`fleet` (planning, no generation).** Pure parameter planner: given
  `FleetParams`, returns `list[GeneratedShip]` with per-ship seed, dims,
  hull/engine/wing styles, greeble density, and palette. Callers feed each
  `GeneratedShip` back through `generator.generate`.

## Key data contracts

- **`Role` (IntEnum, `palette.py`).** `EMPTY=0, HULL, HULL_DARK, WINDOW,
  ENGINE, ENGINE_GLOW, COCKPIT_GLASS, WING, GREEBLE, LIGHT, INTERIOR`. All
  non-EMPTY members are required in every palette.
- **`ShapeParams` (dataclass, `shape/core.py`).** `length, width_max,
  height_max, engine_count, wing_prob, greeble_density, cockpit_style,
  structure_style, wing_style`. Validates on construction.
- **`TextureParams` (dataclass, `texture.py`).** `window_period_cells,
  accent_stripe_period, engine_glow_depth, belly_light_period,
  nose_tip_light, hull_noise_ratio, panel_line_bands, rivet_period,
  engine_glow_ring`.
- **`Palette` (frozen dataclass, `palette.py`).** `name`, `blocks: dict[Role,
  BlockState]`, `preview_colors: dict[Role, RGBA]`. Loaded via
  `load_palette(name)` / `Palette.load(path)` / `Palette.from_dict`.
- **Style enums.** `HullStyle` (arrow, saucer, whale, dagger,
  blocky_freighter), `StructureStyle` (frigate, fighter, dreadnought,
  shuttle, hammerhead, carrier), `WingStyle` (straight, swept, delta,
  tapered, gull, split), `CockpitStyle` (bubble, pointed, integrated,
  canopy_dome, wrap_bridge, offset_turret), `EngineStyle` (single_core,
  twin_nacelle, quad_cluster, ring, ion_array), `WeaponType`
  (turret_large, missile_pod, laser_lance, point_defense, plasma_core),
  `GreebleType` (turret, dish, vent, antenna, panel_line, sensor_pod).
- **`GeneratedShip` (frozen dataclass, `fleet.py`).** `seed, dims,
  hull_style, engine_style, wing_style, greeble_density, palette`.
- **`FleetParams` (dataclass, `fleet.py`).** `count, palette, size_tier,
  style_coherence, seed`.

## Extension points

- **New palette.** Drop `<name>.yaml` under `palettes/` at the repo root
  with `name`, `blocks:` mapping every required role to a block-state
  string (`minecraft:foo` or `minecraft:foo[prop=val]`), and optional
  `preview_colors:`. `validate_palette_file` in `palette.py` is the
  reference linter; `list_palettes(include_errors=True)` surfaces it. See
  [palette_authoring.md](palette_authoring.md).
- **New style enum member.** Add the member to the enum, add a matching
  `_place_<name>` or `build_<name>` implementation, and register it in
  that module's dispatch table (`place_wings`, `build_engines`,
  `build_weapon`, `build_greeble`) or profile / scale maps (`_PROFILE_FNS`,
  `_HULL_PROFILE_FNS`, `_HULL_RX_RY_SCALES`). `--list-styles` and
  `/api/meta` enumerate the enum so new members surface automatically.
- **New cockpit variant.** Add a value to `CockpitStyle` in
  `shape/core.py`, implement `_place_<variant>` in `shape/cockpit.py`, and
  wire it into `_place_cockpit`'s dispatch. `--cockpit` / `--cockpit-style`
  and the web form's cockpit dropdown pick it up through
  `build_params_from_source`.

## Related documentation

- [faq.md](faq.md) — common questions and troubleshooting.
- [palette_authoring.md](palette_authoring.md) — palette YAML format.
- [performance.md](performance.md) — benchmark guide + vectorization notes.
- [release.md](release.md) — release checklist.
- [gallery.md](gallery.md) — curated seed + palette examples.
