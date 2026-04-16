// Spaceship Generator — client-side UI wiring.
//
// Responsibilities:
//   * HTMX bridges (swap 4xx responses, re-init Lucide + tooltip flip, re-init
//     WebGL canvas on the new partial)
//   * Top-bar buttons: Generate, Random (randomize every param and submit),
//     Randomize seed, Download, Fullscreen, view presets
//   * Paired slider + number input binding (plus readout update)
//   * Status indicator driven by HTMX lifecycle events
//   * Toast helper on window.ui
//
// Globals exposed:
//   window.ui          = { toast, setStatus }
//   window.__lucide    = { createIcons, icons }   (populated by index.html CDN)
//   window.shipPreview = { init, setView, resetCamera, fullscreen, ... }  (preview.js)

(function () {
    "use strict";

    // --- constants -----------------------------------------------------------

    var STATUS_DOT_CLASSES = ["ready", "working", "error", "warn"];
    var TOAST_DEFAULT_MS = 2500;
    var REDUCED_MOTION = (function () {
        try {
            return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        } catch (e) {
            return false;
        }
    })();

    // --- HTMX: swap 4xx responses so _error.html renders inline --------------

    document.addEventListener("htmx:beforeSwap", function (ev) {
        if (ev.detail && ev.detail.xhr && ev.detail.xhr.status === 400) {
            ev.detail.shouldSwap = true;
            ev.detail.isError = false;
        }
    });

    // --- tooltip viewport-flip ----------------------------------------------

    function updateTipFlip(tip) {
        var rect = tip.getBoundingClientRect();
        tip.classList.toggle("tip-below", rect.top < 120);
    }

    function bindTipFlip(root) {
        var scope = root || document;
        if (!scope.querySelectorAll) return;
        scope.querySelectorAll(".tip").forEach(function (tip) {
            if (tip.dataset.tipFlipBound === "1") return;
            tip.dataset.tipFlipBound = "1";
            var handler = function () { updateTipFlip(tip); };
            tip.addEventListener("mouseenter", handler);
            tip.addEventListener("focus", handler);
        });
    }

    // --- Lucide re-init after fragment swap ----------------------------------

    function reinitLucide() {
        try {
            if (window.__lucide && window.__lucide.createIcons) {
                window.__lucide.createIcons({ icons: window.__lucide.icons });
            } else if (window.lucide && window.lucide.createIcons) {
                // Fall back to older Lucide global API.
                window.lucide.createIcons();
            }
        } catch (e) {
            // Lucide is optional; never break the page over icon init.
            if (window.console && console.warn) {
                console.warn("Lucide re-init failed:", e);
            }
        }
    }

    // --- Status indicator ----------------------------------------------------

    function setStatus(text, kind) {
        var el = document.getElementById("status-text");
        if (el) el.textContent = text;
        var dot = document.querySelector(".status-dot, [data-status-dot]");
        if (!dot) return;
        STATUS_DOT_CLASSES.forEach(function (c) { dot.classList.remove(c); });
        if (kind) dot.classList.add(kind);
    }

    // --- Toast helper --------------------------------------------------------

    var TOAST_ICONS = {
        info: "info",
        success: "check-circle-2",
        warn: "alert-triangle",
        error: "x-circle",
    };

    function toast(kind, text, ms) {
        var wrap = document.getElementById("toast-container");
        if (!wrap) {
            // No container — fall back to console so callers don't silently lose the message.
            if (window.console && console.log) console.log("[toast " + kind + "]", text);
            return;
        }
        var duration = typeof ms === "number" ? ms : TOAST_DEFAULT_MS;
        var el = document.createElement("div");
        el.className = "toast toast-" + (kind || "info");
        el.setAttribute("role", "status");
        el.setAttribute("aria-live", "polite");

        var iconName = TOAST_ICONS[kind] || "info";
        var iconSpan = document.createElement("span");
        iconSpan.className = "toast-icon";
        var iEl = document.createElement("i");
        iEl.setAttribute("data-lucide", iconName);
        iconSpan.appendChild(iEl);

        var textSpan = document.createElement("span");
        textSpan.className = "toast-text";
        textSpan.textContent = String(text == null ? "" : text);

        el.appendChild(iconSpan);
        el.appendChild(textSpan);
        wrap.appendChild(el);
        reinitLucide();

        // Schedule removal. Use longer linger for reduced-motion users since
        // fade-in/out transitions may be disabled.
        var lifetime = REDUCED_MOTION ? duration : duration;
        var removeTimer = window.setTimeout(function () {
            el.classList.add("toast-leaving");
            var gone = function () {
                if (el.parentNode) el.parentNode.removeChild(el);
            };
            if (REDUCED_MOTION) {
                gone();
            } else {
                window.setTimeout(gone, 220);
            }
        }, lifetime);

        // Allow click-to-dismiss.
        el.addEventListener("click", function () {
            window.clearTimeout(removeTimer);
            if (el.parentNode) el.parentNode.removeChild(el);
        });
    }

    // --- Paired slider + number input binding --------------------------------

    function updateReadout(nameOrCtl, value) {
        // Accept either a param name (string) or a control element.
        var name;
        if (typeof nameOrCtl === "string") {
            name = nameOrCtl;
        } else if (nameOrCtl && nameOrCtl.closest) {
            var controlWrap = nameOrCtl.closest(".control");
            if (controlWrap && controlWrap.dataset.param) {
                name = controlWrap.dataset.param;
            }
        }
        if (!name) return;
        var span = document.querySelector('[data-readout-for="' + name + '"]');
        if (span) span.textContent = String(value);
    }

    function bindNumCtls(root) {
        var ctls = (root || document).querySelectorAll(".num-ctl");
        ctls.forEach(function (ctl) {
            if (ctl.dataset.numCtlBound === "1") return;
            ctl.dataset.numCtlBound = "1";
            var slider = ctl.querySelector("input.num-slider");
            var num = ctl.querySelector("input.num-input");
            if (!slider || !num) return;

            var name = num.getAttribute("name") || "";

            // Initial readout sync.
            updateReadout(name, num.value);

            slider.addEventListener("input", function () {
                num.value = slider.value;
                updateReadout(name, num.value);
            });
            num.addEventListener("input", function () {
                var v = parseFloat(num.value);
                if (!Number.isFinite(v)) {
                    // Still reflect the raw string in the readout.
                    updateReadout(name, num.value);
                    return;
                }
                var lo = parseFloat(slider.min);
                var hi = parseFloat(slider.max);
                var clamped = Math.max(lo, Math.min(hi, v));
                slider.value = String(clamped);
                updateReadout(name, num.value);
            });
        });
    }

    // --- "Generate random ship" ---------------------------------------------
    //
    // Randomizes every parameter within its declared bounds, then submits the
    // form. Tests scan the rendered HTML for a `getElementById('randomize-all')`
    // call so the legacy id keeps working even after the Markup agent strips
    // the inline script; the binding below is the live handler for that case.

    function randomizeAndSubmit() {
        var form = document.querySelector(".gen-form");
        if (!form) return;

        // Seed: full int32 range.
        if (form.seed) {
            form.seed.value = Math.floor(Math.random() * 2147483648);
            try { form.seed.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) { /* noop */ }
        }

        // Numeric inputs: sample uniformly in [slider-lo, slider-hi], snap to step.
        form.querySelectorAll('input[type="number"]').forEach(function (inp) {
            if (inp.name === "seed") return;
            var lo = parseFloat(inp.dataset.sliderLo);
            var hi = parseFloat(inp.dataset.sliderHi);
            if (!Number.isFinite(lo)) lo = parseFloat(inp.min);
            if (!Number.isFinite(hi)) hi = parseFloat(inp.max);
            if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) return;
            var step = parseFloat(inp.step);
            if (!Number.isFinite(step) || step <= 0) step = 1;
            var v = lo + Math.random() * (hi - lo);
            if (step >= 1) {
                v = Math.round(v);
            } else {
                v = Math.round((v - lo) / step) * step + lo;
                v = parseFloat(v.toFixed(4));
            }
            inp.value = String(v);
            try { inp.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) { /* noop */ }
        });

        // Palette: skip the "random" meta so the user sees a concrete palette.
        var pal = form.querySelector('select[name="palette"]');
        if (pal) {
            var palOpts = Array.from(pal.options).filter(function (o) {
                return o.value && o.value !== "random";
            });
            if (palOpts.length) {
                pal.value = palOpts[Math.floor(Math.random() * palOpts.length)].value;
            }
        }

        // Cockpit: uniform over available styles.
        var cockpit = form.querySelector('select[name="cockpit"]');
        if (cockpit && cockpit.options.length) {
            cockpit.value = cockpit.options[
                Math.floor(Math.random() * cockpit.options.length)
            ].value;
        }

        // Structure style: uniform over available archetypes.
        var structureStyle = form.querySelector('select[name="structure_style"]');
        if (structureStyle && structureStyle.options.length) {
            structureStyle.value = structureStyle.options[
                Math.floor(Math.random() * structureStyle.options.length)
            ].value;
        }

        // Wing style: uniform over available silhouettes.
        var wingStyle = form.querySelector('select[name="wing_style"]');
        if (wingStyle && wingStyle.options.length) {
            wingStyle.value = wingStyle.options[
                Math.floor(Math.random() * wingStyle.options.length)
            ].value;
        }

        // Engine glow ring: 50/50.
        var ring = form.querySelector('input[name="engine_glow_ring"]');
        if (ring) ring.checked = Math.random() < 0.5;

        if (typeof form.requestSubmit === "function") {
            form.requestSubmit();
        } else {
            form.submit();
        }
    }

    // --- Canvas init on HTMX swap -------------------------------------------

    function initCanvasInSwap(root) {
        if (!window.shipPreview || typeof window.shipPreview.init !== "function") {
            return;
        }
        var scope = root || document;
        var canvases = scope.querySelectorAll ? scope.querySelectorAll("canvas") : [];
        canvases.forEach(function (canvas) {
            // Prefer the agreed id when present, but also init .preview-canvas for legacy markup.
            if (canvas.id === "viewport-canvas" || canvas.classList.contains("preview-canvas")) {
                try {
                    window.shipPreview.init(canvas);
                } catch (e) {
                    if (window.console && console.warn) console.warn("preview init failed:", e);
                }
            }
        });
    }

    // --- Result metadata wiring (download button, readouts) ------------------

    function extractResultMeta(root) {
        var scope = root || document;
        var inner = scope.querySelector ? scope.querySelector(".result-inner") : null;
        if (!inner) {
            // Fallback: look for the legacy .result/.preview with data-gen-id/data-preview-url.
            var legacy = scope.querySelector ? scope.querySelector(".result") : null;
            if (!legacy) return null;
            return {
                genId: legacy.getAttribute("data-gen-id") || "",
                seed: legacy.getAttribute("data-seed") || "",
                palette: legacy.getAttribute("data-palette") || "",
                blocks: legacy.getAttribute("data-blocks") || "",
                voxels: legacy.getAttribute("data-voxels") || "",
                downloadUrl:
                    (legacy.querySelector('a[href*="/download/"]') || {}).href || "",
                shape: legacy.getAttribute("data-shape") || "",
            };
        }
        return {
            genId: inner.getAttribute("data-gen-id") || "",
            seed: inner.getAttribute("data-seed") || "",
            palette: inner.getAttribute("data-palette") || "",
            blocks: inner.getAttribute("data-blocks") || "",
            voxels: inner.getAttribute("data-voxels") || "",
            downloadUrl: inner.getAttribute("data-download-url") || "",
            shape: inner.getAttribute("data-shape") || "",
        };
    }

    function applyResultMeta(meta) {
        if (!meta) return;
        var setText = function (id, val) {
            var el = document.getElementById(id);
            if (el && val != null && val !== "") el.textContent = String(val);
        };
        setText("ship-id-readout", meta.genId);
        setText("seed-readout", meta.seed);
        setText("palette-readout", meta.palette);
        setText("stat-voxels", meta.voxels || meta.blocks);

        var dl = document.getElementById("btn-download");
        if (dl) {
            if (meta.downloadUrl) {
                dl.setAttribute("href", meta.downloadUrl);
                dl.classList.remove("disabled");
                dl.removeAttribute("aria-disabled");
                dl.removeAttribute("tabindex");
            } else {
                dl.classList.add("disabled");
                dl.setAttribute("aria-disabled", "true");
            }
        }
    }

    // --- Fullscreen ----------------------------------------------------------

    function invokeFullscreen() {
        try {
            if (window.shipPreview && typeof window.shipPreview.fullscreen === "function") {
                window.shipPreview.fullscreen();
                return;
            }
        } catch (e) { /* fall through */ }
        // Fallback: use the Fullscreen API on the viewport container directly.
        var vp = document.getElementById("viewport") || document.querySelector(".preview");
        if (!vp) return;
        if (document.fullscreenElement) {
            if (document.exitFullscreen) document.exitFullscreen();
        } else if (vp.requestFullscreen) {
            vp.requestFullscreen();
        }
    }

    // --- FPS / voxel stat hookup --------------------------------------------

    function bindStatsListener() {
        document.addEventListener("ship-preview-stats", function (ev) {
            var d = ev && ev.detail;
            if (!d) return;
            var fpsEl = document.getElementById("stat-fps");
            if (fpsEl && typeof d.fps === "number") {
                fpsEl.textContent = d.fps.toFixed(0);
            }
            var vxEl = document.getElementById("stat-voxels");
            if (vxEl && typeof d.voxelCount === "number") {
                vxEl.textContent = String(d.voxelCount);
            }
        });
    }

    // --- View preset buttons ------------------------------------------------

    function bindViewButtons() {
        var map = [
            ["btn-view-persp", "persp"],
            ["btn-view-top", "top"],
            ["btn-view-front", "front"],
            ["btn-view-side", "side"],
        ];
        map.forEach(function (pair) {
            var btn = document.getElementById(pair[0]);
            if (!btn || btn.dataset.viewBound === "1") return;
            btn.dataset.viewBound = "1";
            btn.addEventListener("click", function () {
                if (window.shipPreview && typeof window.shipPreview.setView === "function") {
                    try { window.shipPreview.setView(pair[1]); } catch (e) { /* noop */ }
                }
            });
        });
        var reset = document.getElementById("btn-view-reset");
        if (reset && reset.dataset.viewBound !== "1") {
            reset.dataset.viewBound = "1";
            reset.addEventListener("click", function () {
                if (window.shipPreview && typeof window.shipPreview.resetCamera === "function") {
                    try { window.shipPreview.resetCamera(); } catch (e) { /* noop */ }
                }
            });
        }
    }

    // --- Top-bar button bindings --------------------------------------------

    function bindTopbar() {
        var gen = document.getElementById("btn-generate");
        if (gen && gen.dataset.genBound !== "1") {
            gen.dataset.genBound = "1";
            gen.addEventListener("click", function () {
                var form = document.querySelector(".gen-form");
                if (!form) return;
                if (typeof form.requestSubmit === "function") {
                    form.requestSubmit();
                } else {
                    form.submit();
                }
            });
        }

        // The canonical random button is #btn-random; #randomize-all is the
        // legacy id the Python tests still look up via getElementById.
        ["btn-random", "randomize-all"].forEach(function (id) {
            var btn = document.getElementById(id);
            if (!btn || btn.dataset.randomBound === "1") return;
            btn.dataset.randomBound = "1";
            btn.addEventListener("click", randomizeAndSubmit);
        });

        var seed = document.getElementById("randomize-seed");
        if (seed && seed.dataset.seedBound !== "1") {
            seed.dataset.seedBound = "1";
            seed.addEventListener("click", function () {
                var field = document.getElementById("seed");
                if (!field) return;
                field.value = Math.floor(Math.random() * 2147483648);
                try { field.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) { /* noop */ }
            });
        }

        var fs = document.getElementById("btn-fullscreen");
        if (fs && fs.dataset.fsBound !== "1") {
            fs.dataset.fsBound = "1";
            fs.addEventListener("click", invokeFullscreen);
        }
    }

    // --- HTMX lifecycle wiring ----------------------------------------------

    function bindHtmxLifecycle() {
        document.addEventListener("htmx:beforeRequest", function (ev) {
            var tgt = ev && ev.detail && ev.detail.elt;
            if (!tgt) return;
            if (tgt.matches && tgt.matches(".gen-form, .gen-form *")) {
                setStatus("GENERATING\u2026", "working");
            }
        });

        document.body.addEventListener("htmx:afterSwap", function (ev) {
            var targetId = ev && ev.target && ev.target.id;
            if (targetId === "result-panel") {
                setStatus("READY", "ready");
            }
            bindTipFlip(ev.target || document);
            bindNumCtls(ev.target || document);
            initCanvasInSwap(ev.target || document);
            reinitLucide();
            var meta = extractResultMeta(ev.target || document);
            if (meta) {
                applyResultMeta(meta);
                toast("success", "READY");
            }
        });

        document.addEventListener("htmx:responseError", function () {
            setStatus("ERROR", "error");
            toast("error", "GENERATION FAILED");
        });

        document.addEventListener("htmx:sendError", function () {
            setStatus("ERROR", "error");
            toast("error", "NETWORK ERROR");
        });
    }

    // --- Boot ----------------------------------------------------------------

    function boot() {
        bindTipFlip(document);
        bindNumCtls(document);
        bindTopbar();
        bindViewButtons();
        bindStatsListener();
        bindHtmxLifecycle();
        reinitLucide();
        setStatus("READY", "ready");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }

    // --- Public API ----------------------------------------------------------

    window.ui = window.ui || {};
    window.ui.toast = toast;
    window.ui.setStatus = setStatus;
    window.ui.reinitLucide = reinitLucide;
    window.ui.randomizeAndSubmit = randomizeAndSubmit;
    window.ui.bindNumCtls = bindNumCtls;
})();
