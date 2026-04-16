// Spaceship Generator — recent-ship history, backed by localStorage.
//
// Schema:
//   localStorage["shipforge.history.v1"] = JSON.stringify([
//       {
//           genId, seed, palette, shape, blocks,
//           filename, downloadUrl, capturedAt,
//           thumbnailDataUrl?, params?   // params captured from the form
//       },
//       ...
//   ])
// Capped at HISTORY_CAP (30) entries. Newest is last; renderer displays
// reversed.
//
// Exposed as window.shipHistory (not window.history, which is the browser API):
//   captureFromResult(root?)   -> entry | null
//   renderHistoryList(target?) -> void
//   applyEntry(entry|id)       -> bool
//   clearHistory()             -> void
//   list()                     -> [entry]
//   storageKey

(function () {
    "use strict";

    var STORAGE_KEY = "shipforge.history.v1";
    var HISTORY_CAP = 30;
    // Wait ~200ms after an HTMX swap before snapshotting so the WebGL preview
    // has time to decode/render the first frame.
    var SNAPSHOT_DELAY_MS = 220;

    // --- storage helpers -----------------------------------------------------

    function readStore() {
        try {
            var raw = window.localStorage.getItem(STORAGE_KEY);
            if (!raw) return [];
            var parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) {
                if (window.console && console.warn) {
                    console.warn("history: non-array payload in " + STORAGE_KEY + "; resetting");
                }
                writeStore([]);
                return [];
            }
            return parsed;
        } catch (e) {
            if (window.console && console.warn) {
                console.warn("history: failed to parse " + STORAGE_KEY + "; resetting", e);
            }
            try { window.localStorage.removeItem(STORAGE_KEY); } catch (e2) { /* noop */ }
            return [];
        }
    }

    function writeStore(list) {
        try {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
            return true;
        } catch (e) {
            // Likely QuotaExceededError. Trim the list and retry once.
            try {
                if (Array.isArray(list) && list.length > 1) {
                    var trimmed = list.slice(-Math.max(1, Math.floor(list.length / 2)));
                    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
                    return true;
                }
            } catch (e2) { /* noop */ }
            if (window.console && console.warn) {
                console.warn("history: failed to persist " + STORAGE_KEY, e);
            }
            return false;
        }
    }

    // --- result-panel scraping ----------------------------------------------

    function extractResultData(root) {
        var scope = root || document;
        var inner = scope.querySelector ? scope.querySelector(".result-inner") : null;
        var legacy = scope.querySelector ? scope.querySelector(".result") : null;
        var source = inner || legacy;
        if (!source) return null;

        var getAttr = function (name) { return source.getAttribute(name) || ""; };
        var genId = inner ? getAttr("data-gen-id") : (legacy ? legacy.getAttribute("data-gen-id") || "" : "");
        var downloadUrl = inner ? getAttr("data-download-url") : "";
        if (!downloadUrl && legacy) {
            var a = legacy.querySelector('a[href*="/download/"]');
            if (a) downloadUrl = a.href || a.getAttribute("href") || "";
        }

        return {
            genId: genId,
            seed: getAttr("data-seed") || "",
            palette: getAttr("data-palette") || "",
            shape: getAttr("data-shape") || "",
            blocks: getAttr("data-blocks") || "",
            filename: getAttr("data-filename") || "",
            downloadUrl: downloadUrl,
        };
    }

    function getFormParams() {
        // Re-use presets.snapshotParams when available so both stores stay in sync.
        if (window.presets && typeof window.presets.snapshotParams === "function") {
            try { return window.presets.snapshotParams(); } catch (e) { /* fall through */ }
        }
        var form = document.querySelector(".gen-form");
        if (!form) return {};
        var out = {};
        Array.from(form.elements).forEach(function (el) {
            if (!el.name) return;
            if (el.type === "button" || el.type === "submit" || el.type === "reset") return;
            if (el.type === "checkbox") out[el.name] = !!el.checked;
            else out[el.name] = el.value;
        });
        return out;
    }

    function trySnapshotPNG() {
        try {
            if (window.shipPreview && typeof window.shipPreview.snapshotPNG === "function") {
                return window.shipPreview.snapshotPNG(128) || null;
            }
        } catch (e) { /* noop */ }
        return null;
    }

    // --- capture / apply / clear -------------------------------------------

    function captureFromResult(root) {
        var data = extractResultData(root);
        if (!data || !data.genId) return null;

        // Avoid duplicate captures if the same gen_id is already at the tail.
        var list = readStore();
        if (list.length && list[list.length - 1].genId === data.genId) {
            // Still refresh the thumbnail if we got one this time.
            var thumb = trySnapshotPNG();
            if (thumb) {
                list[list.length - 1].thumbnailDataUrl = thumb;
                writeStore(list);
            }
            renderHistoryList();
            return list[list.length - 1];
        }

        var entry = {
            genId: data.genId,
            seed: data.seed,
            palette: data.palette,
            shape: data.shape,
            blocks: data.blocks,
            filename: data.filename,
            downloadUrl: data.downloadUrl,
            capturedAt: new Date().toISOString(),
            thumbnailDataUrl: trySnapshotPNG(),
            params: getFormParams(),
        };

        list.push(entry);
        while (list.length > HISTORY_CAP) list.shift();
        writeStore(list);
        renderHistoryList();
        return entry;
    }

    function applyEntry(entryOrId) {
        var entry = (typeof entryOrId === "string")
            ? readStore().find(function (e) { return e.genId === entryOrId; })
            : entryOrId;
        if (!entry) return false;
        if (window.presets && typeof window.presets.applyParamsToForm === "function" && entry.params) {
            window.presets.applyParamsToForm(entry.params);
        }
        // Re-trigger generation so HTMX swaps a fresh result in.
        var form = document.querySelector(".gen-form");
        if (form) {
            if (typeof form.requestSubmit === "function") {
                form.requestSubmit();
            } else {
                form.submit();
            }
        }
        return true;
    }

    function clearHistory() {
        writeStore([]);
        renderHistoryList();
    }

    function list() {
        return readStore().slice();
    }

    // --- rendering -----------------------------------------------------------

    function formatAge(iso) {
        try {
            var d = new Date(iso);
            if (isNaN(d.getTime())) return "";
            var diffSec = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
            if (diffSec < 60) return diffSec + "s ago";
            var diffMin = Math.floor(diffSec / 60);
            if (diffMin < 60) return diffMin + "m ago";
            var diffHr = Math.floor(diffMin / 60);
            if (diffHr < 24) return diffHr + "h ago";
            var diffDay = Math.floor(diffHr / 24);
            return diffDay + "d ago";
        } catch (e) {
            return "";
        }
    }

    function renderHistoryList(container) {
        var target = container || document.getElementById("history-list");
        if (!target) return;
        var entries = readStore();
        target.innerHTML = "";

        // Header with clear button.
        var header = document.createElement("div");
        header.className = "history-header";
        var title = document.createElement("span");
        title.className = "history-title";
        title.textContent = "RECENT SHIPS (" + entries.length + ")";
        header.appendChild(title);

        var clearBtn = document.createElement("button");
        clearBtn.type = "button";
        clearBtn.className = "btn btn-ghost history-clear";
        clearBtn.setAttribute("aria-label", "Clear history");
        clearBtn.innerHTML = '<i data-lucide="trash-2"></i><span>CLEAR</span>';
        clearBtn.addEventListener("click", function () {
            if (!entries.length) return;
            clearHistory();
            toast("info", "HISTORY CLEARED");
        });
        header.appendChild(clearBtn);
        target.appendChild(header);

        if (!entries.length) {
            var empty = document.createElement("div");
            empty.className = "history-empty";
            empty.textContent = "NO SHIPS YET";
            target.appendChild(empty);
            reinitIcons();
            return;
        }

        entries.slice().reverse().forEach(function (entry) {
            var row = document.createElement("button");
            row.type = "button";
            row.className = "history-row";
            row.setAttribute("data-gen-id", entry.genId);
            row.setAttribute("aria-label", "Re-apply ship " + (entry.seed || entry.genId));

            // Thumbnail (or palette-swatch fallback).
            var thumbWrap = document.createElement("span");
            thumbWrap.className = "history-thumb";
            if (entry.thumbnailDataUrl) {
                var img = document.createElement("img");
                img.src = entry.thumbnailDataUrl;
                img.alt = "";
                img.width = 48;
                img.height = 48;
                img.loading = "lazy";
                img.draggable = false;
                thumbWrap.appendChild(img);
            } else {
                var ph = document.createElement("span");
                ph.className = "history-thumb-fallback";
                ph.textContent = "\u25A0";
                thumbWrap.appendChild(ph);
            }

            var info = document.createElement("span");
            info.className = "history-info";

            var line1 = document.createElement("span");
            line1.className = "history-line history-line-primary";
            line1.textContent = "SEED " + (entry.seed || "?") + "  \u00b7  " +
                String(entry.palette || "").toUpperCase();

            var line2 = document.createElement("span");
            line2.className = "history-line history-line-secondary";
            var ageStr = formatAge(entry.capturedAt);
            var parts = [];
            if (entry.shape) parts.push(entry.shape);
            if (entry.blocks) parts.push(entry.blocks + " blocks");
            if (ageStr) parts.push(ageStr);
            line2.textContent = parts.join("  \u00b7  ");

            info.appendChild(line1);
            info.appendChild(line2);

            row.appendChild(thumbWrap);
            row.appendChild(info);

            row.addEventListener("click", function () {
                applyEntry(entry);
                toast("info", "RE-GENERATING\u2026");
            });

            target.appendChild(row);
        });

        reinitIcons();
    }

    function toast(kind, text) {
        if (window.ui && typeof window.ui.toast === "function") {
            window.ui.toast(kind, text);
        }
    }

    function reinitIcons() {
        if (window.ui && typeof window.ui.reinitLucide === "function") {
            window.ui.reinitLucide();
        }
    }

    // --- event wiring -------------------------------------------------------

    function scheduleCapture(root) {
        // Give the WebGL canvas a tick to render its first frame before we ask
        // it for a snapshot. Also listen for the "ship-preview-loaded" event
        // fired by preview.js; whichever happens first wins.
        var captured = false;
        var doCapture = function () {
            if (captured) return;
            captured = true;
            try { captureFromResult(root); } catch (e) { /* noop */ }
        };
        window.setTimeout(doCapture, SNAPSHOT_DELAY_MS);

        var canvas = (root && root.querySelector)
            ? root.querySelector("#viewport-canvas, .preview-canvas")
            : document.getElementById("viewport-canvas");
        if (canvas) {
            canvas.addEventListener("ship-preview-loaded", doCapture, { once: true });
        }
    }

    function bindHistoryToggle() {
        var toggle = document.getElementById("btn-toggle-history");
        if (!toggle || toggle.dataset.historyBound === "1") return;
        toggle.dataset.historyBound = "1";
        toggle.addEventListener("click", function () {
            // The template's Alpine state owns the visibility toggle; we just
            // make sure the list is freshly rendered whenever it opens.
            renderHistoryList();
        });
    }

    function boot() {
        bindHistoryToggle();
        renderHistoryList();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }

    // HTMX lifecycle: capture after each successful result swap, and re-render
    // once the list markup is (re)available.
    if (document.body) {
        document.body.addEventListener("htmx:afterSwap", function (ev) {
            var targetId = ev && ev.target && ev.target.id;
            if (targetId === "result-panel") {
                scheduleCapture(ev.target);
            }
            bindHistoryToggle();
            // Re-render so the new entry appears immediately even if the user
            // hadn't opened the drawer yet.
            renderHistoryList();
        });
    }

    // --- Public API ---------------------------------------------------------

    window.shipHistory = {
        capture: captureFromResult,
        apply: applyEntry,
        clear: clearHistory,
        list: list,
        render: renderHistoryList,
        storageKey: STORAGE_KEY,
    };
})();
