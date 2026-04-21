# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- _Nothing yet._

### Changed
- _Nothing yet._

### Fixed
- _Nothing yet._

### Removed
- _Nothing yet._

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
