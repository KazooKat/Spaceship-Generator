// Spaceship Generator — UI polish layer.
//
// This file is additive: every other module (app.js, shortcuts.js, hud.js,
// etc.) is untouched. Responsibilities:
//
//   * Palette swatch strip next to the palette dropdown. Colors are derived
//     from a deterministic hash of the palette name, then refined with the
//     real block colors scraped from .key-hex after a matching ship has been
//     generated (cached in localStorage so repeat selections show the real
//     palette at a glance).
//
//   * Copy-seed button: writes the current #seed value to the clipboard,
//     with a document.execCommand('copy') fallback for older browsers and
//     a toast confirmation.
//
//   * Theme toggle: swaps the [data-theme] attribute on <html> between
//     "dark" (default) and "light", persisted via localStorage. The
//     <html data-theme> attribute is also pre-seeded by a tiny inline
//     script in base.html so there's no dark flash on cold page loads.
//
// No build tooling, no new deps. Vanilla JS only. Safe on HTMX swaps.

(function () {
    "use strict";

    // --- small utilities -----------------------------------------------------

    function byId(id) { return document.getElementById(id); }

    function safeToast(kind, text) {
        if (window.ui && typeof window.ui.toast === "function") {
            try { window.ui.toast(kind, text); return; } catch (e) { /* noop */ }
        }
        if (window.console && console.log) console.log("[toast " + kind + "]", text);
    }

    function reinitIcons() {
        if (window.ui && typeof window.ui.reinitLucide === "function") {
            try { window.ui.reinitLucide(); } catch (e) { /* noop */ }
        } else if (window.__lucide && window.__lucide.createIcons) {
            try { window.__lucide.createIcons({ icons: window.__lucide.icons }); } catch (e) { /* noop */ }
        }
    }

    // =========================================================================
    // THEME TOGGLE
    // =========================================================================

    var THEME_KEY = "shipforge.theme";

    function currentTheme() {
        var attr = document.documentElement.getAttribute("data-theme");
        if (attr === "light" || attr === "dark") return attr;
        try {
            var stored = window.localStorage.getItem(THEME_KEY);
            if (stored === "light" || stored === "dark") return stored;
        } catch (e) { /* noop */ }
        return "dark";
    }

    function applyTheme(theme) {
        if (theme !== "light" && theme !== "dark") theme = "dark";
        document.documentElement.setAttribute("data-theme", theme);
        try { window.localStorage.setItem(THEME_KEY, theme); } catch (e) { /* noop */ }
        updateThemeButton(theme);
    }

    function updateThemeButton(theme) {
        var btn = byId("btn-theme");
        if (!btn) return;
        var next = theme === "light" ? "dark" : "light";
        btn.setAttribute("aria-label", "Switch to " + next + " theme");
        btn.setAttribute("title", "Theme: " + theme.toUpperCase());
        // Replace the icon so the user sees which state they'll switch to.
        var icon = btn.querySelector("[data-theme-icon]");
        if (icon) {
            var name = theme === "light" ? "sun" : "moon";
            icon.setAttribute("data-lucide", name);
        }
        reinitIcons();
    }

    function bindThemeToggle() {
        var btn = byId("btn-theme");
        if (!btn || btn.dataset.themeBound === "1") return;
        btn.dataset.themeBound = "1";
        btn.addEventListener("click", function () {
            var next = currentTheme() === "light" ? "dark" : "light";
            applyTheme(next);
            safeToast("info", "THEME: " + next.toUpperCase());
        });
        // Sync the button visuals on first boot.
        updateThemeButton(currentTheme());
    }

    // =========================================================================
    // COPY SEED
    // =========================================================================

    function copyText(text) {
        // Prefer the async Clipboard API. Fall back to a transient textarea
        // + execCommand('copy') for older browsers / non-HTTPS dev loopbacks.
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text);
        }
        return new Promise(function (resolve, reject) {
            try {
                var ta = document.createElement("textarea");
                ta.value = text;
                ta.setAttribute("readonly", "");
                ta.style.position = "absolute";
                ta.style.left = "-9999px";
                document.body.appendChild(ta);
                ta.select();
                var ok = document.execCommand("copy");
                document.body.removeChild(ta);
                if (ok) resolve(); else reject(new Error("execCommand failed"));
            } catch (e) {
                reject(e);
            }
        });
    }

    function bindCopySeed() {
        var btn = byId("btn-copy-seed");
        if (!btn || btn.dataset.copySeedBound === "1") return;
        btn.dataset.copySeedBound = "1";
        btn.addEventListener("click", function () {
            var input = byId("seed");
            var value = input ? String(input.value || "").trim() : "";
            if (!value) {
                safeToast("warn", "NO SEED TO COPY");
                return;
            }
            copyText(value).then(
                function () { safeToast("success", "SEED " + value + " COPIED"); },
                function () { safeToast("error", "COPY FAILED"); }
            );
        });
    }

    // =========================================================================
    // PALETTE SWATCHES
    // =========================================================================
    //
    // Strategy:
    //   * The backend's /api/palettes only returns palette names, not colors.
    //     We can't add routes (backend is read-only for this task), so we
    //     compute a small deterministic swatch strip from a hash of the name.
    //   * Whenever a ship is generated, .result-inner .key-list .key-hex
    //     carries the *real* approximated block colors for the palette the
    //     user just rendered. We scrape those and cache them under the
    //     palette name so the next time the user picks that palette in the
    //     dropdown, the strip shows real block colors.
    //   * "random" palette shows a question-mark style row so users know
    //     the concrete colors aren't decidable until generation.

    var SWATCH_CACHE_KEY = "shipforge.paletteSwatches.v1";
    var SWATCH_COUNT = 5;

    function readSwatchCache() {
        try {
            var raw = window.localStorage.getItem(SWATCH_CACHE_KEY);
            if (!raw) return {};
            var parsed = JSON.parse(raw);
            return (parsed && typeof parsed === "object") ? parsed : {};
        } catch (e) {
            return {};
        }
    }

    function writeSwatchCache(map) {
        try {
            window.localStorage.setItem(SWATCH_CACHE_KEY, JSON.stringify(map));
        } catch (e) { /* quota / privacy mode — silently ignore */ }
    }

    // Tiny deterministic 32-bit string hash. Not cryptographic — we just
    // need repeatable pseudo-random bytes per palette name.
    function hash32(str) {
        var h = 2166136261 >>> 0;
        for (var i = 0; i < str.length; i++) {
            h ^= str.charCodeAt(i);
            h = Math.imul(h, 16777619);
        }
        return h >>> 0;
    }

    // HSL -> "hsl(H,S%,L%)" string. We lean on the browser to convert.
    function hsl(h, s, l) {
        return "hsl(" + Math.round(h) + "," + Math.round(s) + "%," + Math.round(l) + "%)";
    }

    function fallbackColorsFor(name) {
        // Spread 5 hues around the wheel, anchored on the name hash. Keep
        // saturation/lightness in a readable band against both themes.
        if (!name || name === "random") {
            return [
                "hsl(0,0%,28%)", "hsl(0,0%,38%)", "hsl(0,0%,48%)",
                "hsl(0,0%,58%)", "hsl(0,0%,68%)",
            ];
        }
        var h0 = hash32(name) % 360;
        var out = [];
        for (var i = 0; i < SWATCH_COUNT; i++) {
            var hue = (h0 + i * 47) % 360;
            var sat = 42 + ((hash32(name + ":s:" + i)) % 28);  // 42-70
            var lum = 34 + ((hash32(name + ":l:" + i)) % 34);  // 34-68
            out.push(hsl(hue, sat, lum));
        }
        return out;
    }

    function scrapeResultHexes(scope) {
        // Return up to SWATCH_COUNT "#rrggbb" strings from the block-key
        // .key-hex elements in the current result partial. Duplicates are
        // skipped so a 5-cell strip actually shows 5 distinct colors.
        var root = scope || document;
        var hexEls = root.querySelectorAll(".result-inner .key-hex");
        var seen = {};
        var out = [];
        for (var i = 0; i < hexEls.length && out.length < SWATCH_COUNT; i++) {
            var raw = (hexEls[i].textContent || "").trim();
            // Normalize: must look like #rgb or #rrggbb, case-insensitive.
            var m = raw.match(/#[0-9a-fA-F]{3,6}/);
            if (!m) continue;
            var hex = m[0].toLowerCase();
            if (seen[hex]) continue;
            seen[hex] = true;
            out.push(hex);
        }
        return out;
    }

    function colorsFor(name) {
        if (!name) return fallbackColorsFor("");
        var cache = readSwatchCache();
        var cached = cache[name];
        if (Array.isArray(cached) && cached.length) {
            // Pad with hashed fallbacks if the scraped set was shorter than
            // SWATCH_COUNT so the strip always looks balanced.
            if (cached.length >= SWATCH_COUNT) return cached.slice(0, SWATCH_COUNT);
            var pad = fallbackColorsFor(name);
            return cached.concat(pad.slice(cached.length));
        }
        return fallbackColorsFor(name);
    }

    function renderSwatches() {
        var host = byId("palette-swatches");
        if (!host) return;
        var select = byId("palette") || document.querySelector('select[name="palette"]');
        var name = select ? select.value : "";
        host.innerHTML = "";

        var colors = colorsFor(name);
        var cache = readSwatchCache();
        var isReal = Array.isArray(cache[name]) && cache[name].length > 0;

        colors.forEach(function (c, i) {
            var cell = document.createElement("span");
            cell.className = "palette-swatch";
            cell.style.background = c;
            cell.setAttribute("title", (isReal ? "" : "≈ ") + c);
            cell.setAttribute("aria-hidden", "true");
            host.appendChild(cell);
            void i;
        });

        // Small textual hint so screen readers know the mode.
        host.setAttribute("data-source", isReal ? "real" : "approx");
        host.setAttribute("aria-label",
            (isReal ? "Palette preview (from last generation): " : "Palette preview (approximate): ")
            + (name || "none"));
    }

    function captureCurrentPaletteSwatches(scope) {
        // Called after a successful HTMX swap. Read the just-rendered ship's
        // palette + key-hex colors and stash them for future dropdown changes.
        var root = scope || document;
        var inner = root.querySelector ? root.querySelector(".result-inner") : null;
        if (!inner) return;
        var palette = (inner.getAttribute("data-palette") || "").trim();
        if (!palette) return;
        var hexes = scrapeResultHexes(root);
        if (!hexes.length) return;
        var cache = readSwatchCache();
        cache[palette] = hexes;
        writeSwatchCache(cache);
        // If the dropdown still has this palette selected, refresh live.
        var select = byId("palette") || document.querySelector('select[name="palette"]');
        if (select && select.value === palette) renderSwatches();
    }

    function bindPaletteSwatches() {
        var select = byId("palette") || document.querySelector('select[name="palette"]');
        if (!select || select.dataset.swatchBound === "1") return;
        select.dataset.swatchBound = "1";
        select.addEventListener("change", renderSwatches);
        select.addEventListener("input", renderSwatches);
        renderSwatches();
    }

    // =========================================================================
    // HELP MODAL — keep the Lucide icon inside the help dl refreshed when
    // Alpine flips helpOpen on. The template uses an Alpine <template x-if> so
    // the modal is mounted fresh every time — our icons call handles that.
    // =========================================================================

    function watchHelpModal() {
        // Alpine dispatches transition events on the modal-backdrop when it
        // appears; re-running reinitIcons there catches the freshly-mounted
        // SVG placeholders. The existing htmx:afterSwap hook in app.js already
        // reinits icons for HTMX-swapped content, so we only need the Alpine
        // side here.
        document.addEventListener("click", function (ev) {
            var t = ev.target;
            if (!t || !t.closest) return;
            if (t.closest("#btn-help")) {
                // Tiny timeout so the <template x-if> has expanded.
                window.setTimeout(reinitIcons, 0);
            }
        });
    }

    // =========================================================================
    // BOOT
    // =========================================================================

    function boot() {
        bindThemeToggle();
        bindCopySeed();
        bindPaletteSwatches();
        watchHelpModal();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }

    // Re-bind + capture on every HTMX swap. The result partial carries fresh
    // block colors we want to remember, and the sidebar pieces can theoretically
    // be swapped too (e.g., if a future agent ever swaps the whole form).
    if (document.body) {
        document.body.addEventListener("htmx:afterSwap", function (ev) {
            bindThemeToggle();
            bindCopySeed();
            bindPaletteSwatches();
            captureCurrentPaletteSwatches(ev && ev.target ? ev.target : document);
        });
    }

    // --- Public API (for tests / debugging) ---------------------------------

    window.shipPolish = {
        applyTheme: applyTheme,
        currentTheme: currentTheme,
        renderSwatches: renderSwatches,
        captureCurrentPaletteSwatches: captureCurrentPaletteSwatches,
        copyText: copyText,
        _colorsFor: colorsFor,
        _fallbackColorsFor: fallbackColorsFor,
        _cacheKey: SWATCH_CACHE_KEY,
        _themeKey: THEME_KEY,
    };
})();
