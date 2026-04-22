// app_ui.js — UI interactions: randomize, canvas init, result metadata,
// fullscreen, stats listener, view presets, topbar buttons, HTMX lifecycle,
// and boot sequence.
// Depends on app_core.js (window.ui) loaded before this file.

(function () {
    "use strict";

    // --- "Generate random ship" ---------------------------------------------
    function randomizeAndSubmit() {
        var form = document.querySelector(".gen-form");
        if (!form) return;

        if (form.seed) {
            form.seed.value = Math.floor(Math.random() * 2147483648);
            try { form.seed.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) { /* noop */ }
        }

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

        var pal = form.querySelector('select[name="palette"]');
        if (pal) {
            var palOpts = Array.from(pal.options).filter(function (o) { return o.value && o.value !== "random"; });
            if (palOpts.length) pal.value = palOpts[Math.floor(Math.random() * palOpts.length)].value;
        }

        var cockpit = form.querySelector('select[name="cockpit"]');
        if (cockpit && cockpit.options.length) {
            cockpit.value = cockpit.options[Math.floor(Math.random() * cockpit.options.length)].value;
        }

        var structureStyle = form.querySelector('select[name="structure_style"]');
        if (structureStyle && structureStyle.options.length) {
            structureStyle.value = structureStyle.options[Math.floor(Math.random() * structureStyle.options.length)].value;
        }

        var wingStyle = form.querySelector('select[name="wing_style"]');
        if (wingStyle && wingStyle.options.length) {
            wingStyle.value = wingStyle.options[Math.floor(Math.random() * wingStyle.options.length)].value;
        }

        var ring = form.querySelector('input[name="engine_glow_ring"]');
        if (ring) ring.checked = Math.random() < 0.5;

        if (typeof form.requestSubmit === "function") { form.requestSubmit(); } else { form.submit(); }
    }

    // --- Canvas init on HTMX swap -------------------------------------------
    function initCanvasInSwap(root) {
        if (!window.shipPreview || typeof window.shipPreview.init !== "function") return;
        var scope = root || document;
        var canvases = scope.querySelectorAll ? scope.querySelectorAll("canvas") : [];
        canvases.forEach(function (canvas) {
            if (canvas.id === "viewport-canvas" || canvas.classList.contains("preview-canvas")) {
                try { window.shipPreview.init(canvas); } catch (e) {
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
            var legacy = scope.querySelector ? scope.querySelector(".result") : null;
            if (!legacy) return null;
            return {
                genId: legacy.getAttribute("data-gen-id") || "",
                seed: legacy.getAttribute("data-seed") || "",
                palette: legacy.getAttribute("data-palette") || "",
                blocks: legacy.getAttribute("data-blocks") || "",
                voxels: legacy.getAttribute("data-voxels") || "",
                downloadUrl: (legacy.querySelector('a[href*="/download/"]') || {}).href || "",
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
                window.shipPreview.fullscreen(); return;
            }
        } catch (e) { /* fall through */ }
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
            if (fpsEl && typeof d.fps === "number") fpsEl.textContent = d.fps.toFixed(0);
            var vxEl = document.getElementById("stat-voxels");
            if (vxEl && typeof d.voxelCount === "number") vxEl.textContent = String(d.voxelCount);
        });
    }

    // --- View preset buttons ------------------------------------------------
    function bindViewButtons() {
        var map = [
            ["btn-view-persp", "persp"], ["btn-view-top", "top"],
            ["btn-view-front", "front"], ["btn-view-side", "side"],
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
                if (typeof form.requestSubmit === "function") { form.requestSubmit(); } else { form.submit(); }
            });
        }

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
                window.ui.setStatus("GENERATING\u2026", "working");
            }
        });

        document.body.addEventListener("htmx:afterSwap", function (ev) {
            var targetId = ev && ev.target && ev.target.id;
            if (targetId === "result-panel") window.ui.setStatus("READY", "ready");
            window.ui.bindTipFlip(ev.target || document);
            window.ui.bindNumCtls(ev.target || document);
            initCanvasInSwap(ev.target || document);
            window.ui.reinitLucide();
            var meta = extractResultMeta(ev.target || document);
            if (meta) { applyResultMeta(meta); window.ui.toast("success", "READY"); }
        });

        document.addEventListener("htmx:responseError", function () {
            window.ui.setStatus("ERROR", "error");
            window.ui.toast("error", "GENERATION FAILED");
        });

        document.addEventListener("htmx:sendError", function () {
            window.ui.setStatus("ERROR", "error");
            window.ui.toast("error", "NETWORK ERROR");
        });
    }

    // --- Palette swatches ----------------------------------------------------
    var paletteColors = {};

    function renderSwatches(paletteName) {
        var strip = document.getElementById("palette-swatches");
        if (!strip) return;
        strip.innerHTML = "";
        var cols = paletteColors[paletteName];
        if (!cols) return;
        for (var role in cols) {
            if (!Object.prototype.hasOwnProperty.call(cols, role)) continue;
            var s = document.createElement("span");
            s.className = "palette-swatch";
            s.style.backgroundColor = cols[role];
            s.title = role;
            strip.appendChild(s);
        }
    }

    function bindPaletteSwatches() {
        var sel = document.getElementById("palette");
        if (!sel) return;
        // Render immediately for the current selection.
        renderSwatches(sel.value);
        sel.addEventListener("change", function () {
            renderSwatches(sel.value);
        });
    }

    function fetchPaletteColors() {
        fetch("/api/palettes")
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (data && data.colors) {
                    paletteColors = data.colors;
                    // Render swatches now that colors are loaded.
                    var sel = document.getElementById("palette");
                    if (sel) renderSwatches(sel.value);
                }
            })
            .catch(function () { /* non-fatal — swatches stay empty */ });
    }

    // --- Boot ----------------------------------------------------------------
    function boot() {
        window.ui.bindTipFlip(document);
        window.ui.bindNumCtls(document);
        bindTopbar();
        bindViewButtons();
        bindStatsListener();
        bindHtmxLifecycle();
        bindPaletteSwatches();
        fetchPaletteColors();
        window.ui.reinitLucide();
        window.ui.setStatus("READY", "ready");
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }

    // --- Extend public API --------------------------------------------------
    window.ui.randomizeAndSubmit = randomizeAndSubmit;
})();
