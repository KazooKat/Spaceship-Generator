# Glossary

Definitions for recurring project terms. Cross-link to per-doc deep dives.

## `--config-dump`

CLI flag in `src/spaceship_generator/__main__.py` emitting the
preset-resolved args that WOULD be passed into `generate()` as
`{"effective_config":{...}}`, then exits 0 without producing a ship.
See [cli.md — Effective config dump](cli.md#effective-config-dump).

## `--from-manifest`

CLI flag in `src/spaceship_generator/__main__.py` reproducing a prior
run byte-identically from a `<name>.json` sidecar written by
`--export-manifest` (mutex with seed/repeat/fleet flags); sibling of
`--config-dump`. See [configuration.md — Determinism / seeding](configuration.md#determinism--seeding).

## `--meta-json`

CLI flag in `src/spaceship_generator/__main__.py` emitting a single
combined JSON document with every per-enum / palette / preset / version
payload — CLI mirror of the `/api/meta` web endpoint. See [cli.md — Machine-readable list / output flags](cli.md#machine-readable-list--output-flags).

## `--version-json`

CLI flag in `src/spaceship_generator/__main__.py` — machine-readable
sibling of `--version` emitting `{"version": __version__}` from
`spaceship_generator.__version__`. See [cli.md — Machine-readable list / output flags](cli.md#machine-readable-list--output-flags).

## `.litematic`

The primary output artifact — a gzipped NBT schematic file used by the
Litematica Minecraft mod to paste a 3D region of block states into the
world. Spaceship Generator writes one `.litematic` per ship via
`export.py::export_litematic`. See
[output-formats.md](output-formats.md#litematic-schematic) for the full
file-shape reference.

## `/api/version`

Read-only Flask endpoint in `src/spaceship_generator/web/blueprints/ship.py`
returning `{"version":"<X.Y.Z>"}` — narrower JSON sibling of
`/api/health` / `/api/meta` for about-box dialogs and deploy probes.
See [web_ui.md — Discovery & metadata](web_ui.md#discovery--metadata).

## biome pack catalog

The `## Biome packs` section in `docs/palettes.md` cataloging the
2-palette biome-themed pack series — reader-facing companion to the
`biome palette pack` process pattern. See [palettes.md — Biome packs](palettes.md#biome-packs).

## biome palette pack

Process pattern: a periodically-shipped pair of themed palette YAMLs
under `palettes/` landed in one `feat-palettes-biome-pack-<date>` cycle,
both passing `palette_lint.py --strict`. See [palette_authoring.md](palette_authoring.md).

## `CockpitStyle`

`StrEnum` declared in `src/spaceship_generator/shape/core.py` — picks the
forward-upper canopy archetype: `bubble`, `pointed`, `integrated`,
`canopy_dome`, `wrap_bridge`, or `offset_turret`. It is a field on
`ShapeParams` and the sole input that picks which placer
`shape/cockpit.py::_place_cockpit` dispatches to. See
[architecture.md — Cockpit pipeline](architecture.md#cockpit-pipeline)
and CLI flag [`--cockpit-style`](cli.md#shape-parameters).

## Common pitfalls

Five mistakes new palette authors hit most often (missing `minecraft:`
namespace, role-name typo, non-existent block id, YAML quoting slips,
non-cube in solid-cube role). See [palette_authoring.md](palette_authoring.md#common-pitfalls).

## Consumer examples

Two copy-paste snippets showing how a downstream tool reads a generated
ship — a Python `litemapy` block counting `.litematic` blocks, and a
shell `--output-json | jq` one-liner. See [output-formats.md — Consumer examples](output-formats.md#consumer-examples).

## cross-axis property test

Pytest parametrize-grid test in `tests/test_properties.py` pinning two
ship-axis dials together (e.g. `cockpit_style × hull_style × seed`) for
27 nodes, catching interaction-only regressions. See [faq.md](faq.md#why-do-cross-axis-property-tests-exist-alongside-single-axis-ones).

## cross-axis test (extension)

Process pattern: extending the cross-axis property test family in
`tests/test_properties.py` with a new (axis × axis × seed) 3 × 3 × 3
grid (27 nodes). See [recipes.md — Recipe 26](recipes.md).

## cross-link footer (architecture.md)

Trailing `## Cross-link index` table in `docs/architecture.md` mapping
each pipeline section to its CLI flag(s) + web API endpoint(s). See
[architecture.md — Cross-link index](architecture.md#cross-link-index).

## `EngineStyle`

`StrEnum` in `src/spaceship_generator/engine_styles.py` — picks the
rear-engine archetype (`single_core`, `twin_nacelle`, `quad_cluster`,
`ring`, `ion_array`, `plasma_pulse`, `magnetic_rail`, `bio_organic`,
`retro_rocket_cluster`). Keyword-only on `generator.generate(...)`; the
CLI exposes it via [`--engine-style`](cli.md#shape-parameters) and the
web API via [`GET /api/engine-styles`](web_ui.md#json-api-api).

## Fleet pipeline

Batch ship-build driver in `src/spaceship_generator/fleet.py` —
`generate_fleet(FleetParams)` plans per-ship seed/dims/styles
deterministically (CLI: `--fleet-count > 1`). See [architecture.md — Fleet pipeline](architecture.md#fleet-pipeline).

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

## hull × wing cross-axis property test

Pytest parametrize-grid test in `tests/test_properties.py` pinning
(`HullStyle` × `WingStyle` × seed) for 27 nodes — catches hull-silhouette
× wing-planform interaction regressions that single-axis siblings miss. See [faq.md](faq.md#why-do-cross-axis-property-tests-exist-alongside-single-axis-ones).

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

## palette × hull cross-axis test

Pytest parametrize-grid test in `tests/test_properties.py` pinning
(palette × `HullStyle` × seed) for 27 nodes — catches palette × hull
interaction regressions. Sibling of `hull × wing cross-axis property test`. See [faq.md](faq.md#why-do-cross-axis-property-tests-exist-alongside-single-axis-ones).

## palette_lint JSON schema

Per-palette object emitted by `scripts/palette_lint.py --json` —
`{"palette": "<name>", "ok": true|false, "errors": [...], "warnings": [...]}`.
`--all --json` emits an array of these. CI gates branch on
`jq -r '.[].ok'`. See [recipes.md — Recipe 23](recipes.md).

## `palette_diff.py`

Authoring helper in `scripts/palette_diff.py` printing a role-by-role
block diff between two palette YAMLs (also `--csv`); one-sided roles
surface as `<missing>`. See [recipes.md — Recipe 11](recipes.md#recipe-11--diff-two-palettes).

## `palette_merge.py`

Authoring helper in `scripts/palette_merge.py` that merges two palette
YAML files into a third via `--out` per `--strategy` (`prefer-a` /
`prefer-b` / `prefer-defined`) for role-conflict resolution. See
[recipes.md](recipes.md).

## `palette_search.py`

Authoring helper in `scripts/palette_search.py` walking every
`palettes/*.yaml` and printing one `(palette, role)` pair per match for
a target block id (also `--csv`). See [recipes.md — Recipe 15](recipes.md#recipe-15--find-every-palette-referencing-a-minecraft-block-id).

## `palette_stats.py`

Authoring helper in `scripts/palette_stats.py` printing cross-corpus
palette stats — palette count, block-ID frequency across roles, most
common block per role (also `--csv`, `--top N`). See
[recipes.md — Recipe 12](recipes.md#recipe-12--audit-my-palette-corpus).

## preset

A named ship archetype (e.g. `corvette`, `scout`, `battlecruiser`,
`capital_carrier`) declared in `presets.py` that pins a specific
combination of hull / engine / wing / cockpit style, dimensions,
greeble density, and weapon settings. Individual style flags override
preset values when explicitly set. See CLI flag
[`--preset`](cli.md#presets) and the web endpoint
[`GET /api/presets`](web_ui.md#json-api-api).

## Reading the output

Bench-output semantics for the wall-clock `bench_*.py` family — per-row
`mean_ms` is the arithmetic mean of per-iteration timings, `p95_ms` the
95th percentile, and the final `TOTAL` row aggregates across every
per-row sample pool (NOT a sum of per-row means). See [bench.md — Reading the output](bench.md#reading-the-output).

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

## Structure pipeline

Assembly pipeline rooted at `StructureStyle` — the *coarsest* dial
scaling every later stage (hull profile, engine count, wing probability,
cockpit default). See [architecture.md — Structure pipeline](architecture.md#structure-pipeline).

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

## web UI presets drawer

Client-side modal in `src/spaceship_generator/web/static/presets.js`
(topbar `#btn-presets`, shortcut `P`) saving form snapshots to
`localStorage["shipforge.presets.v1"]` — independent of the server-side `<select name="preset">` picker. See [web_ui.md — Picking a palette and preset](web_ui.md#picking-a-palette-and-preset).

## `WingStyle`

`StrEnum` in `src/spaceship_generator/wing_styles.py` — picks the wing
planform (`straight`, `swept`, `delta`, `tapered`, `gull`, `split`).
Field on `ShapeParams`; `straight` reproduces legacy byte-for-byte
output. See [architecture.md — Wing pipeline](architecture.md#wing-pipeline)
and CLI flag [`--wing-style`](cli.md#shape-parameters).

See also: `docs/cli.md`, `docs/web_ui.md`, `docs/configuration.md`, `docs/architecture.md`, `docs/output-formats.md`, `docs/recipes.md`.
