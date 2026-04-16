// Spaceship Generator — client-side enhancements.
//
// The preview viewport (orbit/pan/zoom) is handled by preview.js as a WebGL
// canvas. This file keeps the small HTMX bridges and the tooltip flip logic;
// the server-orbit image-swap code that used to live here was removed with
// the WebGL overhaul.

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
        bindTipFlip(document);
    });

    // Re-bind after HTMX swaps fresh markup into the page.
    document.body.addEventListener("htmx:afterSwap", function (ev) {
        bindTipFlip(ev.target || document);
    });
})();
