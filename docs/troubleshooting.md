# Troubleshooting

Quick reference for common errors when running the spaceship generator. Companion to [quickstart.md](quickstart.md) — if a command in the quickstart fails, check the table below first.

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| `Palette 'NAME' not found at .../palettes/NAME.yaml` | The palette name passed to `--palette` does not match any YAML in `palettes/`. | Run `spaceship-generator --list-palettes` to print every available name (or browse [palettes.md](palettes.md)), then re-run with one of those. |
| `argument --hull-style: invalid choice: 'X'` (or `--engine-style` / `--wing-style` / `--cockpit`) | The shape-style value is not a member of the corresponding enum. | Run `spaceship-generator --list-shape-styles` to see every `HullStyle` / `EngineStyle` / `WingStyle` member. |
| `argument --greeble-style: invalid choice: 'X'` | The greeble type is not a `GreebleType` enum member. | Run `spaceship-generator --list-greeble-types` for the bare value list. |
| `argument --weapon-type: invalid choice: 'X'` (or unknown values warned by `--weapon-types`) | The weapon-type token is not a `WeaponType` enum member. | Run `spaceship-generator --list-weapon-types` for the bare value list. |
| `--no-weapons and --weapon-count are mutually exclusive` | Both flags were passed in one invocation. | Drop one — `--no-weapons` is the shortcut for `--weapon-count 0`. |
| `--no-greebles and --greeble-density are mutually exclusive` | Both flags were passed in one invocation. | Drop one — `--no-greebles` is the shortcut for `--greeble-density 0`. |
| `--stats and --stats-json are mutually exclusive` | Both stat flags were passed. | Drop one — `--stats-json` is the machine-readable variant of `--stats`. |
| `--output - is single-ship only; mutually exclusive with --repeat, --fleet-count, --seeds` | Stdout-streaming mode only supports one ship per invocation. | Drop the bulk-mode flag, or write to a directory with `--out PATH` instead of `--output -`. |
| `--ship-size: W>=4, H>=4, L>=8 required` | Dimensions below the `ShapeParams` floor. | Pass dimensions that meet the minimums (e.g. `--ship-size 8x6x16`). |
| `argument --greeble-density: must be in [0.0, 1.0]` | Greeble density is a unit float. | Pass a value in `[0.0, 1.0]`. |
| `--seeds range must be 'A-B' with integers` (or `must not be empty`) | Malformed `--seeds` value — accepts comma-list, inclusive range, or mix. | Use `--seeds 1,2,3`, `--seeds 0-9`, or `--seeds 1,3-4,9`. |
| Web UI returns HTTP 429 with `{"error": "rate_limited"}` | Per-IP fixed-window rate limit was hit on a `POST /generate` / `/api/generate` / `/api/batch` / `GET /preview-lite` / `/download-fleet` request. | Wait `Retry-After` seconds, or tune via env vars `SHIPFORGE_RATE_LIMIT` (default 30) and `SHIPFORGE_RATE_WINDOW` (default 60s) — see [web_ui.md](web_ui.md). |
| `ModuleNotFoundError: No module named 'flask'` (or `jsonschema`, `PIL` / `Pillow`) | Optional dependency not installed in the active environment. | `pip install -e .[dev]` to pick up the dev extras, or install just the missing package (e.g. `pip install flask`); `jsonschema>=4.0` is also pinned in `requirements-dev.txt`. |
| `presets unavailable` / `weapon_styles unavailable` warning on stderr | Optional submodule failed to import (partial install or in-progress refactor). | Re-install the package with `pip install -e .` from the repo root; the CLI still runs without these but `--preset` / `--weapon-*` flags will no-op. |

## Where to find more

- [quickstart.md](quickstart.md) — 5-minute getting-started guide.
- [cli.md](cli.md) — full CLI flag reference.
- [palettes.md](palettes.md) — palette catalog with preview swatches.
- [web_ui.md](web_ui.md) — HTML pages, `/api/*` JSON routes, and rate-limit env tunables.
