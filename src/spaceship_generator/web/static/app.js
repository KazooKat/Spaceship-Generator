// Spaceship Generator — client-side enhancements.
//
// Preview interaction model:
//   * Left-drag                   → orbit camera (server re-renders via ?elev=&azim=)
//   * Right-drag OR shift+left-drag OR middle-drag → pan (CSS translate)
//   * Scroll wheel                → zoom (CSS scale, cursor-anchored)
//   * Double-click                → reset orbit, pan, and zoom
//
// Also re-initializes after HTMX swaps fresh markup into the result panel.

(function () {
    "use strict";

    // Make HTMX swap 4xx responses too so our _error.html partial renders
    // inline instead of being silently dropped.
    document.addEventListener("htmx:beforeSwap", function (ev) {
        if (ev.detail.xhr && ev.detail.xhr.status === 400) {
            ev.detail.shouldSwap = true;
            ev.detail.isError = false;
        }
    });

    const DEFAULT_ELEV = 22.0;
    const DEFAULT_AZIM = -62.0;
    const ELEV_MIN = -89.0;
    const ELEV_MAX = 89.0;
    const DRAG_SENSITIVITY = 0.5; // degrees per pixel
    const RENDER_DEBOUNCE_MS = 120;
    const ZOOM_MIN = 0.5;
    const ZOOM_MAX = 6.0;
    const ZOOM_STEP = 0.0015; // per wheel deltaY unit

    function clamp(v, lo, hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    function attachOrbit(previewEl) {
        if (!previewEl || previewEl.dataset.orbitBound === "1") return;
        previewEl.dataset.orbitBound = "1";

        const img = previewEl.querySelector(".preview-img");
        const baseUrl = previewEl.dataset.previewUrl;
        if (!img || !baseUrl) return;

        const parsedElev = parseFloat(previewEl.dataset.elev);
        const parsedAzim = parseFloat(previewEl.dataset.azim);
        let elev = Number.isFinite(parsedElev) ? parsedElev : DEFAULT_ELEV;
        let azim = Number.isFinite(parsedAzim) ? parsedAzim : DEFAULT_AZIM;
        let panX = 0;
        let panY = 0;
        let zoom = 1.0;

        // "mode" is set on mousedown based on which button/modifier was used:
        //   null    → not dragging
        //   "orbit" → left-drag: update elev/azim and re-render
        //   "pan"   → right/middle/shift+left-drag: translate img via CSS
        let mode = null;
        let lastX = 0;
        let lastY = 0;
        let pendingTimer = null;

        function applyTransform() {
            img.style.transform =
                "translate(" + panX.toFixed(1) + "px, " + panY.toFixed(1) + "px) " +
                "scale(" + zoom.toFixed(3) + ")";
            img.style.transformOrigin = "center center";
        }

        function buildUrl() {
            // Include view params so the server re-renders for this camera.
            const u = new URL(baseUrl, window.location.origin);
            u.searchParams.set("elev", elev.toFixed(1));
            u.searchParams.set("azim", azim.toFixed(1));
            return u.pathname + "?" + u.searchParams.toString();
        }

        function scheduleRerender() {
            if (pendingTimer) clearTimeout(pendingTimer);
            pendingTimer = setTimeout(function () {
                pendingTimer = null;
                img.src = buildUrl();
            }, RENDER_DEBOUNCE_MS);
        }

        function resetView() {
            elev = DEFAULT_ELEV;
            azim = DEFAULT_AZIM;
            panX = 0;
            panY = 0;
            zoom = 1.0;
            previewEl.dataset.elev = String(elev);
            previewEl.dataset.azim = String(azim);
            applyTransform();
            scheduleRerender();
        }

        // Suppress the native context menu so right-drag is usable for panning.
        previewEl.addEventListener("contextmenu", function (ev) {
            ev.preventDefault();
        });

        previewEl.addEventListener("mousedown", function (ev) {
            // Right button, middle button, or shift+left → pan.
            const isPan =
                ev.button === 1 ||
                ev.button === 2 ||
                (ev.button === 0 && ev.shiftKey);
            mode = isPan ? "pan" : (ev.button === 0 ? "orbit" : null);
            if (!mode) return;
            lastX = ev.clientX;
            lastY = ev.clientY;
            previewEl.classList.add("dragging");
            if (mode === "pan") previewEl.classList.add("panning");
            ev.preventDefault();
        });

        window.addEventListener("mousemove", function (ev) {
            if (!mode) return;
            const dx = ev.clientX - lastX;
            const dy = ev.clientY - lastY;
            lastX = ev.clientX;
            lastY = ev.clientY;

            if (mode === "orbit") {
                azim = ((azim - dx * DRAG_SENSITIVITY) + 540) % 360 - 180;
                elev = clamp(elev + dy * DRAG_SENSITIVITY, ELEV_MIN, ELEV_MAX);
                previewEl.dataset.elev = elev.toFixed(1);
                previewEl.dataset.azim = azim.toFixed(1);
                scheduleRerender();
            } else if (mode === "pan") {
                panX += dx;
                panY += dy;
                applyTransform();
            }
        });

        window.addEventListener("mouseup", function () {
            if (!mode) return;
            mode = null;
            previewEl.classList.remove("dragging");
            previewEl.classList.remove("panning");
        });

        // Scroll wheel → zoom, anchored to cursor position so the point under
        // the mouse stays put.
        previewEl.addEventListener("wheel", function (ev) {
            ev.preventDefault();
            const rect = previewEl.getBoundingClientRect();
            const cx = ev.clientX - rect.left - rect.width / 2;
            const cy = ev.clientY - rect.top - rect.height / 2;
            const prevZoom = zoom;
            const factor = Math.exp(-ev.deltaY * ZOOM_STEP);
            zoom = clamp(zoom * factor, ZOOM_MIN, ZOOM_MAX);
            const ratio = zoom / prevZoom;
            // Keep the point under the cursor stationary during zoom.
            panX = cx - (cx - panX) * ratio;
            panY = cy - (cy - panY) * ratio;
            applyTransform();
        }, { passive: false });

        previewEl.addEventListener("dblclick", resetView);

        applyTransform();
    }

    function initAll(root) {
        const scope = root || document;
        const els = scope.querySelectorAll(".preview[data-preview-url]");
        els.forEach(attachOrbit);
    }

    // --- Tooltip viewport-flip ----------------------------------------------
    //
    // .tip bubbles render above the trigger by default. If the trigger is near
    // the top of the viewport, flip the bubble below instead so it remains
    // visible. Toggled via a CSS class so the stylesheet owns the geometry.
    function updateTipFlip(tip) {
        const rect = tip.getBoundingClientRect();
        // 120px == generous guess for tooltip height + arrow; avoids measuring
        // the ::after pseudo-element (which has no direct geometry access).
        const needsFlip = rect.top < 120;
        tip.classList.toggle("tip-below", needsFlip);
    }

    function bindTipFlip(root) {
        const scope = root || document;
        scope.querySelectorAll(".tip").forEach(function (tip) {
            if (tip.dataset.tipFlipBound === "1") return;
            tip.dataset.tipFlipBound = "1";
            const handler = function () { updateTipFlip(tip); };
            tip.addEventListener("mouseenter", handler);
            tip.addEventListener("focus", handler);
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        initAll(document);
        bindTipFlip(document);
    });

    // Re-bind after HTMX swaps fresh markup into the page.
    document.body.addEventListener("htmx:afterSwap", function (ev) {
        initAll(ev.target || document);
        bindTipFlip(ev.target || document);
    });
})();
