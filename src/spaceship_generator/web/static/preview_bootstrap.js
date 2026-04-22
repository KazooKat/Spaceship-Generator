// preview_bootstrap.js — HTMX lifecycle wiring, canvas init, window.shipPreview facade.
// Depends on preview_renderer.js (window.PreviewRenderer) loaded before this file.

(function () {
    "use strict";

    function showFallback(canvas) {
        window.PreviewRenderer.showFallback(canvas);
    }

    function initCanvas(canvas) {
        if (!canvas) return;
        if (canvas.__renderer && typeof canvas.__renderer.destroy === "function") {
            try { canvas.__renderer.destroy(); } catch (e) { /* ignore */ }
            canvas.__renderer = null;
            delete canvas.dataset.previewBound;
            delete canvas.dataset.previewReady;
        }
        if (canvas.dataset.previewBound === "1") return;
        canvas.dataset.previewBound = "1";

        const voxelsUrl = canvas.dataset.voxelsUrl;
        if (!voxelsUrl) return;

        const t0 = performance.now();
        fetch(voxelsUrl, { credentials: "same-origin" })
            .then(function (r) {
                if (!r.ok) throw new Error("voxels fetch " + r.status);
                return r.json();
            })
            .then(function (data) {
                const r = window.PreviewRenderer.makeRenderer(canvas, data);
                if (!r) { showFallback(canvas); return; }
                canvas.__renderer = r;
                canvas.__previewMs = performance.now() - t0;
                canvas.dataset.previewReady = "1";
                bindGlobalShipPreview(r);
                if (typeof r.fireLoaded === "function") {
                    try { r.fireLoaded(); } catch (e) { /* best-effort */ }
                }
            })
            .catch(function (err) {
                console.warn("preview load failed:", err);
                showFallback(canvas);
            });
    }

    function initAll(root) {
        const scope = root || document;
        scope.querySelectorAll(".preview-canvas[data-voxels-url]").forEach(initCanvas);
    }

    window.SpaceshipPreview = { initAll: initAll, initCanvas: initCanvas };

    // --- window.shipPreview (HUD / Interactions API) -------------------------
    let activeRenderer = null;
    const pendingFrameSubs = [];
    const pendingLoadedSubs = [];

    function bindGlobalShipPreview(renderer) {
        activeRenderer = renderer;
        for (let i = 0; i < pendingFrameSubs.length; i++) {
            try { renderer.onFrame(pendingFrameSubs[i]); } catch (e) { /* ignore */ }
        }
        for (let i = 0; i < pendingLoadedSubs.length; i++) {
            try { renderer.onLoaded(pendingLoadedSubs[i]); } catch (e) { /* ignore */ }
        }
    }

    window.shipPreview = {
        setView: function (preset) {
            if (activeRenderer && typeof activeRenderer.setView === "function") activeRenderer.setView(preset);
        },
        resetCamera: function () {
            if (activeRenderer && typeof activeRenderer.resetCamera === "function") activeRenderer.resetCamera();
        },
        getCamera: function () {
            return (activeRenderer && typeof activeRenderer.getCamera === "function") ? activeRenderer.getCamera() : null;
        },
        getStats: function () {
            return (activeRenderer && typeof activeRenderer.getStats === "function") ? activeRenderer.getStats() : null;
        },
        snapshotPNG: function (size) {
            if (activeRenderer && typeof activeRenderer.snapshotPNG === "function") return activeRenderer.snapshotPNG(size);
            return "";
        },
        fullscreen: function () {
            if (activeRenderer && typeof activeRenderer.fullscreen === "function") return activeRenderer.fullscreen();
            const viewport = document.getElementById("viewport");
            if (viewport && typeof viewport.requestFullscreen === "function") {
                try { viewport.requestFullscreen(); } catch (e) { /* ignore */ }
                return true;
            }
            return false;
        },
        onFrame: function (cb) {
            if (typeof cb !== "function") return function () {};
            pendingFrameSubs.push(cb);
            if (activeRenderer && typeof activeRenderer.onFrame === "function") activeRenderer.onFrame(cb);
            return function () {
                const idx = pendingFrameSubs.indexOf(cb);
                if (idx !== -1) pendingFrameSubs.splice(idx, 1);
            };
        },
        onLoaded: function (cb) {
            if (typeof cb !== "function") return function () {};
            pendingLoadedSubs.push(cb);
            if (activeRenderer && typeof activeRenderer.onLoaded === "function") activeRenderer.onLoaded(cb);
            return function () {
                const idx = pendingLoadedSubs.indexOf(cb);
                if (idx !== -1) pendingLoadedSubs.splice(idx, 1);
            };
        },
    };

    document.addEventListener("DOMContentLoaded", function () { initAll(document); });
    document.body.addEventListener("htmx:afterSwap", function (ev) { initAll(ev.target || document); });
})();
