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

## Consumer examples

Short copy-paste snippets for downstream tools that read the output formats
above. See [`.litematic schematic`](#litematic-schematic) for the binary
artifact and [CLI JSON output (`--output-json`)](#cli-json-output---output-json)
for the NDJSON envelope.

### Python — read a `.litematic` with litemapy

`litemapy>=0.11.0b0` is already a runtime dependency (see `pyproject.toml`),
so no extra install is needed. Load the schematic, grab its single region,
and ask for the non-air block count:

```python
from litemapy import Schematic

schem = Schematic.load("out/ship_42.litematic")
region = next(iter(schem.regions.values()))
print("block_count:", region.count_blocks())  # non-air cells
```

This matches the `blocks` field emitted by `--output-json` for the same
ship. See `src/spaceship_generator/export.py` for how the file is written.

### Shell — parse `--output-json` NDJSON with `jq`

`--output-json` emits one JSON object per ship to stdout (NDJSON), so `jq`
can pull individual fields out of a bulk run. Errors stay on stderr, so no
`2>&1` is needed:

```sh
python -m spaceship_generator --output-json --seed 42 \
  --palette sci_fi_industrial --out out/ \
  | jq -r '"\(.seed)\t\(.palette)\t\(.blocks)"'
# → 42	sci_fi_industrial	1742
```

For the formal field contract, pipe `--output-json-schema` (see
[docs/cli.md](cli.md)) into a Draft-7 validator.

### Python — load a `.litematic` with amulet-core

[`amulet-core`](https://github.com/Amulet-Team/Amulet-Core) is an alternate
reader (Mojang-block-id-aware, used by the Amulet level editor) for consumers
that want world-edit semantics rather than a pure NBT view. Install with
`pip install amulet-core`; the non-air count matches `blocks` from
`--output-json` for the same ship:

```python
import amulet
from amulet.api.selection import SelectionBox

level = amulet.load_format("out/ship_42.litematic")
level.open()
box = SelectionBox((0, 0, 0), level.bounds("minecraft:overworld").max)
non_air = sum(1 for _ in level.get_coord_box("minecraft:overworld", box))
print("non_air:", non_air)
level.close()
```

### Python — parse `--stats-json` into a pandas DataFrame

`--stats-json` (see `cli.py::_print_stats_json`) emits one JSON document per
ship with a `roles` array of `{"role", "count", "pct"}` entries. Pipe a bulk
run (`--seeds A,B,C` or `--fleet-count N`) into a file and load the NDJSON to
compare role distributions across seeds:

```python
import json
import pandas as pd

with open("stats.ndjson") as fh:
    rows = [
        {"seed": doc["seed"], "palette": doc["palette"], **r}
        for doc in (json.loads(line) for line in fh)
        for r in doc["roles"]
    ]
df = pd.DataFrame(rows).pivot_table(
    index="seed", columns="role", values="count", fill_value=0
)
print(df)
```

### Shell — binary-diff two ships via `--output-json | jq`

The raw `.litematic` bytes diverge on any block reorder, so `diff` on the
schematics is too noisy. Compare structured fields from `--stats-json`
instead — `jq -S` sorts keys for a stable line-diff:

```sh
for s in 42 43; do
  python -m spaceship_generator --stats-json --seed "$s" \
    --palette sci_fi_industrial --out out/ \
    | jq -S '{seed, blocks: .total_blocks, shape, roles}' > "ship_$s.json"
done
diff -u ship_42.json ship_43.json
```

## Cross-links

- [docs/cli.md](cli.md) — per-flag CLI reference (incl. `--output-json`,
  `--output-json-schema`)
- [docs/web_ui.md](web_ui.md) — per-endpoint web reference (incl.
  `/api/generate`, `/api/result/<gen_id>`)
- [docs/configuration.md](configuration.md) — config-by-category index
- [docs/quickstart.md](quickstart.md) — 5-minute getting-started
