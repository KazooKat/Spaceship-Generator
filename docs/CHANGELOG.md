# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
