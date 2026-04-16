// Spaceship Generator — global keyboard shortcut layer.
//
// Bindings (printable keys are case-insensitive):
//   g -> #btn-generate
//   r -> #btn-random
//   s -> #btn-save-preset
//   p -> #btn-presets
//   h -> #btn-toggle-history
//   f -> #btn-fullscreen
//   d -> #btn-download       (ignored if disabled)
//   1 -> #btn-view-top
//   2 -> #btn-view-front
//   3 -> #btn-view-side
//   4 -> #btn-view-persp
//   0 -> #btn-view-reset
//   ? -> open help modal     (Shift+/)
//   Esc -> close help/presets/history panels and blur input focus
//
// Principles:
//   * Ignored when focus is inside an editable field (inputs, textareas,
//     selects, contenteditable) EXCEPT for Escape which always works.
//   * Resolves the target button via [data-shortcut="KEY"] first, then falls
//     back to the hardcoded id so the layer works even if Markup drops the
//     data-shortcut attribute.
//   * Adds a transient .kbd-flash class on the matched button (120ms) for
//     visual confirmation. Respects prefers-reduced-motion.

(function () {
    "use strict";

    var FLASH_MS = 120;
    var REDUCED_MOTION = (function () {
        try {
            return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        } catch (e) {
            return false;
        }
    })();

    var BINDINGS = {
        "g": { id: "btn-generate" },
        "r": { id: "btn-random" },
        "s": { id: "btn-save-preset" },
        "p": { id: "btn-presets" },
        "h": { id: "btn-toggle-history" },
        "f": { id: "btn-fullscreen" },
        "d": { id: "btn-download", respectDisabled: true },
        "1": { id: "btn-view-top" },
        "2": { id: "btn-view-front" },
        "3": { id: "btn-view-side" },
        "4": { id: "btn-view-persp" },
        "0": { id: "btn-view-reset" },
    };

    function isEditableTarget(el) {
        if (!el || el === document.body) return false;
        var tag = (el.tagName || "").toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select") return true;
        if (el.isContentEditable) return true;
        return false;
    }

    function resolveShortcutButton(key) {
        // Prefer data-shortcut attribute lookup; fall back to the documented id.
        var byData = document.querySelector('[data-shortcut="' + cssEscape(key) + '"]');
        if (byData) return byData;
        var binding = BINDINGS[key];
        if (binding && binding.id) {
            return document.getElementById(binding.id);
        }
        return null;
    }

    // Small CSS.escape polyfill for attribute selectors (covers the chars we use).
    function cssEscape(s) {
        if (window.CSS && typeof window.CSS.escape === "function") {
            return window.CSS.escape(s);
        }
        return String(s).replace(/[^a-zA-Z0-9_-]/g, function (ch) {
            return "\\" + ch;
        });
    }

    function isDisabled(btn) {
        if (!btn) return true;
        if (btn.disabled) return true;
        if (btn.getAttribute("aria-disabled") === "true") return true;
        if (btn.classList && btn.classList.contains("disabled")) return true;
        return false;
    }

    function flashButton(btn) {
        if (!btn || REDUCED_MOTION) return;
        btn.classList.add("kbd-flash");
        window.setTimeout(function () {
            btn.classList.remove("kbd-flash");
        }, FLASH_MS);
    }

    function clickButton(btn, opts) {
        if (!btn) return false;
        if (opts && opts.respectDisabled && isDisabled(btn)) return false;
        flashButton(btn);
        try {
            btn.click();
        } catch (e) {
            // Some anchor-style buttons may throw on .click(); use a focus+activate fallback.
            try {
                btn.focus();
                btn.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
            } catch (e2) { /* noop */ }
        }
        return true;
    }

    function getAppRoot() {
        return document.getElementById("app");
    }

    function setModalState(key, value) {
        // Uses Alpine's public $data API when available; falls back to the
        // legacy __x_data field. Silently noops if neither is present (e.g.,
        // Alpine not yet booted) so a mis-timed keypress never throws.
        var root = getAppRoot();
        if (!root) return false;
        try {
            if (window.Alpine && typeof window.Alpine.$data === "function") {
                var data = window.Alpine.$data(root);
                if (data && key in data) {
                    data[key] = value;
                    return true;
                }
            }
        } catch (e) { /* fall through */ }
        try {
            if (root.__x_data && key in root.__x_data) {
                root.__x_data[key] = value;
                return true;
            }
        } catch (e) { /* fall through */ }
        // Final fallback: dispatch a custom event other components can listen for.
        root.dispatchEvent(new CustomEvent("ui:set-state", {
            bubbles: true,
            detail: { key: key, value: value },
        }));
        return false;
    }

    function closeAllModals() {
        setModalState("helpOpen", false);
        setModalState("presetsOpen", false);
        setModalState("historyOpen", false);
    }

    function openHelp() {
        setModalState("helpOpen", true);
        var helpBtn = document.getElementById("btn-help");
        flashButton(helpBtn);
    }

    // --- keydown handler -----------------------------------------------------

    function handleKey(ev) {
        // Never swallow modified combos that could belong to the browser/OS.
        if (ev.ctrlKey || ev.metaKey || ev.altKey) {
            // ? (Shift+/) is OK; any other modifier means "not our business".
            var isQuestion = ev.key === "?" || (ev.shiftKey && ev.key === "/");
            if (!isQuestion) return;
        }

        var target = ev.target;
        var editable = isEditableTarget(target);

        // Escape: always active. Blurs focus + closes modals.
        if (ev.key === "Escape" || ev.key === "Esc") {
            if (editable && target && typeof target.blur === "function") {
                target.blur();
            }
            closeAllModals();
            return;
        }

        // Everywhere else: let typing through untouched.
        if (editable) return;

        // Help modal shortcut — supports `?` and Shift+/ (the physical keystroke).
        if (ev.key === "?" || (ev.shiftKey && ev.key === "/")) {
            ev.preventDefault();
            openHelp();
            return;
        }

        var key = (ev.key || "").toLowerCase();
        if (!Object.prototype.hasOwnProperty.call(BINDINGS, key)) return;

        // Resolve target.
        var btn = resolveShortcutButton(key);
        if (!btn) return;

        // d is special: respect disabled state so users can't "download" before
        // a ship exists.
        var binding = BINDINGS[key];
        var fired = clickButton(btn, binding);
        if (fired) ev.preventDefault();
    }

    document.addEventListener("keydown", handleKey);

    // Expose a tiny surface in case debugging or external tests want to peek.
    window.shortcuts = {
        bindings: BINDINGS,
        closeAllModals: closeAllModals,
        openHelp: openHelp,
        trigger: function (key) {
            var k = String(key || "").toLowerCase();
            var btn = resolveShortcutButton(k);
            return clickButton(btn, BINDINGS[k]);
        },
    };
})();
