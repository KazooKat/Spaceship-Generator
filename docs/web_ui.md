# Web UI & HTTP API reference

Full route catalog for the Spaceship Generator Flask app
(`flask --app spaceship_generator.web.app run`). Routes are sourced from the
blueprints in `src/spaceship_generator/web/blueprints/` — `ship.py` carries
the generate / preview / voxels / JSON API surface, `static_ext.py` carries
the cached block textures + `.litematic` downloads, and the JSON `/api/*`
half is mirrored into the hand-curated `_OPENAPI_PATHS` dict in `ship.py`
which `GET /api/spec` serves to clients.

For the CLI flag reference see [cli.md](cli.md). For the palette catalog
see [palettes.md](palettes.md).

## HTML pages

Browser-facing pages rendered with Jinja templates under
`src/spaceship_generator/web/templates/`. These return `text/html` and are
intended for direct human use, not API consumers.

| Method | Path | Template | Summary |
|---|---|---|---|
| `GET` | `/` | `index.html` | Main form: pick seed, palette, preset, hull/engine/wing/cockpit styles, shape + texture params, weapon settings; submits to `POST /generate`. Also seeds the WebGL preview canvas via `/voxels/<gen_id>.json`. |
| `POST` | `/generate` | `_result.html` (htmx) or redirects to `/result/<gen_id>` | Form-submit endpoint. Reads form fields, runs `generate()`, stores the result in the in-memory cache, then either swaps in the result partial (htmx) or redirects to the result page (full-page nav). On `ValueError`/`FileNotFoundError` re-renders `index.html` with a 400 + flash error (or `_error.html` for htmx). Rate-limited per IP. |
| `GET` | `/result/<gen_id>` | `result.html` | Result page for a previously generated ship: shows seed, palette, dims, block count, palette key swatches, embedded WebGL preview, and download link. 404 if `gen_id` is unknown or has been LRU-evicted. |

## Auxiliary (binary / JSON) routes used by the HTML UI

Non-API routes that the HTML pages depend on at render time. Not under
`/api/*` and not enumerated in `/api/spec`, but documented here because
they round-trip with the templates above.

| Method | Path | Returns | Summary |
|---|---|---|---|
| `GET` | `/preview/<gen_id>.png` | `image/png` | Matplotlib-rendered isometric preview PNG for a generated ship. Lazy: rendered on first request and cached on the result. Optional `?elev=<deg>&azim=<deg>` query params override the default view (caps `elev` to `[-89, 89]`; 400 on non-numeric). 404 if `gen_id` is unknown or its palette failed to load. |
| `GET` | `/preview-lite` | `image/png` | Cheap GET-only matplotlib preview at ≤256 px used by the debounced live-preview slider. Reads the same param set as the main form from the query string (seed, palette, shape params, etc.) and skips the `.litematic` export. `Cache-Control: public, max-age=30` so identical query strings don't re-render for half a minute. Rate-limited per IP. 400 on bad params or unknown palette. |
| `GET` | `/voxels/<gen_id>.json` | `application/json` | Surface-voxel + role-color payload for the WebGL canvas in `result.html`. Body shape: `{dims:[W,H,L], count:N, voxels:"<base64 Int16Array of x,y,z,role tuples>", colors:{"<role_int>":[r,g,b,a], ...}}`. Only emits surface voxels (filled cell with at least one empty 6-neighbor) — interior cubes are dropped to keep the payload small. 404 if `gen_id` is unknown or its palette failed to load; 500 if the role grid is not 3D. |
| `GET` | `/block-texture/<block_id>.png` | `image/png` | Serves the cached Minecraft block texture PNG keyed by namespaced block id (e.g. `minecraft:light_gray_concrete`). Read-only — never reaches out to the network at request time. 400 on malformed id, 404 if the texture is not on disk. `Cache-Control: public, max-age=604800, immutable`. |
| `GET` | `/download/<gen_id>` | `application/octet-stream` | Stream the previously generated `.litematic` file as a download (`Content-Disposition: attachment`). 404 if `gen_id` is unknown OR the underlying file was evicted from the temp tree. |
| `GET` | `/download-fleet` | `application/zip` | Plan + generate a fleet of ships and stream them back as one zip of `.litematic` entries. Query params: `seed` (int, default 0), `palette` (default `sci_fi_industrial`, must exist), `count` (int 1–20, default 1), `size_tier` (`small`/`mid`/`large`/`capital`/`mixed`, default `mixed`), `style_coherence` (float 0.0–1.0, default 0.7). Filename: `fleet_<seed>_<palette>.zip`. Rate-limited per IP. 400 on bad params, 500 on mid-pipeline generation failure. |

## JSON API (`/api/*`)

Read-only metadata + ship-generation endpoints intended for programmatic
clients. The same paths are enumerated in the OpenAPI 3.0.3 document
served at `GET /api/spec` (sourced from `_OPENAPI_PATHS` in
`src/spaceship_generator/web/blueprints/ship.py`). All responses are
`application/json`.

### Discovery & metadata

| Method | Path | Query / path params | Summary | Success body |
|---|---|---|---|---|
| `GET` | `/api/palettes` | — | List palette names with preview hex colors. | `{palettes:[<name>...], colors:{"<name>":{"<role>":"#rrggbb", ...}, ...}}` |
| `GET` | `/api/palettes/<name>` | path: `name` | Get a single palette's roles, blocks, and preview colors. 404 on unknown name. | `{name:"<n>", roles:{"<ROLE>":"<block_id>", ...}, preview_colors:{"<ROLE>":"#rrggbb", ...}}` |
| `GET` | `/api/styles` | — | All style enums: hull, engine, wing, greeble, weapon types. | `{hull_styles:[...], engine_styles:[...], wing_styles:[...], greeble_types:[...], weapon_types:[...]}` |
| `GET` | `/api/shape-styles` | — | Narrower sibling of `/api/styles` — only the three core shape enums (mirrors CLI `--list-shape-styles`). | `{hull_styles:[...], engine_styles:[...], wing_styles:[...]}` |
| `GET` | `/api/presets` | — | Full metadata for every named preset. | `{presets:[<PresetDetail>...]}` (see `/api/presets/<name>` for each entry's shape) |
| `GET` | `/api/presets/<name>` | path: `name` | Get one named preset's full metadata. 404 on unknown name; 503 if the presets module failed to import. | `{name, description, hull_style, engine_style, wing_style, cockpit_style, greeble_density, weapon_count, weapon_types:[...], size:{width,height,length}}` |
| `GET` | `/api/meta` | — | UI metadata bundle used by the Alpine.js console: palettes, presets, every enum, the `param_help` tooltip map, defaults, package version, `batch_max`. | `{palettes, presets, cockpit_styles, structure_styles, wing_styles, hull_styles, engine_styles, weapon_types, param_help, defaults, version, batch_max}` |
| `GET` | `/api/health` | — | Liveness probe. Sets `Cache-Control: no-store` so a CDN/browser can't memoize a stale "ok" reading. | `{status:"ok", version, uptime_s, palette_count, preset_count}` |
| `GET` | `/api/random` | query: `seed` (int, optional) | Random `{seed, palette, preset}` triple — "spin the wheel". With `?seed=<int>` the palette+preset selection is reproducible; without it every call yields a fresh non-deterministic pick via `secrets.randbits`. `Cache-Control: no-store`. | `{seed, palette, preset}` |
| `GET` | `/api/spec` | — | OpenAPI 3.0.3 schema enumerating every `/api/*` route (paths, methods, summaries, params, 200 schemas). Hand-curated alongside the routes in `_OPENAPI_PATHS`. | OpenAPI 3.0.3 document (`{openapi, info, paths, components}`) |

### Generation

| Method | Path | Query / path / body params | Summary | Success body |
|---|---|---|---|---|
| `POST` | `/api/generate` | JSON body: same param surface as the HTML form (seed, palette, shape params, texture params, style pickers, weapon_count, etc.) | Generate one ship. Stores the result in the in-memory cache. Rate-limited per IP. 400 on bad params, 429 if rate-limited. | `{seed, palette, shape:[W,H,L], blocks, download_url, preview_url, gen_id}` |
| `POST` | `/api/batch` | JSON body: any single-ship param set + `count` (int 1–10) and optional `seed` (base; per-ship seeds are `seed+i`) | Generate up to 10 ships in one call. If any ship fails the whole batch returns 400 with the failing `ship_index`. Rate-limited per IP. | `{ships:[<GenerateResult>...], count}` |
| `GET` | `/api/result/<gen_id>` | path: `gen_id` | Fetch metadata for a previously generated ship. 404 if unknown or evicted. | `{gen_id, seed, palette, shape:[W,H,L], blocks, filename, download_url, preview_url}` |
| `GET` | `/api/fleet/plan` | query: `seed` (int, default 0), `palette` (str, default `sci_fi_industrial`), `count` (int 1–10, default 3), `size_tier` (`small`/`mid`/`large`/`capital`/`mixed`, default `mid`), `coherence` (float 0.0–1.0, default 0.8) | Plan a fleet — runs the fleet RNG and returns per-ship metadata only. No files are written and no `gen_id` is allocated. 400 on bad params. | `{seed, palette, count, size_tier, coherence, ships:[{index, seed, hull_style, engine_style, wing_style, cockpit_style, greeble_density, weapon_count, dims:{width,height,length}}, ...]}` |
| `GET` | `/api/compare` | query: `seed_a` (int, required), `seed_b` (int, required), `palette` (str, default `sci_fi_industrial`), `preset` (str, optional) | Compare two ships side-by-side without generating files. Returns dims, voxel count, and role-count breakdown for each. 400 on missing/invalid params. | `{palette, ship_a:<ShipMetadata>, ship_b:<ShipMetadata>}` where `ShipMetadata = {seed, dimensions:{width,height,length}, voxel_count, role_counts:{"<role_int>":N, ...}}` |

### Error response shapes

* `400` — `{error:"<message>"}` (and `{error,"ship_index":i}` from `/api/batch`).
* `404` — `{error:"<message>"}` (e.g. unknown palette, unknown preset, unknown `gen_id`).
* `429` — `{error:"rate_limited", retry_after, limit, window_seconds}` plus a `Retry-After` header (rounded up to whole seconds per RFC 9110).
* `503` — `{error:"presets unavailable"}` from `/api/presets/<name>` when the optional presets module fails to import.

## Rate limiting

`POST /generate`, `POST /api/generate`, `POST /api/batch`,
`GET /preview-lite`, and `GET /download-fleet` are rate-limited per
client IP via a fixed-window counter (see
`src/spaceship_generator/web/blueprints/ratelimit.py`). Loopback
addresses (`127.0.0.1`, `::1`, `localhost`) are exempt — local dev
never hits the cap. Tunables (env vars, read once at app creation):

| Env var | Default | Description |
|---|---|---|
| `SHIPFORGE_RATE_LIMIT` | `30` | Max requests per window per IP. Set to `0` to disable the limiter. |
| `SHIPFORGE_RATE_WINDOW` | `60` | Window length in seconds. |
| `SHIPFORGE_CSP` | `1` | Content-Security-Policy enable flag. Set to `0`/`false`/`off`/`no` to disable the CSP header (useful for local dev with inline scripts). |
