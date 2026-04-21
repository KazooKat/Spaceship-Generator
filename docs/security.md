# Security Audit — Spaceship Generator

Date: 2026-04-21 · Scope: `src/spaceship_generator/web/**`, `palette.py`, `export.py`.

## Threat model

The app ships as a **local developer tool** plus a thin Flask web UI. The
intended deployment is a single-user session bound to `127.0.0.1`, behind
either no proxy or a locally-trusted one. It has **no authentication**, **no
persistent user data**, **no file uploads**, and **no outbound network calls
in request paths** (the block-texture fetcher uses `allow_network=False` from
every web view).

That said, the web UI is trivial to expose (e.g. `flask run --host 0.0.0.0`
or a docker port map), so the audit assumes a hostile remote client can
reach every HTTP route. Attacker goals we care about, in priority order:

1. Remote code execution / sandbox escape — **N/A** (no deserialization,
   no `eval`, no `shell=True` anywhere, all YAML uses `safe_load`).
2. Arbitrary disk read/write — traversal through `send_file` or `out_dir`.
3. Denial of service — CPU pinning via unbounded generation requests.
4. XSS against the operator — stored or reflected in the Jinja templates.
5. SSRF pivot into metadata endpoints — outbound HTTP with user-controlled
   URLs.

## Findings

| Severity | Location | Description | Recommendation |
|----|----|----|----|
| **Medium (CVE-class: rate-limit bypass)** | `web/blueprints/ratelimit.py:89-108` | `_client_ip_key` reads the first `X-Forwarded-For` hop unconditionally, and `_is_rate_limit_exempt` exempts `127.0.0.1` / `::1` / `localhost`. When the app runs without a trusted reverse proxy stripping / overwriting XFF, any remote client can send `X-Forwarded-For: 127.0.0.1` and fully bypass the limiter, re-enabling the CPU DoS the limiter exists to stop. | Gate XFF trust behind an explicit env flag (`SHIPFORGE_TRUST_PROXY=1`). When unset, ignore the header and key on `request.remote_addr` only. The loopback exemption stays correct then. |
| **Low-Medium** | `web/app.py:54-64` | CSP allows `'unsafe-inline'` + `'unsafe-eval'` in `script-src` to support htmx `hx-*` and Alpine `x-data` reactive expressions. An XSS primitive elsewhere would be unmitigated by CSP. | Future: switch to Alpine's CSP-safe build + per-request nonces, drop `'unsafe-eval'` / `'unsafe-inline'`. Documented as a deliberate tradeoff in the existing comment. |
| **Low** | `web/app.py` (response headers) | No `X-Content-Type-Options`, `Referrer-Policy`, or `Permissions-Policy` headers. `frame-ancestors 'none'` in CSP covers X-Frame-Options. | Add `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and a minimal `Permissions-Policy` (deny camera/mic/geolocation/usb) in the existing `_apply_security_and_cache_headers` hook. |
| **Low** | `web/blueprints/ship.py` (`POST /generate`, `POST /api/generate`) | No CSRF token. An attacker-hosted page can `fetch('http://victim:5000/generate', {method:'POST', body: form})` to force ship generation. Browsers block cross-origin JSON with credentials, but form-encoded POST without credentials still runs. Since there is no auth/session, the only impact is CPU load — partly absorbed by the rate limiter (once finding #1 is closed). | Accept as-is for the local-tool use case. If the web UI ever grows state-mutating endpoints beyond "consume CPU and write to an ephemeral instance dir", add Flask-WTF / a double-submit cookie pattern. |
| **Info** | `web/blueprints/static_ext.py:23,37-38` | `/block-texture/<path:block_id>.png` validates `block_id` with `^[A-Za-z0-9_:\-\[\]=,]+$`. `block_texture_png` reads from a bundled on-disk cache only (`allow_network=False`). Regex rejects `.` and `/`, so a traversal payload like `../../etc/passwd` fails at the regex — but `block_id` is concatenated into a URL/path deeper in `block_colors.py` without a second normalization check. | Defense-in-depth: after the regex, resolve the candidate path and `assert path.is_relative_to(cache_root)` before reading. The current regex already makes traversal impossible; this just removes the "one regex to rule them all" dependency. |
| **Info** | `palette.py:122-123,189-190` | YAML loading uses `yaml.safe_load`. Palette files come from the server-side `palettes/` directory, never from request input. Safe. | Keep `safe_load`. Never accept palette YAML over HTTP. |
| **Info** | `export.py:37-38` + `generator.py:22-41,229-231` | `out_dir` is not validated by `export_litematic`, but every caller passes a server-controlled path: the web layer uses `Flask.instance_path / "generated"` (`ship_support.py:174-177`), and the CLI uses an explicit `--out` arg. The filename is sanitized by `_sanitize_filename` (rejects absolute paths, separators, `..`, `NUL`, Windows-illegal chars). | Keep the caller-supplied `out_dir` model; filename sanitization is the right trust boundary. If `export_litematic` ever grows a public caller that hands it user input, add an `out_dir` allow-list guard. |
| **Info** | `web/blueprints/ship.py:182-222`, `static_ext.py:48-65` (`send_file`) | All `send_file` calls either stream in-memory bytes (`io.BytesIO(png)`) or serve a path looked up by UUID-keyed dict (`gen_id` → `result.litematic_path`, server-generated). No user-controlled filesystem path is passed to `send_file`. Download route 404s on missing disk file instead of letting `send_file` 500. | No change needed. |
| **Info** | `block_colors.py:128-136` (`_fetch_png`) | SSRF-adjacent: builds a URL as `_MCMETA_BASE + stem + ".png"` and calls `urllib.request.urlopen`. `_MCMETA_BASE` is a hard-coded `https://raw.githubusercontent.com/...` prefix, and `stem` only comes from internal constants (`_NAME_FALLBACKS`, `_SUFFIXES`) or a regex-validated block id. Every web view passes `allow_network=False`, so this code never runs during HTTP handling. | No change needed. If request paths ever flip `allow_network=True`, also validate that `stem` matches `^[a-z0-9_]+$` before URL assembly. |
| **Info** | XSS surfaces (all Jinja templates) | Autoescape is on by default in Flask (`.html` extension triggers it). No `|safe`, `Markup(`, or `render_template_string` anywhere. Inline event handlers (`onclick="this.classList.toggle('tip-open');"`) use only literal strings, never user input. | No change needed. |

## Currently mitigated (already safe, and why)

* **Unsafe YAML deserialization** — `palette.py` uses `yaml.safe_load` on
  both call sites. No `yaml.load(...)` / `yaml.unsafe_load(...)` / `Loader=`
  anywhere in the tree.
* **Pickle / marshal / eval / exec** — grep-clean across `src/`. No
  dynamic code evaluation exists.
* **XSS** — Jinja autoescape defaults on for `.html` templates; no opt-outs
  used. No `render_template_string` calls on user input.
* **SSRF in request paths** — the only `urlopen` call sits behind
  `allow_network: bool = False`, which every web view explicitly passes.
  The URL is built from a hard-coded base + validated stem.
* **CPU DoS** — per-IP fixed-window rate limiter (default 30 req/min),
  tunable via `SHIPFORGE_RATE_LIMIT` / `SHIPFORGE_RATE_WINDOW`. Response
  includes `Retry-After`. (Note finding #1 — the XFF trust model weakens
  this against remote attackers.)
* **Filename traversal through `filename=`** — `_sanitize_filename` in
  `generator.py` rejects absolute paths, `/`, `\`, `.`, `..`, `..` anywhere
  in path parts, and the Windows-illegal set `<>:"|?*\0`.
* **`send_file` with user input** — user never hands a path; only a
  `gen_id` that's a UUID dict key into a server-controlled store.
* **CSP baseline** — present on every response (`object-src 'none'`,
  `base-uri 'self'`, `frame-ancestors 'none'`, `img-src 'self' data:`),
  gated by `SHIPFORGE_CSP` env flag for dev experimentation.
* **JSON error handler** — `/api/*` 404s return a structured JSON body
  instead of the HTML error page, avoiding a minor content-type confusion
  surface.
* **Finite-float validation** — `_finite_float` rejects `NaN` / `inf` so a
  poisoned form can't propagate through numpy into the voxel payload.
* **Enum validation** — `_parse_optional_enum` rejects unknown
  `structure_style` / `wing_style` / `hull_style` / `engine_style` /
  `cockpit_style` tokens with an explicit 400 and the valid set in the
  error message (no internal-state leak).
* **Weapon-count clamp** — `_parse_weapon_count` clamps to `[0, 8]`, so a
  tampered URL can't drive `scatter_weapons` into pathological loops.
* **Thread-safe results store** — `store_lock` around `OrderedDict`
  mutation in `_ShipState.store` prevents the LRU eviction race under
  threaded WSGI.
* **Evicted-file cleanup** — disk `.litematic` files are deleted outside
  the lock when their gen_id falls out of the LRU, bounding disk use.

## Follow-ups (in priority order)

Three concrete commits to land if the above medium finding is accepted:

1. **`fix(web): gate X-Forwarded-For trust behind SHIPFORGE_TRUST_PROXY`** —
   `ratelimit.py`: only honor `X-Forwarded-For` when the env flag is set.
   Default: ignore XFF, key on `request.remote_addr`. Loopback exemption
   then correctly applies to the actual loopback. Add one test that sends
   `X-Forwarded-For: 127.0.0.1` without the flag and asserts the request
   still gets rate-limited.

2. **`feat(web): add nosniff + referrer-policy + permissions-policy headers`** —
   `app.py`: in `_apply_security_and_cache_headers`, set
   `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and
   `Permissions-Policy: camera=(), microphone=(), geolocation=(), usb=()`
   when not already present. Add a test over `/` asserting the headers.

3. **`fix(web): re-validate block_id path is inside cache dir`** —
   `static_ext.py`: after the existing regex, resolve the candidate path
   via `block_texture_png` and add a `path.is_relative_to(cache_root)`
   assertion. Belt-and-braces defense in depth so traversal isn't one
   regex-bug away.

Optional next:

4. **`feat(web): CSP-safe Alpine build + per-request nonces`** — drop
   `'unsafe-eval'` / `'unsafe-inline'` from `script-src`. Requires a small
   build step to bundle the CSP-safe Alpine variant.
5. **`feat(cli): security-scan command`** — wire `npx @claude-flow/cli@latest
   security scan` (or a Python equivalent) into the CI smoke workflow so
   regressions (e.g. someone reintroducing `yaml.load`) fail the build.
