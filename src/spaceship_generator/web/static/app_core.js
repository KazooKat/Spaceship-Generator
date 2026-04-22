// app_core.js — core UI utilities: HTMX bridge, tooltip flip, Lucide init,
// status indicator, toast helper, and paired slider/number-input binding.
// Exposes window.ui with toast, setStatus, reinitLucide, bindNumCtls.

(function () {
    "use strict";

    var STATUS_DOT_CLASSES = ["ready", "working", "error", "warn"];
    var TOAST_DEFAULT_MS = 2500;
    var REDUCED_MOTION = (function () {
        try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; }
    })();

    // --- HTMX: swap 4xx responses so _error.html renders inline --------------
    document.addEventListener("htmx:beforeSwap", function (ev) {
        if (ev.detail && ev.detail.xhr && ev.detail.xhr.status === 400) {
            ev.detail.shouldSwap = true;
            ev.detail.isError = false;
        }
    });

    // --- Tooltip viewport-flip ----------------------------------------------
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
                window.lucide.createIcons();
            }
        } catch (e) {
            if (window.console && console.warn) console.warn("Lucide re-init failed:", e);
        }
    }

    // --- Status indicator ---------------------------------------------------
    function setStatus(text, kind) {
        var el = document.getElementById("status-text");
        if (el) el.textContent = text;
        var dot = document.querySelector(".status-dot, [data-status-dot]");
        if (!dot) return;
        STATUS_DOT_CLASSES.forEach(function (c) { dot.classList.remove(c); });
        if (kind) dot.classList.add(kind);
    }

    // --- Toast helper -------------------------------------------------------
    var TOAST_ICONS = { info: "info", success: "check-circle-2", warn: "alert-triangle", error: "x-circle" };

    function toast(kind, text, ms) {
        var wrap = document.getElementById("toast-container");
        if (!wrap) {
            if (window.console && console.log) console.log("[toast " + kind + "]", text);
            return;
        }
        var duration = typeof ms === "number" ? ms : TOAST_DEFAULT_MS;
        var el = document.createElement("div");
        el.className = "toast toast-" + (kind || "info");
        el.setAttribute("role", "status");
        el.setAttribute("aria-live", "polite");

        var iconSpan = document.createElement("span");
        iconSpan.className = "toast-icon";
        var iEl = document.createElement("i");
        iEl.setAttribute("data-lucide", TOAST_ICONS[kind] || "info");
        iconSpan.appendChild(iEl);

        var textSpan = document.createElement("span");
        textSpan.className = "toast-text";
        textSpan.textContent = String(text == null ? "" : text);

        el.appendChild(iconSpan);
        el.appendChild(textSpan);
        wrap.appendChild(el);
        reinitLucide();

        var removeTimer = window.setTimeout(function () {
            el.classList.add("toast-leaving");
            var gone = function () { if (el.parentNode) el.parentNode.removeChild(el); };
            if (REDUCED_MOTION) { gone(); } else { window.setTimeout(gone, 220); }
        }, duration);

        el.addEventListener("click", function () {
            window.clearTimeout(removeTimer);
            if (el.parentNode) el.parentNode.removeChild(el);
        });
    }

    // --- Paired slider + number input binding --------------------------------
    function updateReadout(nameOrCtl, value) {
        var name;
        if (typeof nameOrCtl === "string") {
            name = nameOrCtl;
        } else if (nameOrCtl && nameOrCtl.closest) {
            var controlWrap = nameOrCtl.closest(".control");
            if (controlWrap && controlWrap.dataset.param) name = controlWrap.dataset.param;
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
            updateReadout(name, num.value);
            slider.addEventListener("input", function () {
                num.value = slider.value;
                updateReadout(name, num.value);
            });
            num.addEventListener("input", function () {
                var v = parseFloat(num.value);
                if (!Number.isFinite(v)) { updateReadout(name, num.value); return; }
                var lo = parseFloat(slider.min), hi = parseFloat(slider.max);
                var clamped = Math.max(lo, Math.min(hi, v));
                slider.value = String(clamped);
                updateReadout(name, num.value);
            });
        });
    }

    // --- Expose on window.ui ------------------------------------------------
    window.ui = window.ui || {};
    window.ui.toast = toast;
    window.ui.setStatus = setStatus;
    window.ui.reinitLucide = reinitLucide;
    window.ui.bindNumCtls = bindNumCtls;
    window.ui.bindTipFlip = bindTipFlip;
})();
