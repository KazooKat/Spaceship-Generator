# Glossary

Definitions for recurring project terms. Cross-link to per-doc deep dives.

## `.litematic`

The primary output artifact — a gzipped NBT schematic file used by the
Litematica Minecraft mod to paste a 3D region of block states into the
world. Spaceship Generator writes one `.litematic` per ship via
`export.py::export_litematic`. See
[output-formats.md](output-formats.md#litematic-schematic) for the full
file-shape reference.

## `CockpitStyle`

`StrEnum` declared in `src/spaceship_generator/shape/core.py` — picks the
forward-upper canopy archetype: `bubble`, `pointed`, `integrated`,
`canopy_dome`, `wrap_bridge`, or `offset_turret`. It is a field on
`ShapeParams` and the sole input that picks which placer
`shape/cockpit.py::_place_cockpit` dispatches to. See
[architecture.md — Cockpit pipeline](architecture.md#cockpit-pipeline)
and CLI flag [`--cockpit-style`](cli.md#shape-parameters).

## `EngineStyle`

`StrEnum` in `src/spaceship_generator/engine_styles.py` — picks the
rear-engine archetype (`single_core`, `twin_nacelle`, `quad_cluster`,
`ring`, `ion_array`, `plasma_pulse`, `magnetic_rail`, `bio_organic`,
`retro_rocket_cluster`). Keyword-only on `generator.generate(...)`; the
CLI exposes it via [`--engine-style`](cli.md#shape-parameters) and the
web API via [`GET /api/engine-styles`](web_ui.md#json-api-api).

## `gen_id`

12-character hex token (`uuid4().hex[:12]`) returned by
`POST /api/generate` and `POST /generate`. It keys the in-memory LRU
cache that holds a generated ship's role grid + `.litematic` path on the
running Flask app, and is the path component of `/result/<gen_id>`,
`/download/<gen_id>`, `/preview/<gen_id>.png`, and `/voxels/<gen_id>.json`.
See [output-formats.md — Web API JSON response](output-formats.md#web-api-json-response-apigenerate).

## `GreebleType`

`StrEnum` in `src/spaceship_generator/greeble_styles.py` — names the
multi-cell surface-detail archetypes (`turret`, `dish`, `vent`,
`antenna`, `panel_line`, `sensor_pod`, `circuit_board`, `battle_damage`,
`pipe_cluster`, `organic_growth`, `nano_mesh`). Used as the optional
allow-list passed to `scatter_greebles`. See
[architecture.md — Greeble pipeline](architecture.md#greeble-pipeline)
and CLI flag [`--greeble-style`](cli.md#shape-parameters).

## `HullStyle`

`StrEnum` declared in `src/spaceship_generator/structure_styles.py` —
picks the hull-membrane silhouette (`arrow`, `saucer`, `whale`,
`dagger`, `blocky_freighter`, `organic_bio`, `hexagonal_lattice`,
`asymmetric_scavenger`, `modular_block`, `sleek_racing`). It is a
keyword-only argument on `generate_shape` and `generator.generate`, not
a `ShapeParams` field. See
[architecture.md — Hull pipeline](architecture.md#hull-pipeline) and
CLI flag [`--hull-style`](cli.md#shape-parameters).

## palette

A YAML file in `palettes/<name>.yaml` mapping every required `Role`
(HULL, WINDOW, ENGINE_GLOW, ...) to a Minecraft block-ID string and an
optional preview hex color. Loaded into a `Palette` dataclass by
`palette.py::load_palette`. See
[configuration.md — Palette](configuration.md#palette) and the web
endpoint [`GET /api/palettes`](web_ui.md#json-api-api).

## preset

A named ship archetype (e.g. `corvette`, `scout`, `battlecruiser`,
`capital_carrier`) declared in `presets.py` that pins a specific
combination of hull / engine / wing / cockpit style, dimensions,
greeble density, and weapon settings. Individual style flags override
preset values when explicitly set. See CLI flag
[`--preset`](cli.md#presets) and the web endpoint
[`GET /api/presets`](web_ui.md#json-api-api).

## `Role`

`IntEnum` in `src/spaceship_generator/palette.py` (`EMPTY=0`, `HULL`,
`HULL_DARK`, `WINDOW`, `ENGINE`, `ENGINE_GLOW`, `COCKPIT_GLASS`, `WING`,
`GREEBLE`, `LIGHT`, `INTERIOR`) — the semantic per-voxel classification
stored as `int8` in the role grid. Every non-EMPTY member must be
present in every palette. See
[architecture.md — Key data contracts](architecture.md#key-data-contracts)
and the web endpoint [`GET /api/roles`](web_ui.md#json-api-api).

## `ShapeParams`

The user-tunable shape dataclass in
`src/spaceship_generator/shape/core.py` that carries `length`,
`width_max`, `height_max`, `engine_count`, `wing_prob`,
`greeble_density`, `cockpit_style`, `structure_style`, `wing_style`, and
`hull_noise`. Validates eagerly in `__post_init__`. See
[configuration.md — Shape](configuration.md#shape) and
[architecture.md — Key data contracts](architecture.md#key-data-contracts).

## `StructureStyle`

`StrEnum` in `src/spaceship_generator/structure_styles.py` — the
top-level ship archetype (`frigate`, `fighter`, `dreadnought`, `shuttle`,
`hammerhead`, `carrier`) that drives wing-prob overrides, engine-count
overrides, and the legacy hull profile. Field on `ShapeParams`. See
CLI flag [`--structure-style`](cli.md#shape-parameters) and the web
endpoint [`GET /api/structure-styles`](web_ui.md#json-api-api).

## `WeaponType`

`StrEnum` in `src/spaceship_generator/weapon_styles.py` — names the
top-facing weapon archetypes (`turret_large`, `missile_pod`,
`laser_lance`, `point_defense`, `plasma_core`). Used as the optional
allow-list passed to `scatter_weapons`. See
[architecture.md — Weapon pipeline](architecture.md#weapon-pipeline)
and CLI flag [`--weapon-types`](cli.md#weapons).

## `WingStyle`

`StrEnum` in `src/spaceship_generator/wing_styles.py` — picks the wing
planform (`straight`, `swept`, `delta`, `tapered`, `gull`, `split`).
Field on `ShapeParams`; `straight` reproduces legacy byte-for-byte
output. See [architecture.md — Wing pipeline](architecture.md#wing-pipeline)
and CLI flag [`--wing-style`](cli.md#shape-parameters).

See also: `docs/cli.md`, `docs/web_ui.md`, `docs/configuration.md`, `docs/architecture.md`, `docs/output-formats.md`, `docs/recipes.md`.
