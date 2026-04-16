// Spaceship Generator — client-side presets, backed by localStorage.
//
// Schema (versioned so we can migrate without blowing away existing user data):
//   localStorage["shipforge.presets.v1"] = JSON.stringify([
//       { id, name, createdAt, params: { seed, palette, length, ... } },
//       ...
//   ])
// Capped at PRESET_CAP (50) entries with LRU (append = newest, evict oldest).
//
// Exposed as window.presets:
//   savePreset(name)            -> preset
//   loadPreset(id)              -> bool
//   deletePreset(id)            -> bool
//   listPresets()               -> [preset]
//   promptSaveName()            -> string | null
//   renderPresetsList(target?)  -> void    (renders into #presets-list)

(function () {
    "use strict";

    var STORAGE_KEY = "shipforge.presets.v1";
    var PRESET_CAP = 50;

    // --- storage helpers -----------------------------------------------------

    function readStore() {
        try {
            var raw = window.localStorage.getItem(STORAGE_KEY);
            if (!raw) return [];
            var parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) {
                // Malformed: log and reset so the page keeps working.
                if (window.console && console.warn) {
                    console.warn("presets: non-array payload in " + STORAGE_KEY + "; resetting");
                }
                writeStore([]);
                return [];
            }
            return parsed;
        } catch (e) {
            if (window.console && console.warn) {
                console.warn("presets: failed to parse " + STORAGE_KEY + "; resetting", e);
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
            if (window.console && console.warn) {
                console.warn("presets: failed to write " + STORAGE_KEY, e);
            }
            return false;
        }
    }

    // --- form <-> params snapshot -------------------------------------------

    function getForm() {
        return document.querySelector(".gen-form");
    }

    function snapshotParams() {
        var form = getForm();
        if (!form) return {};
        var out = {};

        // Numbers, text, selects: read every named control.
        Array.from(form.elements).forEach(function (el) {
            if (!el.name) return;
            if (el.type === "button" || el.type === "submit" || el.type === "reset") return;
            if (el.type === "checkbox") {
                out[el.name] = !!el.checked;
            } else if (el.type === "radio") {
                if (el.checked) out[el.name] = el.value;
            } else {
                out[el.name] = el.value;
            }
        });
        return out;
    }

    function applyParamsToForm(params) {
        var form = getForm();
        if (!form || !params) return;
        Object.keys(params).forEach(function (name) {
            var value = params[name];
            var el = form.elements[name];
            if (!el) return;
            // RadioNodeList when multiple inputs share the name (e.g. radios).
            if (el instanceof RadioNodeList || (el.length && !("value" in el))) {
                Array.from(el).forEach(function (n) {
                    if (n.type === "radio") {
                        n.checked = (String(n.value) === String(value));
                        try { n.dispatchEvent(new Event("change", { bubbles: true })); } catch (e) { /* noop */ }
                    }
                });
                return;
            }
            if (el.type === "checkbox") {
                el.checked = (value === true || value === "true" || value === "on" || value === 1);
            } else {
                el.value = (value == null ? "" : String(value));
            }
            // Let sliders / readouts sync via the input handler in app.js.
            try { el.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) { /* noop */ }
            try { el.dispatchEvent(new Event("change", { bubbles: true })); } catch (e) { /* noop */ }
        });
    }

    // --- id generation -------------------------------------------------------

    function newId() {
        // Timestamp + small random tail; good enough for local-only ids.
        return "p_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 8);
    }

    // --- core API ------------------------------------------------------------

    function savePreset(name) {
        var list = readStore();
        var preset = {
            id: newId(),
            name: (name == null ? "" : String(name)).trim() || "Preset " + (list.length + 1),
            createdAt: new Date().toISOString(),
            params: snapshotParams(),
        };
        list.push(preset);
        // LRU cap: drop the oldest entries when we exceed PRESET_CAP.
        while (list.length > PRESET_CAP) {
            list.shift();
        }
        writeStore(list);
        return preset;
    }

    function loadPreset(id) {
        var list = readStore();
        var found = list.find(function (p) { return p.id === id; });
        if (!found) return false;
        applyParamsToForm(found.params);
        return true;
    }

    function deletePreset(id) {
        var list = readStore();
        var next = list.filter(function (p) { return p.id !== id; });
        if (next.length === list.length) return false;
        writeStore(next);
        return true;
    }

    function listPresets() {
        return readStore().slice();
    }

    function promptSaveName() {
        try {
            var suggested = "Preset " + (readStore().length + 1);
            var name = window.prompt("Preset name:", suggested);
            if (name == null) return null;
            return String(name).trim() || suggested;
        } catch (e) {
            return null;
        }
    }

    // --- rendering -----------------------------------------------------------

    function formatTimestamp(iso) {
        try {
            var d = new Date(iso);
            if (isNaN(d.getTime())) return "";
            var y = d.getFullYear();
            var mo = String(d.getMonth() + 1).padStart(2, "0");
            var da = String(d.getDate()).padStart(2, "0");
            var hh = String(d.getHours()).padStart(2, "0");
            var mi = String(d.getMinutes()).padStart(2, "0");
            return y + "-" + mo + "-" + da + " " + hh + ":" + mi;
        } catch (e) {
            return "";
        }
    }

    function summaryLine(params) {
        if (!params) return "";
        var parts = [];
        if (params.seed != null) parts.push("SEED " + params.seed);
        if (params.palette) parts.push(String(params.palette).toUpperCase());
        if (params.length && params.width && params.height) {
            parts.push(params.width + "x" + params.height + "x" + params.length);
        }
        return parts.join("  \u00b7  ");
    }

    function renderPresetsList(container) {
        var target = container || document.getElementById("presets-list");
        if (!target) return;
        var list = listPresets();
        target.innerHTML = "";

        if (!list.length) {
            var empty = document.createElement("div");
            empty.className = "preset-empty";
            empty.textContent = "NO PRESETS SAVED";
            target.appendChild(empty);
            reinitIcons();
            return;
        }

        // Newest first.
        list.slice().reverse().forEach(function (p) {
            var row = document.createElement("div");
            row.className = "preset-row";
            row.setAttribute("data-preset-id", p.id);

            var info = document.createElement("div");
            info.className = "preset-info";
            var nameEl = document.createElement("div");
            nameEl.className = "preset-name";
            nameEl.textContent = p.name;
            var metaEl = document.createElement("div");
            metaEl.className = "preset-meta";
            metaEl.textContent = formatTimestamp(p.createdAt) + "  " + summaryLine(p.params);
            info.appendChild(nameEl);
            info.appendChild(metaEl);

            var actions = document.createElement("div");
            actions.className = "preset-actions";

            var applyBtn = document.createElement("button");
            applyBtn.type = "button";
            applyBtn.className = "btn btn-ghost preset-apply";
            applyBtn.setAttribute("data-preset-id", p.id);
            applyBtn.setAttribute("aria-label", "Apply preset " + p.name);
            applyBtn.innerHTML = '<i data-lucide="download"></i><span>APPLY</span>';
            applyBtn.addEventListener("click", function () {
                onApply(p.id);
            });

            var delBtn = document.createElement("button");
            delBtn.type = "button";
            delBtn.className = "btn btn-ghost preset-delete";
            delBtn.setAttribute("data-preset-id", p.id);
            delBtn.setAttribute("aria-label", "Delete preset " + p.name);
            delBtn.innerHTML = '<i data-lucide="trash-2"></i><span>DELETE</span>';
            delBtn.addEventListener("click", function () {
                onDelete(p.id);
            });

            actions.appendChild(applyBtn);
            actions.appendChild(delBtn);

            row.appendChild(info);
            row.appendChild(actions);
            target.appendChild(row);
        });

        reinitIcons();
    }

    function onApply(id) {
        if (loadPreset(id)) {
            toast("success", "APPLIED");
            setPresetsOpen(false);
        } else {
            toast("warn", "PRESET MISSING");
        }
    }

    function onDelete(id) {
        if (deletePreset(id)) {
            toast("info", "DELETED");
            renderPresetsList();
        }
    }

    // --- UI glue -------------------------------------------------------------

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

    function setPresetsOpen(value) {
        var root = document.getElementById("app");
        if (!root) return;
        try {
            if (window.Alpine && typeof window.Alpine.$data === "function") {
                var data = window.Alpine.$data(root);
                if (data && "presetsOpen" in data) {
                    data.presetsOpen = value;
                    return;
                }
            }
        } catch (e) { /* fall through */ }
        try {
            if (root.__x_data && "presetsOpen" in root.__x_data) {
                root.__x_data.presetsOpen = value;
                return;
            }
        } catch (e) { /* fall through */ }
        root.dispatchEvent(new CustomEvent("ui:set-state", {
            bubbles: true,
            detail: { key: "presetsOpen", value: value },
        }));
    }

    function bindTopbarButtons() {
        var save = document.getElementById("btn-save-preset");
        if (save && save.dataset.presetBound !== "1") {
            save.dataset.presetBound = "1";
            save.addEventListener("click", function () {
                var name = promptSaveName();
                if (name == null) return;
                savePreset(name);
                toast("success", "SAVED");
                renderPresetsList();
            });
        }

        var list = document.getElementById("btn-presets");
        if (list && list.dataset.presetBound !== "1") {
            list.dataset.presetBound = "1";
            list.addEventListener("click", function () {
                renderPresetsList();
                setPresetsOpen(true);
            });
        }
    }

    function boot() {
        bindTopbarButtons();
        // Render once in case the drawer markup is already present.
        renderPresetsList();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }

    // Re-bind after HTMX swaps (e.g., if the preset drawer markup lives inside
    // a swapped fragment).
    document.body && document.body.addEventListener("htmx:afterSwap", function () {
        bindTopbarButtons();
    });

    // --- Public API ----------------------------------------------------------

    window.presets = {
        save: savePreset,
        load: loadPreset,
        delete: deletePreset,
        list: listPresets,
        promptSaveName: promptSaveName,
        render: renderPresetsList,
        applyParamsToForm: applyParamsToForm,
        snapshotParams: snapshotParams,
        storageKey: STORAGE_KEY,
    };
})();
