# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- feat(shape): add `--hull-style-front`/`--hull-style-rear` flags — blend two `HullStyle` profiles along Z with a cosine-weighted crossover centred at z = L/2 over a 25% midband; both flags must be set to engage the blend (a partial pair silently falls back to the legacy single-style hull); when both are set the blend overrides `--hull-style`; new `apply_hull_blend()` library helper and `generate_shape(..., hull_style_front=, hull_style_rear=, hull_blend_midband=)` kwargs are deterministic per-seed (TODO: gallery sample render pending manual rendering tooling) (shapes-B)
- feat(palettes): add `lush_caves`, `mangrove_swamp`, `pale_garden` palettes — biome pack for Minecraft 1.18 lush caves (moss-block hull, azalea-leaves accent, verdant-froglight glow, glow-lichen lights), 1.19 mangrove swamp (mangrove-log hull, muddy-mangrove-roots accent, ochre-froglight glow), and 1.21 pale garden (pale-oak-log hull, pale-moss-block accent, creaking-heart engines, lantern glow)
- feat(api): add `GET /api/spec` endpoint — returns a hand-written OpenAPI 3.0.3 JSON document enumerating every `/api/*` route (paths, methods, summaries, query/path params, 200 response schemas) for client codegen and Swagger/Redoc browsers; version sourced from package metadata
- docs(architecture): document shape pipeline — new `## Shape pipeline` section in `docs/architecture.md` with a Mermaid build-order diagram (hull -> cockpit -> engines -> wings -> greebles -> mirror -> connect-floaters -> mirror) and one subsection per module in `src/spaceship_generator/shape/` (`core.py`, `hull.py`, `assembly.py`, `cockpit.py`, `wings.py`, `engines.py`, `greebles.py`); foundation for the `shapes-A`..`shapes-E` epic
- feat(cli): add `--from-manifest FILE` flag — reproduce a ship from a prior `--export-manifest` JSON sidecar; validates required keys (seed/palette/shape) and rejects conflicts with `--seed`/`--seeds`/`--seed-phrase`/`--repeat`/`--fleet-count`
- feat(api): add `GET /api/random` endpoint — returns a random `{seed, palette, preset}` JSON triple for client-side spin-the-wheel; optional `?seed=<int>` query param makes palette/preset selection reproducible; `Cache-Control: no-store`
- feat(cli): add `--no-greebles` shortcut — equivalent to `--greeble-density 0`; mutually exclusive with `--greeble-density` (errors with non-zero exit if both passed)
- feat(palettes): add `ancient_city` palette — deepslate-tile hull, cracked-deepslate accent, sculk-catalyst engine glow, soul-lantern running lights (deep dark biome / ancient city theme)
- feat(palettes): add `dripstone_cave` palette — dripstone-block hull, pointed-dripstone accent, copper-bulb warm engine glow, cut-copper engines, weathered-copper wings (Minecraft dripstone cave biome)
- test(cli): pin `--repeat N` produces exactly N distinct `.litematic` files with byte-distinct contents (4-ship distinctness property test, runs ~0.07s)
- fix(ci): commit 105 block-texture PNG cache files and add `.gitignore` exception — resolves `test_block_texture_png_returns_cached_bytes` and two related CI failures on all Python/OS matrix combinations
- feat(api): add `GET /api/styles` endpoint — returns `hull_styles`, `engine_styles`, `wing_styles`, `greeble_types`, `weapon_types` arrays for client-side discovery (parity with `/api/palettes` and `/api/presets`)
- feat(cli): add `--dry-run` flag — resolves and prints generation params (seed, palette, dims, preset) as JSON without writing files; exits 0
- feat(cli): add `--greeble-style TYPE` flag — restricts greeble scatter to one named `GreebleType` (turret/dish/vent/antenna/panel_line/sensor_pod); threads through `generate()` via new `greeble_types` param
- feat(palettes): add `badlands_mesa` palette — red terracotta hull, orange terracotta wings, copper block engine, ochre froglight glow (Minecraft badlands/mesa biome theme)
- feat(palettes): add `end_city` palette — purpur block hull, end stone brick accent, end rod glow (The End dimension / End City theme)
- docs(readme): update palette count (33→40), hull silhouette count (5→10), engine style count (5→9); add missing `--ship-size`, `--seed-phrase`, `--export-manifest`, `--palette-info` to key-flags table; expand Styles section with all current hull/engine variants

- fix(cli): replace `utcnow()` with timezone-aware `datetime.now(UTC)` in `--export-manifest` timestamp — eliminates DeprecationWarning on Python 3.12+
- fix(tests): add pytest `filterwarnings` entry to suppress known-harmless runpy `RuntimeWarning` in `test_cli_module_runpy_smoke`
- feat(palettes): add `mushroom_islands` palette — mycelium hull, red mushroom cap wings, shroomlight engine glow (mushroom island biome theme)
- feat(palettes): add `prismarine_sea` palette — prismarine-brick hull, dark prismarine underframe, sea-lantern engine glow (ocean monument theme)
- feat(cli): add `--ship-size WxHxL` flag — override ship dimensions at generation time; validates W>=4, H>=4, L>=8; overrides preset size
- feat(api): add `GET /api/compare` endpoint — accepts `seed_a`/`seed_b` plus optional `palette`/`preset`; returns both ships' dims, voxel count, and role counts side-by-side without generating files

- fix(cli): replace `→` with `->` in `--stats` help and `--seed-phrase` stderr output — fixes `UnicodeEncodeError` on Windows cp1252 terminals
- feat(cli): add `--palette-info <name>` flag — prints each role with its block ID and hex preview color for the named palette; exits 0 on success, 1 on unknown name
- feat(cli): add `--export-manifest` flag — writes a `<name>.json` sidecar alongside each generated `.litematic` containing seed, palette, shape, block count, and UTC timestamp
- feat(api): add `GET /api/fleet/plan` endpoint — returns JSON fleet metadata (count, size tier, coherence, per-ship seed/dims/styles) without generating any files; validates all five query params with 400 on bad input
- feat(palettes): add `jungle_canopy` palette — jungle log hull, mossy cobblestone underframe, ochre froglight engine glow, lime glass windows (tropical jungle theme)
- feat(palettes): add `swamp_bog` palette — mangrove log hull, mud underframe, verdant froglight engine glow, soul lantern running lights (dark swamp theme)

- feat(web): add seed-phrase text input to web form — type a phrase to get a deterministic seed (SHA-256, same algorithm as `--seed-phrase`); overrides the numeric seed field
- feat(api): add `GET /api/presets/<name>` endpoint — returns full single-preset detail (symmetry with `/api/palettes/<name>`); 404 on unknown name
- feat(cli): add `--list-weapon-types` flag — prints all 5 weapon type names with 2-space indent; completes the `--list-*` discovery family alongside `--list-palettes`, `--list-styles`, `--list-presets`

- feat(presets): add `description` field to all 9 ship archetypes — shown in `--list-presets` output and `/api/presets` JSON response
- feat(api): add `GET /api/palettes/<name>` endpoint — returns roles, block IDs, and hex preview colors for a single named palette; 404 on unknown name
- feat(cli): add `--seed-phrase <text>` flag — hashes text to deterministic seed (SHA-256 mod 2^31-1); prints resolved integer seed so ships can be reproduced
- feat(palettes): add `cherry_blossom` palette — cherry planks hull, pink concrete accent, shroomlight glow (Minecraft 1.20 cherry blossom theme)
- feat(api): add `GET /api/presets` endpoint — returns full preset metadata (hull/engine/wing/cockpit styles, size, weapon config) as JSON for all 9 archetypes
- feat(cli): add `--repeat N` flag — generates N ships with consecutive seeds from a base seed; mutually exclusive with `--seeds`
- feat(palettes): add `frozen_tundra` palette — calcite hull, packed-ice engine mass, soul-lantern cold-blue glow (arctic tundra theme)
- feat(api): add `GET /api/health` health-probe endpoint — returns `{"status":"ok","version":"...","palette_count":N,"preset_count":M}` for Docker/orchestration
- feat(palettes): add `volcanic_ash` palette — tuff hull, basalt engine casing, glowstone ember glow (volcanic ash theme)

- feat(presets): add `scout`, `battlecruiser`, `capital_carrier` ship archetypes — small fast recon, heavy combat cruiser, and massive fleet carrier presets
- feat(palettes): add `nebula_drift` palette — deep purple/purpur hull, magenta glass windows, amethyst engine block with shroomlight glow
- feat(palettes): add `solar_flare` palette — yellow/orange terracotta hull, gold-block wings, glowstone engine wash and lantern running lights
- feat(palettes): add `abyss_deep` palette — deepslate-brick hull, dark prismarine engines, soul-lantern running lights in cold deep-ocean blue
- feat(web): add DIMS (W×H×L) ship dimensions readout to viewport status bar alongside VOX and FPS
- feat(cli): add `--block-summary` flag — prints `block_id,count` CSV sorted by count descending for survival mode resource planning

- feat(cli): add `--preview-azimuth` and `--preview-elevation` flags to control isometric camera angle when saving previews
- feat(palettes): add `autumn_harvest` palette — orange terracotta hull, brown terracotta dark, shroomlight engine glow, jack o'lantern lights (seasonal theme)
- feat(web): add keyboard shortcut help overlay — press `?` (or click the `?` button) to toggle a modal listing all shortcuts; styled with neon accent border
- feat(cli): add `--palette random` alias — resolves to a randomly chosen palette at generation time
- feat(web): add ⟳ Random Palette button inline with the palette selector; updates swatch strip on click

- feat(web): palette color swatches in UI — `/api/palettes` now returns hex preview colors; swatch strip renders below palette selector
- feat(api): `GET /api/result/<gen_id>` endpoint returns full result metadata (seed, palette, shape, blocks, filename, download/preview URLs)
- feat(cli): `--output-json` flag emits NDJSON summary (seed, palette, shape, blocks, path) to stdout after each generation
- feat(api): `POST /api/batch` endpoint generates 1–10 ships per request; `api_meta` exposes `batch_max: 10`
- fix(test): replaced private `app.config["_RESULTS"]` access in eviction test with new `/api/result/<id>` endpoint
- refactor(web): split monolithic app.js/preview.js/style.css into focused modules (app_core, app_ui, preview_math, preview_renderer, preview_bootstrap, style_base, style_controls, style_preview)
- fix(block_colors): replace deprecated `Image.getdata()` with `get_flattened_data()` (Pillow 12+)
- fix(web): form controls (styles/preset/density) now wire into the generator pipeline
- feat(palettes): add circus_bigtop (red/white main, gray support, blue accent)
- chore(lint): remove unused `json` import in `tests/test_web_ui.py` (ruff autofix)

### Fixed
- **Palettes**: tightened `preview_colors` to reduce `palette_lint.py` warnings from 36 to 23. Brightened dark WINDOW previews (`coral_reef`, `crimson_nether`, `rustic_salvage`, `stealth_black`, `steampunk_brass`) above the Y≥0.35 threshold and darkened HULL_DARK previews (`biopunk_fungal`, `candy_pop`, `crimson_nether`, `deepslate_drone`, `desert_sandstone`, `ice_crystal`, `nordic_scout`, `steampunk_brass`) to raise HULL contrast above 1.5. In-game block IDs are unchanged — only the 2D preview swatches were adjusted.

### Notes
- *Intentional "non-emissive ENGINE_GLOW" lint warnings are kept as design choices: `amethyst_crystal` (amethyst_block — crystal aesthetic), `candy_pop` (pink_glazed_terracotta — candy gloss), `end_void` (end_rod — end-dimension voidrunner motif), `rustic_salvage` (fire_coral_block — scrap-metal coral glow), `sleek_modern` (end_rod — minimalist accent).*
- *Intentional duplicate-role warnings (same block assigned to two roles) are preserved when they reflect palette identity — e.g. `amethyst_crystal` HULL/WING both calcite, `stealth_black` HULL/INTERIOR both black_concrete, `wooden_frigate` WINDOW/COCKPIT_GLASS both glass.*

## [0.2.0] - 2026-04-21

Wave-1 and wave-2 content expansion, performance, and infrastructure landings.

### Added
- **Hull styles**: ARROW, SAUCER, WHALE, DAGGER, BLOCKY_FREIGHTER silhouettes (`e70d2e0`).
- **Engine styles**: `EngineStyle` enum with 5 variants (`08dfe15`).
- **Wing styles**: `WingStyle` enum with 5 silhouettes — swept, delta, tapered, gull, split (`5a7ef95`).
- **Cockpit styles**: CANOPY_DOME, WRAP_BRIDGE, OFFSET_TURRET variants (`e93bbb0`).
- **Greeble styles**: 6 greeble types plus `scatter_greebles` helper (`efe67cc`).
- **Weapon styles**: `weapon_styles` library with 5 types plus scatter helper (`6e98599`).
- **Fleet generator**: coherent multi-ship planning (`0d0d69f`).
- **Palettes**: `steampunk_brass`, `biopunk_fungal`, `cyberpunk_neon` built-ins plus palette author guide (`8acbe19`).
- **Palette linter**: validator script plus tests (`caa451c`).
- **Generator integration**: HullStyle + EngineStyle + `scatter_greebles` wired into the pipeline (`daa0313`).
- **CLI flags**: `--hull-style`, `--engine-style`, `--wing-style`, `--greeble-density`, `--list-styles` (`34f7134`); weapon-count and fleet-generation flags (`0f4af3c`).
- **Web UI polish**: palette swatches, seed copy button, shortcuts help overlay, responsive layout, theme toggle (`81ee2b1`).
- **Web style pickers**: hull, engine, wing pickers plus greeble-density slider (`65c17ed`).
- **Web live preview**: `/preview-lite` endpoint with debounced live preview toggle (`d69af03`).
- **Preview quality**: supersampling antialias, specular highlights, transparent background (`c348db7`).
- **Smoke tests**: end-to-end smoke script plus `ci-subset` pytest wrapper (`59e6aa4`).
- **Property tests**: hypothesis-based property tests; line coverage raised from 86% to 97% (`2d53980`).
- **Benchmarking**: `bench_generator` script with baseline performance report (`3c7b839`); perf-bench PR-comment workflow plus compare script (`ae5744d`).
- **Docker**: Dockerfile, `.dockerignore`, and `docs/docker.md` (`52cd49a`).
- **Docs**: project FAQ (`d2679cc`); gallery generator script plus rendered showcase (`d96b365`); README refresh with new palettes, styles, CI badge, dev section (`48120da`).
- **CI/CD**: GitHub Actions workflows for CI and release, plus release-process documentation (`726f79b`).

### Changed
- **Shape module** split into submodules, each under the 500-line ceiling (`75f9d27`).
- **Web app** split from monolithic `app.py` into Flask blueprints, each under 500 lines (`ce1e7fd`).
- **Texture**: robust palette fallbacks plus tests for all 18 palettes (`3c9ff7b`).

### Performance
- **Shape**: vectorized `_label_components` — ~91% faster (`dea1ffc`).
- **Export**: cached `BlockState` by role — ~52% faster (`aace72c`).

### Fixed
- _Nothing in 0.2.0 was a pure user-facing fix — see 0.1.0 history for earlier fixes._

### Notes
- *Commit `efe67cc` uses a palette-style message but actually contains the `greeble_styles` module — content-only, not re-pushed.*

---

## [0.1.0] - Pre-release history

Seeded from the commit log prior to formal release tagging. Grouped by
conventional-commit type.

### Added (feat)
- WingStyle enum: 5 new wing silhouettes (swept / delta / tapered / gull / split).
- Web: sci-fi console UI revamp; restored pan/orbit signs.
- Structure styles, translucent blocks, slider controls.
- Web: WebGL preview, progress bar, random-ship button.
- Block-texture preview, async web UI, palette library.
- Cockpit styles, advanced texturing, CLI batch/preview, web API.
- Web: Flask UI for interactive generation.
- Preview: headless matplotlib isometric PNG renderer.
- Generator + CLI: end-to-end pipeline orchestrator and CLI.
- Texture: refine coarse shape grid into fine role assignments.
- Shape: parts-based procedural ship with mirror symmetry.
- Export: role grid to `.litematic` via `litemapy`.
- Palette: role enum, palette YAML loader, three built-in palettes.

### Fixed (fix)
- Web: one POST per Generate/Random click.
- Web: exempt loopback from rate limiting; bump default to 30/min.
- Web: unbroken sci-fi console UI; add rate limiting.
- 20-agent swarm audit (10 hunters + 10 fixers).
- Slider controls and panning behavior.
- Floater artifacts in WebGL preview.

### Chore
- Initial project scaffold.

[Unreleased]: https://github.com/KazooKat/Spaceship-Generator/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/KazooKat/Spaceship-Generator/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/KazooKat/Spaceship-Generator/releases/tag/v0.1.0
