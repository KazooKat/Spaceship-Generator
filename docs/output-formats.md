# Output formats

Spaceship Generator produces one binary artifact and two JSON envelopes:

1. A `.litematic` schematic — the actual ship, loadable in Minecraft.
2. A CLI JSON summary — emitted by `--output-json` (NDJSON to stdout).
3. A web API JSON response — returned by `POST /api/generate` and friends.

This page documents each shape; for per-flag and per-endpoint details see
[docs/cli.md](cli.md) and [docs/web_ui.md](web_ui.md).

## .litematic schematic

The primary artifact. `.litematic` is the schematic format used by the
[Litematica mod](https://www.curseforge.com/minecraft/mc-mods/litematica) for
Minecraft Java Edition — a gzipped NBT file describing a 3D region of block
states. Loading the file inside Litematica's `Load Schematic` menu pastes the
ship into the world.

Written by `src/spaceship_generator/export.py::export_litematic` via the
[litemapy](https://github.com/SmylerMC/litemapy) library. The exporter takes
a 3D `role_grid` indexed `grid[x, y, z]` (width × height × length, matching
Minecraft's coordinate system and litemapy's `Region(x, y, z, w, h, l)`
constructor) plus a `Palette` mapping roles to block IDs, and writes the
schematic with a single `Region` named after the ship. Cells equal to
`Role.EMPTY` (0) become `minecraft:air`. The exporter pre-seeds the region's
block palette in C-order encounter order and assigns palette indices via a
vectorized LUT — bytes are identical to the naive per-cell write but ~3x
faster on a typical ship.

Both CLI and web flows write the same format; the file is portable across
both. Compatibility tracks litemapy / Litematica; this project is tested
against Minecraft Java 1.20+.

## CLI JSON output (`--output-json`)

Pass `--output-json` and the CLI prints one JSON object per generated ship
to stdout, newline-delimited (NDJSON), so that bulk runs (`--repeat N`,
`--seeds A,B,C`) produce one machine-readable line per ship. Errors still
go to stderr.

Built by `src/spaceship_generator/cli.py::_print_json_summary`. The payload
is fixed:

```json
{"seed": 42, "palette": "sci_fi_industrial", "shape": [40, 12, 20], "blocks": 1742, "path": "out/ship_42.litematic"}
```

| field | type | meaning |
|---|---|---|
| `seed` | integer | RNG seed used |
| `palette` | string | palette name (e.g. `sci_fi_industrial`) |
| `shape` | `[int, int, int]` | grid dims `[length, height, width]` (3 entries) |
| `blocks` | integer | count of non-empty voxels in the grid |
| `path` | string | local filesystem path to the written `.litematic` |

The formal Draft-7 schema is available at runtime via `--output-json-schema`
(see `_OUTPUT_JSON_SCHEMA` in `cli.py`); pipe it into a validator if you
need a contract pin.

## Web API JSON response (`/api/generate`)

`POST /api/generate` (and `POST /api/batch`, which wraps it) returns:

```json
{
  "seed": 42,
  "palette": "sci_fi_industrial",
  "shape": [40, 12, 20],
  "blocks": 1742,
  "download_url": "/download/3f9c1ae27b4d",
  "preview_url": "/preview/3f9c1ae27b4d.png",
  "gen_id": "3f9c1ae27b4d"
}
```

Implemented in `src/spaceship_generator/web/blueprints/ship.py::api_generate`.
`gen_id` is a 12-character hex token (`uuid4().hex[:12]`) keying an
in-memory `OrderedDict` LRU cache on the Flask app (`_ShipState.results`,
guarded by a `threading.Lock`). The cache size defaults to
`MAX_RESULTS = 100`; once exceeded, the oldest entry is evicted with
`popitem(last=False)` and its on-disk `.litematic` is unlinked
(best-effort; eviction errors do not raise).

To retrieve a previously generated ship, `GET /api/result/<gen_id>` returns
the same envelope plus a `filename` field, or `404` if the `gen_id` is
unknown or has been evicted.

## Differences between CLI and web payloads

The CLI emits `path` (a local filesystem path); the web API emits
`download_url` / `preview_url` / `gen_id` (URL endpoints rooted at the
running Flask app). Both share `seed`, `palette`, `shape`, `blocks`. The
schemas diverge intentionally — `cli.py` has the comment:

> the CLI payload's key set diverges from the web payload (the CLI emits
> `path`, the web API emits `download_url` / `preview_url` / `gen_id`); the
> structural skeleton (top-level `type: object` + `properties` for `seed` /
> `palette` / `shape` / `blocks`) is kept aligned by hand. The two schemas
> should be kept in lockstep when either output gains a new field

So `--output-json-schema` and the OpenAPI `GenerateResult` component agree
on the four shared fields and disagree on the transport-specific fifth.
When adding a new field, update both.

## Cross-links

- [docs/cli.md](cli.md) — per-flag CLI reference (incl. `--output-json`,
  `--output-json-schema`)
- [docs/web_ui.md](web_ui.md) — per-endpoint web reference (incl.
  `/api/generate`, `/api/result/<gen_id>`)
- [docs/configuration.md](configuration.md) — config-by-category index
- [docs/quickstart.md](quickstart.md) — 5-minute getting-started
