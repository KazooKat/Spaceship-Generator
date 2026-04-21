// Spaceship Generator — debounced live-preview fetcher.
//
// Responsibilities:
//   * Gate auto-refresh behind #live-preview-toggle (a checkbox persisted
//     in localStorage; default off so current UX is unchanged).
//   * Listen for input/change on the generator form, debounce 500ms, then
//     fetch /preview-lite?<current form> and swap #live-preview-img.src.
//   * Show a small spinner during fetch by toggling .htmx-request on the
//     enclosing .progress-bar (reuses existing styling in style.css).
//
// No build tooling, no new deps. Safe on HTMX swaps (sidebar is not
// swap target but we bind idempotently anyway).
(function () {
    "use strict";

    var DEBOUNCE_MS = 500;
    var STORAGE_KEY = "shipforge.live-preview";
    var ENDPOINT = "/preview-lite";

    function byId(id) { return document.getElementById(id); }

    // Read persisted toggle state. Any parse hiccup -> default off so a
    // corrupted storage value can't silently flood the server.
    function loadToggle() {
        try { return window.localStorage.getItem(STORAGE_KEY) === "1"; }
        catch (e) { return false; }
    }
    function saveToggle(on) {
        try { window.localStorage.setItem(STORAGE_KEY, on ? "1" : "0"); }
        catch (e) { /* noop — private mode */ }
    }

    // Build a query string from the form's named inputs. Skip empties so
    // the backend sees "missing" rather than an empty-string coerced to 0.
    function buildQuery(form) {
        var data = new FormData(form);
        var parts = [];
        data.forEach(function (value, key) {
            if (value === "" || value === null) return;
            parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(value));
        });
        // Checkboxes that are unchecked are not in FormData; the server
        // already treats missing = false, so no special handling needed.
        return parts.join("&");
    }

    function setSpinner(on) {
        var bar = byId("live-preview-spinner");
        if (!bar) return;
        bar.classList.toggle("htmx-request", !!on);
    }

    var inFlight = null;
    function refresh(form, img) {
        var qs = buildQuery(form);
        if (!qs) return;
        // Cancel any earlier pending fetch — only the latest matters.
        if (inFlight && typeof inFlight.abort === "function") {
            try { inFlight.abort(); } catch (e) { /* noop */ }
        }
        var ctrl = (typeof AbortController === "function") ? new AbortController() : null;
        inFlight = ctrl;
        setSpinner(true);
        var url = ENDPOINT + "?" + qs;
        fetch(url, ctrl ? { signal: ctrl.signal } : undefined)
            .then(function (resp) {
                if (!resp.ok) throw new Error("preview-lite " + resp.status);
                return resp.blob();
            })
            .then(function (blob) {
                // Use a blob URL instead of URL= to avoid re-downloading the
                // same PNG from the browser cache a second time for <img>.
                if (img.dataset.objUrl) {
                    try { URL.revokeObjectURL(img.dataset.objUrl); } catch (e) {}
                }
                var ou = URL.createObjectURL(blob);
                img.dataset.objUrl = ou;
                img.src = ou;
                // Refresh palette swatches after each preview load so the strip
                // reflects any cached real colors (populated by polish.js after
                // a full generate) without waiting for the user to click Generate.
                if (window.shipPolish && typeof window.shipPolish.renderSwatches === "function") {
                    try { window.shipPolish.renderSwatches(); } catch (e) { /* noop */ }
                }
            })
            .catch(function () { /* silent — debounced spam is normal */ })
            .then(function () { setSpinner(false); inFlight = null; });
    }

    function debounce(fn, ms) {
        var t = null;
        return function () {
            var self = this, args = arguments;
            if (t) clearTimeout(t);
            t = setTimeout(function () { fn.apply(self, args); }, ms);
        };
    }

    function init() {
        var toggle = byId("live-preview-toggle");
        var img = byId("live-preview-img");
        var form = document.querySelector(".gen-form");
        if (!toggle || !img || !form) return;
        // Seed toggle state from storage.
        toggle.checked = loadToggle();
        toggle.addEventListener("change", function () {
            saveToggle(!!toggle.checked);
            if (toggle.checked) refresh(form, img);
        });
        var run = debounce(function () {
            if (!toggle.checked) return;
            refresh(form, img);
        }, DEBOUNCE_MS);
        form.addEventListener("input", run);
        form.addEventListener("change", run);
        // If the user turned the toggle on before page load (persisted
        // state), kick off an initial render.
        if (toggle.checked) refresh(form, img);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
