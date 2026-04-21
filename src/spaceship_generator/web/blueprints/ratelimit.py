"""Per-client fixed-window rate limiter.

Generation is CPU + memory heavy (numpy voxel grid + palette mapping +
litematic serialization + optional preview PNG). Without a cap, a single
impatient client holding Enter on Generate can pin the server. The limiter
is a per-client fixed-window token counter keyed by the best-effort client
IP, thread-safe under the default Flask dev + gunicorn-sync workers.

Tunables (env vars, both honored on app creation):

* ``SHIPFORGE_RATE_LIMIT``  — max requests per window per IP (default 30)
                              set to 0 to disable the limiter entirely
* ``SHIPFORGE_RATE_WINDOW`` — window length in seconds (default 60)

The limiter does NOT persist across restarts — that's fine for the
protection we want here (absorb local bursts). A reverse proxy with
proper throttling (nginx, Cloudflare) should be used in production.
"""

from __future__ import annotations

import math
import os
import threading
import time
from typing import Callable

from flask import Flask, current_app, jsonify, render_template, request


class _RateLimiter:
    """Per-key fixed-window counter. Not a token bucket — simpler and
    adequate for the small-abuse case we care about. Zero deps."""

    def __init__(self, max_requests: int, window_s: float) -> None:
        self.max_requests = int(max_requests)
        self.window_s = float(window_s)
        self._lock = threading.Lock()
        # key -> (window_start_ts, count)
        self._windows: dict[str, tuple[float, int]] = {}
        # Opportunistic GC threshold to bound memory if we see many unique
        # IPs over time.
        self._max_keys = 4096

    def check(self, key: str, now: float | None = None) -> tuple[bool, float]:
        """Return ``(allowed, retry_after_seconds)``.

        ``retry_after_seconds`` is 0 when allowed, otherwise the number of
        seconds until the current window rolls over.
        """
        if self.max_requests <= 0:
            # Disabled: always allow.
            return True, 0.0
        ts = now if now is not None else time.monotonic()
        with self._lock:
            start, count = self._windows.get(key, (ts, 0))
            elapsed = ts - start
            if elapsed >= self.window_s:
                # Fresh window.
                self._windows[key] = (ts, 1)
                self._maybe_gc(ts)
                return True, 0.0
            if count < self.max_requests:
                self._windows[key] = (start, count + 1)
                return True, 0.0
            retry = max(0.0, self.window_s - elapsed)
            return False, retry

    def _maybe_gc(self, ts: float) -> None:
        # Called under the lock. Drops stale windows if the dict is big.
        if len(self._windows) < self._max_keys:
            return
        cutoff = ts - self.window_s
        stale = [k for k, (start, _) in self._windows.items() if start < cutoff]
        for k in stale:
            self._windows.pop(k, None)


# IPs that should never be rate-limited. Loopback covers local dev
# against the Flask dev server or a local gunicorn — hammering
# Generate while iterating shouldn't lock the developer out for a
# whole window. Production deployments behind a proxy see the real
# client IP via X-Forwarded-For, so loopback here really does mean
# "same machine as the server" and is safe to exempt.
_RATE_LIMIT_EXEMPT_IPS = frozenset({
    "127.0.0.1", "::1", "localhost",
})


def _client_ip_key() -> str:
    """Best-effort client key for rate limiting. Honors X-Forwarded-For's
    first hop (common behind a reverse proxy); falls back to
    ``request.remote_addr``; finally uses the literal "anon" bucket so we
    still have *some* cap even when the request has no address."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        head = xff.split(",", 1)[0].strip()
        if head:
            return head
    return request.remote_addr or "anon"


def _is_rate_limit_exempt(key: str) -> bool:
    """True when the resolved client key is a loopback address and
    should bypass the limiter. Kept as a separate hook so tests can
    still exercise the 429 path by passing non-loopback
    X-Forwarded-For headers."""
    return key in _RATE_LIMIT_EXEMPT_IPS


def _rate_limited_response(retry_after: float, *, as_json: bool):
    """Build a 429 response with a ``Retry-After`` header. ``retry_after``
    is rounded UP to the next whole second per RFC 9110."""
    app = current_app
    limiter: _RateLimiter = app.extensions["shipforge_rate_limiter"]
    retry_s = max(1, int(math.ceil(retry_after)))
    if as_json:
        resp = jsonify({
            "error": "rate_limited",
            "retry_after": retry_s,
            "limit": limiter.max_requests,
            "window_seconds": int(limiter.window_s),
        })
    else:
        is_htmx = request.headers.get("HX-Request", "").lower() == "true"
        msg = (
            f"Too many generations — slow down. Try again in {retry_s}s."
        )
        if is_htmx:
            resp = app.response_class(
                render_template("_error.html", error=msg),
                mimetype="text/html",
            )
        else:
            resp = app.response_class(msg, mimetype="text/plain")
    resp.status_code = 429
    resp.headers["Retry-After"] = str(retry_s)
    return resp


def check_rate_limit(*, as_json: bool):
    """Return a 429 response if the request is over the limit, else
    ``None`` to let the view proceed. Uses ``current_app.extensions``
    to locate the per-app limiter instance so this helper can be
    imported into any blueprint without closure state."""
    limiter: _RateLimiter = current_app.extensions["shipforge_rate_limiter"]
    key = _client_ip_key()
    if _is_rate_limit_exempt(key):
        return None
    allowed, retry = limiter.check(key)
    if allowed:
        return None
    return _rate_limited_response(retry, as_json=as_json)


def init_rate_limiter(app: Flask) -> _RateLimiter:
    """Read env config and attach a fresh ``_RateLimiter`` instance to ``app``.

    Default raised from 10 → 30/min after the dev-loop hit the cap during
    normal iteration. 30 covers burst-use of the Random button and leaves
    enough headroom that a developer holding the UI rarely notices the
    limiter while still stopping true abuse.
    """
    try:
        rate_max = int(os.environ.get("SHIPFORGE_RATE_LIMIT", "30"))
    except ValueError:
        rate_max = 30
    try:
        rate_window = float(os.environ.get("SHIPFORGE_RATE_WINDOW", "60"))
    except ValueError:
        rate_window = 60.0
    app.config.setdefault("RATE_LIMIT_MAX", rate_max)
    app.config.setdefault("RATE_LIMIT_WINDOW", rate_window)
    limiter = _RateLimiter(rate_max, rate_window)
    # Exposed for tests that want to reset state between cases.
    app.extensions["shipforge_rate_limiter"] = limiter
    return limiter


__all__ = [
    "_RateLimiter",
    "_RATE_LIMIT_EXEMPT_IPS",
    "_client_ip_key",
    "_is_rate_limit_exempt",
    "check_rate_limit",
    "init_rate_limiter",
]
