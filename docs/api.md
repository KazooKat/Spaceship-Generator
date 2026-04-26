# REST API Reference

Spaceship Generator is a **Flask** app. The primary surface is an HTML UI
(htmx + Alpine.js + a WebGL canvas); several endpoints also return JSON and
can be driven as a JSON API. Source of truth:
`src/spaceship_generator/web/blueprints/`.

## Overview

* `create_app()` lives in `src/spaceship_generator/web/app.py`. Blueprints:
  `ship` (generation + preview + JSON API) and `static_ext` (textures +
  downloads).
* Rate limit: per-client fixed-window, **30 req/min** default (env
  `SHIPFORGE_RATE_LIMIT`, `SHIPFORGE_RATE_WINDOW`). Loopback
  (`127.0.0.1`, `::1`, `localhost`) is **exempt**. Over the limit → `429`
  with `Retry-After`.
* Errors: JSON `404` when the caller prefers `application/json`, else plain
  HTML 404.
* `gen_id` is a 12-char hex UUID held in an in-memory LRU (default 100).
  Evicted ids 404 on follow-up requests and their `.litematic` is deleted.

## Endpoints

### `GET /`

HTML. Renders the generator form with palettes, cockpit / structure / wing /
hull / engine / weapon enums and the default parameter seed. Not rate-limited.
Responses: `200 text/html`.

### `POST /generate` [rate-limited]

Backs the on-page Generate button. Accepts `application/x-www-form-urlencoded`
or an HTMX request (`HX-Request: true`).

* Plain form → `302` redirect to `/result/<gen_id>`.
* HTMX → `200 text/html` partial (`_result.html`).

Form fields (all optional; defaults mirror `GET /`):

| Field | Type | Notes |
|---|---|---|
| `seed` | int | Any integer; deterministic. |
| `palette` | str | Palette name, or `random` (deterministic per-seed pick). |
| `length`, `width`, `height` | int | Voxel dims. |
| `engines` | int | 0-6. |
| `wing_prob` | float | 0-1 finite. |
| `greeble_density` | float | 0-1, auto-clamped. |
| `cockpit` | enum | `CockpitStyle` values. |
| `structure_style` | enum | `StructureStyle` values. |
| `wing_style` | enum | `straight`, `swept`, `delta`, `tapered`, `gull`, `split`. |
| `hull_style`, `engine_style` | enum or `auto` | Optional. |
| `weapon_count` | int | Clamped to 0-8. |
| `weapon_types` | list / CSV | `WeaponType` values; unknowns dropped. |
| `window_period`, `accent_stripe_period`, `engine_glow_depth`, `hull_noise_ratio`, `panel_line_bands`, `rivet_period`, `engine_glow_ring` | various | Texture controls. |

Responses: `302` / `200 text/html`, `400` on bad input, `429` when rate-limited.

### `GET /result/<gen_id>`

HTML. Renders `result.html` for a previously generated ship. `404` if
`gen_id` is unknown or has been evicted from the LRU. Not rate-limited.

### `GET /preview/<gen_id>.png`

Matplotlib-rendered preview of a stored ship. Lazy-rendered; the default view
is cached in-memory after first request.

Query (optional): `elev` (float, clamped `-89..89`), `azim` (float). With
neither, the default cached view is returned; with either, a custom-angle
render is produced (not cached).

Responses: `200 image/png`, `400` on bad query, `404` unknown / evicted.

### `GET /preview-lite` [rate-limited]

Debounced live-preview PNG for sidebar slider drags. Same parameter surface as
`POST /generate`, but read from `request.args` (query string). Skips the
`.litematic` export; renders at 256 px. Sets
`Cache-Control: public, max-age=30`.

Responses: `200 image/png`, `400` on bad input, `429` when rate-limited.

### `GET /voxels/<gen_id>.json`

Surface-voxel payload for the WebGL canvas:

```json
{
  "dims":   [W, H, L],
  "count":  N,
  "voxels": "<base64 Int16Array, length 4*N, (x,y,z,role) tuples, LE>",
  "colors": {"1": [r, g, b, a], "2": [r, g, b, a]}
}
```

Only **surface** voxels are emitted (filled cells with ≥1 empty 6-neighbor).
Translucent Minecraft blocks (glass / ice / honey / slime) have their alpha
rewritten so the client can blend.

Responses: `200 application/json`, `404` unknown / evicted, `500` if the grid
isn't 3-D.

### `GET /block-texture/<block_id>.png`

Passthrough for the on-disk Minecraft block-texture cache. `block_id` may
include a state spec (`my_mod:lamp[lit=true]`); unsafe characters → `400`.
Only serves files already cached (no runtime network fetch). Sets
`Cache-Control: public, max-age=604800, immutable`.

Responses: `200 image/png`, `400` malformed id, `404` un-cached.

### `GET /download/<gen_id>`

Stream the `.litematic` as `application/octet-stream` attachment. `404` if
the id is unknown or the file was swept off disk (LRU eviction, manual
cleanup).

### `GET /api/palettes`

JSON. `{"palettes": ["sci_fi_industrial", ...]}`. Not rate-limited.

### `POST /api/generate` [rate-limited]

JSON-in, JSON-out sibling of `POST /generate`. Body keys match the form table
above. On success:

```json
{
  "seed": 42,
  "palette": "sci_fi_industrial",
  "shape": [40, 20, 12],
  "blocks": 1423,
  "download_url": "/download/<gen_id>",
  "preview_url": "/preview/<gen_id>.png",
  "gen_id": "abc123def456"
}
```

Responses: `200 application/json`, `400 {"error": "..."}`, `429
{"error":"rate_limited","retry_after":N,"limit":M,"window_seconds":W}`.

### `GET /api/meta`

UI metadata: palette list, all enum values, tooltip text, defaults, package
version. Used by the sci-fi console frontend to avoid scraping `/`:

```json
{
  "palettes": ["..."],
  "cockpit_styles": ["..."],
  "structure_styles": ["..."],
  "wing_styles": ["..."],
  "hull_styles": ["..."],
  "engine_styles": ["..."],
  "weapon_types": ["..."],
  "param_help": {"seed": "...", "...": "..."},
  "defaults": {"seed": 42, "palette": "sci_fi_industrial", "...": "..."},
  "version": "dev"
}
```

### `GET /api/spec`

JSON. Hand-written **OpenAPI 3.0.3** document enumerating every public
`/api/*` route — useful for client codegen, doc browsers (Swagger UI,
Redoc), and contract testing. Not rate-limited.

The spec's `paths` map mirrors the live route table in
`src/spaceship_generator/web/blueprints/ship.py`. Each operation carries at
minimum a `summary`, a 200-case response schema, and (where applicable)
query / path parameters and request bodies. Top-level shape:

```json
{
  "openapi": "3.0.3",
  "info": {
    "title": "Spaceship Generator API",
    "version": "0.2.0",
    "description": "..."
  },
  "paths": {
    "/api/health": {"get": {"summary": "...", "responses": {"200": {...}}}},
    "/api/random": {"get": {"summary": "...", "parameters": [...], "responses": {...}}},
    "...": "..."
  },
  "components": {"schemas": {"...": {...}}}
}
```

Responses: `200 application/json`.

## curl examples

```bash
# Generate via JSON API.
curl -s -X POST http://localhost:5000/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"seed": 42, "palette": "sci_fi_industrial", "engines": 2, "wing_style": "swept"}'

# Download the resulting .litematic.
curl -sOJ http://localhost:5000/download/<gen_id>

# Live-preview a parameter combo as a 256 px PNG.
curl -s 'http://localhost:5000/preview-lite?seed=42&wing_style=delta' -o live.png

# Fetch UI metadata (palettes, enums, defaults, version).
curl -s http://localhost:5000/api/meta | jq '.palettes, .wing_styles, .version'

# Pull surface voxels for a WebGL client.
curl -s http://localhost:5000/voxels/<gen_id>.json | jq '.dims, .count'
```

## Related docs

* [Architecture](./architecture.md) — blueprints, state, generator pipeline.
* [FAQ](./faq.md) — rate limits, palette `random`, seeds.
* [Presets](./presets.md) — parameter bundles for the JSON API.
* [Palette authoring](./palette_authoring.md) — add palettes referenced by
  `palette=`.
