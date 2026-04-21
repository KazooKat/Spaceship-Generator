# FAQ

Short answers with pointers. For depth, follow the links.

## Getting started

**How do I install it?**
Clone the repo, make a venv, then `pip install -e .`. Full steps in
[README § Install](../README.md#install). Python 3.11+ is required
([README § Requirements](../README.md#requirements)).

**How do I generate my first ship?**
Run `spaceship-generator --seed 42 --palette sci_fi_industrial --out ./out`.
The CLI call and output location are documented in
[README § Usage — CLI](../README.md#usage--cli).

**Where does the output go?**
Into whatever you pass to `--out`; the filename is `ship_<seed>.litematic`
(e.g. `out/ship_42.litematic`). See [README § Usage — CLI](../README.md#usage--cli).

**Is there a web UI?**
Yes: `flask --app spaceship_generator.web.app run`, then visit
`http://127.0.0.1:5000`. See [README § Usage — Web UI](../README.md#usage--web-ui).

## Palettes

**How do I add a palette?**
Drop a YAML file into `palettes/`. It auto-appears in `--list-palettes`
and the web UI dropdown — no code changes. Full schema, role list, and
testing steps live in
[docs/palette_authoring.md](palette_authoring.md).

**What palettes ship built-in?**
21 palettes in `palettes/*.yaml`:

| | | |
|---|---|---|
| `alien_bio` | `amethyst_crystal` | `biopunk_fungal` |
| `candy_pop` | `coral_reef` | `crimson_nether` |
| `cyberpunk_neon` | `deepslate_drone` | `desert_sandstone` |
| `diamond_tech` | `end_void` | `gold_imperial` |
| `ice_crystal` | `neon_arcade` | `nordic_scout` |
| `rustic_salvage` | `sci_fi_industrial` | `sleek_modern` |
| `stealth_black` | `steampunk_brass` | `wooden_frigate` |

Source: [README § Palettes](../README.md#palettes) and `palettes/`.

## Styles

**How do I pick hull / engine / wing style?**
CLI flags: `--hull-style`, `--engine-style`, `--wing-style`, plus
`--greeble-density` and `--list-styles` (added in commit `34f7134`). In
the web UI, use the three pickers and the greeble-density slider
(`65c17ed`). Full list of each style's behavior is in
[README § Styles](../README.md#styles).

**What does each style do?**
Five hull silhouettes, five engine archetypes, five wing planforms (plus
`straight`). Descriptions for every value are in
[README § Styles](../README.md#styles).

## Seeds & reproducibility

**Does the same seed produce the same ship?**
Yes. Seed-reproducibility is a core feature — same seed + same params ==
same ship ([README § Features](../README.md#features)).

**How do I share a seed?**
Include the seed and all generation parameters (palette, dims, the three
style flags, and `--greeble-density` if set). The web UI provides a "copy
seed" button (see Wave-1 entry in
[docs/CHANGELOG.md](CHANGELOG.md#added), commit `81ee2b1`).

## Litematica loading

**Where do I put the `.litematic` file?**
Copy it into `.minecraft/schematics/` (or wherever Litematica is
configured to look), then use the Litematica mod's `Load Schematic`
menu. See [README § Usage — CLI](../README.md#usage--cli).

**Which Minecraft version?**
Minecraft Java 1.20+ with the [Litematica
mod](https://www.curseforge.com/minecraft/mc-mods/litematica)
([README § Requirements](../README.md#requirements)). Block states in
palettes must be valid 1.20+ IDs
([docs/palette_authoring.md](palette_authoring.md#blocks-format)).

## Troubleshooting

**`ValueError: Palette 'X' missing block roles: [...]`**
The palette YAML doesn't define all 10 required roles. Every palette
must map all of them; see the role table in
[docs/palette_authoring.md § The 10 Roles](palette_authoring.md#the-10-roles).
Raised from `src/spaceship_generator/palette.py:139`.

**Web UI returns HTTP 429 (`rate_limited`).**
The Flask app rate-limits POSTs (default **30/min**, see commit
`d68d986`). Loopback (`127.0.0.1` / `::1`) is exempt (`d68d986`), so
local dev should never hit it — if you do, you're likely testing from
another IP. Override with the `SHIPFORGE_RATE_LIMIT` env var (set to `0`
to disable entirely; see `tests/test_web.py::test_rate_limit_disabled_with_env_zero`).

**`--list-palettes` returns nothing after `pip install`.**
`pyproject.toml` currently only bundles `py.typed` and `data/*.json` as
package-data (`[tool.setuptools.package-data]`), and `palettes_dir()`
resolves to `<package>/../../palettes` relative to the installed source
(`src/spaceship_generator/palette.py:153`). For a non-editable install
outside the repo tree the `palettes/` directory will be missing —
install with `pip install -e .` from a checkout, or point the loader at
an explicit directory via the `search_dir` argument to
`load_palette` / `list_palettes`.

**Litemapy version mismatch / deprecation warnings.**
The project pins `litemapy>=0.11.0b0` (a beta; see `pyproject.toml`). If
you see deprecation warnings or `.litematic` load failures in Minecraft,
check that the installed litemapy version matches this floor and that
your Litematica mod is on 1.20+.

## Performance

**How fast is it, and how do I benchmark?**
Baseline is ~50 ms/ship (wall) at n=20 on the reference machine, with
further wins landed in Wave-2. Bench script, numbers, and profiler
findings are in [docs/performance.md](performance.md); CI-side
regression gating details live in [docs/bench-ci.md](bench-ci.md). Run
`python scripts/bench_generator.py` (or `scripts/bench_compare.py`) to
reproduce.

## Contributing

**How do I run tests and lint?**
`pytest` (includes Hypothesis property tests) and `ruff check .`. Setup
is in [README § Development](../README.md#development). CI runs on
3.11/3.12/3.13 × Ubuntu + Windows ([README § Features](../README.md#features)).

**Commit-message style?**
Conventional Commits — see recent history (`feat:`, `fix:`, `perf:`,
`docs:`, `chore:`, `refactor:`). The release flow in
[docs/release.md § Manual release checklist](release.md#1-manual-release-checklist)
expects the same prefixes when grouping
[docs/CHANGELOG.md](CHANGELOG.md) entries.

**Where's the release process documented?**
[docs/release.md](release.md) — tag-driven, PyPI Trusted Publishing via
OIDC, hotfix flow included.
