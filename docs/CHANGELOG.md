# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Wave-1 content expansion and infrastructure landings.

### Added
- **Hull styles**: ARROW, SAUCER, WHALE, DAGGER, BLOCKY_FREIGHTER silhouettes (`e70d2e0`).
- **Engine styles**: `EngineStyle` enum with 5 variants (`08dfe15`).
- **Greeble styles**: 6 greeble types plus `scatter_greebles` helper (`efe67cc`).
- **Palettes**: `steampunk_brass`, `biopunk_fungal`, `cyberpunk_neon` built-ins plus palette author guide (`8acbe19`).
- **Web UI polish**: palette swatches, seed copy button, shortcuts help overlay, responsive layout, theme toggle (`81ee2b1`).
- **Benchmarking**: `bench_generator` script with baseline performance report (`3c7b839`).
- **Property tests**: hypothesis-based property tests; line coverage raised from 86% to 97% (`2d53980`).
- **CI/CD**: GitHub Actions workflows for CI and release, plus release-process documentation (`726f79b`).

### Changed
- **Shape module** split into submodules, each under the 500-line ceiling (`75f9d27`).
- **Web app** split from monolithic `app.py` into Flask blueprints, each under 500 lines (`ce1e7fd`).

### Fixed
- _Nothing in wave-1 was a pure fix — see 0.1.0 history for earlier fixes._

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

[Unreleased]: https://github.com/KazooKat/Spaceship-Generator/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/KazooKat/Spaceship-Generator/releases/tag/v0.1.0
