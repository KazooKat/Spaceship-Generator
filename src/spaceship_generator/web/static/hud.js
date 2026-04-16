// Sci-fi HUD overlay for the spaceship preview.
//
// Responsibilities:
//   * Draw a small axis gizmo (X/Y/Z arrows) on #axis-gizmo, tracking the
//     live preview camera.
//   * Mirror FPS and voxel counts onto #stat-fps / #stat-voxels.
//   * Wire #btn-view-{top,front,side,persp,reset} and #btn-fullscreen to
//     the shipPreview API, with exclusive .active highlighting.
//   * Idle-state fallback: if no onFrame events arrive for 3s, display "-"
//     placeholders and add .idle to the stat cells.
//
// Contract: extends window.shipPreview exposed by preview.js. Does not
// touch GL state or camera math; presets are set via setView(preset) so
// the pan/orbit sign invariants in preview.js are preserved unchanged.

(function () {
    "use strict";

    const VIEW_BUTTON_IDS = [
        "btn-view-persp",
        "btn-view-top",
        "btn-view-front",
        "btn-view-side",
    ];
    const VIEW_PRESET_OF = {
        "btn-view-persp": "persp",
        "btn-view-top": "top",
        "btn-view-front": "front",
        "btn-view-side": "side",
    };

    const IDLE_MS = 3000;
    const GIZMO_TICK_MS = 1000 / 15;  // ~15Hz even when the preview is idle
    const GIZMO_SIZE = 112;

    // One state object per page lifetime; reused across HTMX swaps so we
    // don't re-add listeners on top of themselves.
    const state = {
        booted: false,
        statFps: null,
        statVoxels: null,
        gizmoCanvas: null,
        gizmoCtx: null,
        gizmoTickId: null,
        activeButtonId: null,
        lastFrameAt: 0,
        idleTimerId: null,
        frameUnsub: null,
        accentCyan: "#5ce1ff",
        tokensRead: false,
    };

    function readCssToken(name, fallback) {
        try {
            const raw = getComputedStyle(document.body).getPropertyValue(name);
            const trimmed = (raw || "").trim();
            return trimmed || fallback;
        } catch (e) {
            return fallback;
        }
    }

    function readTokens() {
        if (state.tokensRead) return;
        state.accentCyan = readCssToken("--accent-cyan", "#5ce1ff");
        state.tokensRead = true;
    }

    // --- gizmo rendering -----------------------------------------------------
    //
    // Camera uses spherical coordinates in preview.js:
    //   eye = target + radius * (cos(phi)*cos(theta), sin(phi), cos(phi)*sin(theta))
    // Forward vector z' in camera space = (target - eye) normalized. We need
    // the inverse view matrix basis (right, up, forward) to project each
    // world-axis endpoint onto screen space.

    function buildCameraBasis(cam) {
        // Reproduce computeEye() then mat4LookAt basis vectors.
        const cp = Math.cos(cam.phi);
        const sp = Math.sin(cam.phi);
        const ct = Math.cos(cam.theta);
        const st = Math.sin(cam.theta);
        const eye = [
            cam.target[0] + cam.radius * cp * ct,
            cam.target[1] + cam.radius * sp,
            cam.target[2] + cam.radius * cp * st,
        ];
        // z' = eye - target (points FROM target TO eye in lookAt convention).
        let zx = eye[0] - cam.target[0];
        let zy = eye[1] - cam.target[1];
        let zz = eye[2] - cam.target[2];
        const zlen = Math.hypot(zx, zy, zz) || 1;
        zx /= zlen; zy /= zlen; zz /= zlen;
        // up: swap well before the pole so cross(up, z) doesn't collapse.
        // The top preset parks phi at π/2-0.01 (|cos| ≈ 0.01); a 1e-3
        // threshold let that slip through and produced a zero-length x
        // basis.
        const up = Math.abs(Math.cos(cam.phi)) < 0.05 ? [0, 0, 1] : [0, 1, 0];
        // right = normalize(cross(up, z))
        let xx = up[1] * zz - up[2] * zy;
        let xy = up[2] * zx - up[0] * zz;
        let xz = up[0] * zy - up[1] * zx;
        const xlen = Math.hypot(xx, xy, xz) || 1;
        xx /= xlen; xy /= xlen; xz /= xlen;
        // true up = cross(z, right)
        const yx = zy * xz - zz * xy;
        const yy = zz * xx - zx * xz;
        const yz = zx * xy - zy * xx;
        // In view space, the camera looks along -z. Forward (into the
        // scene) is therefore (-zx, -zy, -zz). Project(v) = dot(v, right),
        // dot(v, up), dot(v, -forward).
        return {
            rx: xx, ry: xy, rz: xz,
            ux: yx, uy: yy, uz: yz,
            fx: -zx, fy: -zy, fz: -zz,
        };
    }

    function project(basis, vx, vy, vz) {
        return {
            sx: basis.rx * vx + basis.ry * vy + basis.rz * vz,
            sy: basis.ux * vx + basis.uy * vy + basis.uz * vz,
            depth: basis.fx * vx + basis.fy * vy + basis.fz * vz,
        };
    }

    function pollStats() {
        // preview.js only dispatches ship-preview-stats inside draw(), and
        // draw() is on-demand (rAF triggered by user input). So onFrame
        // subscribers can go silent when the camera is idle. Poll
        // getStats() from the gizmo tick so the readout stays fresh.
        const sp = safeShipPreview();
        if (!sp || typeof sp.getStats !== "function") return;
        let stats = null;
        try { stats = sp.getStats(); } catch (e) { stats = null; }
        if (stats && typeof stats.voxelCount === "number") {
            renderStats(stats);
            kickIdleTimer();
        }
    }

    function drawGizmo() {
        pollStats();
        const canvas = state.gizmoCanvas;
        const ctx = state.gizmoCtx;
        if (!canvas || !ctx) return;
        // Keep internal pixel grid in sync with devicePixelRatio while
        // leaving CSS size at 96x96. Re-check every tick in case the user
        // dragged the window to a different-DPI display.
        const dpr = Math.max(1, window.devicePixelRatio || 1);
        const cssW = GIZMO_SIZE;
        const cssH = GIZMO_SIZE;
        const pxW = Math.floor(cssW * dpr);
        const pxH = Math.floor(cssH * dpr);
        if (canvas.width !== pxW || canvas.height !== pxH) {
            canvas.width = pxW;
            canvas.height = pxH;
        }
        if (!canvas.style.width) canvas.style.width = cssW + "px";
        if (!canvas.style.height) canvas.style.height = cssH + "px";

        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cssW, cssH);

        const cx = cssW / 2;
        const cy = cssH / 2;
        const arm = Math.min(cssW, cssH) * 0.36;

        let cam = null;
        if (window.shipPreview && typeof window.shipPreview.getCamera === "function") {
            try { cam = window.shipPreview.getCamera(); } catch (e) { cam = null; }
        }

        // Before the first ship loads there's no active renderer, so
        // getCamera() returns null. Fall back to the default perspective
        // pose so users still see a three-axis readout idle — otherwise
        // the gizmo looks broken (just a dot) before first generate.
        if (!cam) {
            cam = {
                theta: -Math.PI / 3,
                phi: 0.5,
                radius: 1,
                target: [0, 0, 0],
            };
        }

        const basis = buildCameraBasis(cam);

        // Build the three axis lines with depth so we can draw back-to-front.
        const axes = [
            { label: "X", color: "#ff6b6b", v: [1, 0, 0] },
            { label: "Y", color: "#8cff8c", v: [0, 1, 0] },
            { label: "Z", color: "#82b1ff", v: [0, 0, 1] },
        ];
        const projected = axes.map(function (a) {
            const p = project(basis, a.v[0], a.v[1], a.v[2]);
            return {
                label: a.label,
                color: a.color,
                sx: p.sx,
                sy: p.sy,
                depth: p.depth,
            };
        });
        // Draw axes pointing away from the camera first (more negative
        // depth = deeper into the screen), so front-facing axes overwrite.
        projected.sort(function (a, b) { return a.depth - b.depth; });

        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.font = "bold 10px ui-monospace, 'JetBrains Mono', Menlo, Consolas, monospace";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        for (let i = 0; i < projected.length; i++) {
            const p = projected[i];
            // Flip Y because canvas Y grows downward.
            const ex = cx + p.sx * arm;
            const ey = cy - p.sy * arm;
            // Axis pointing away from camera fades toward ~35% alpha.
            const t = (p.depth + 1) * 0.5;  // 0 behind, 1 toward camera
            const alpha = 0.35 + 0.65 * Math.max(0, Math.min(1, t));

            ctx.globalAlpha = alpha;
            ctx.strokeStyle = p.color;
            ctx.lineWidth = 1.6;
            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.lineTo(ex, ey);
            ctx.stroke();

            // Label offset slightly past the line end.
            const dx = ex - cx;
            const dy = ey - cy;
            const dlen = Math.hypot(dx, dy) || 1;
            const lx = ex + (dx / dlen) * 7;
            const ly = ey + (dy / dlen) * 7;
            ctx.fillStyle = p.color;
            ctx.fillText(p.label, lx, ly);
        }

        // Origin dot in accent cyan, drawn on top.
        ctx.globalAlpha = 1;
        ctx.fillStyle = state.accentCyan;
        ctx.beginPath();
        ctx.arc(cx, cy, 2.5, 0, Math.PI * 2);
        ctx.fill();
        // Thin cyan ring for sci-fi flavor.
        ctx.strokeStyle = state.accentCyan;
        ctx.globalAlpha = 0.45;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(cx, cy, 5, 0, Math.PI * 2);
        ctx.stroke();
        ctx.globalAlpha = 1;
    }

    // --- stats readout -------------------------------------------------------

    function renderStatsIdle() {
        if (state.statFps) {
            state.statFps.textContent = "-";
            state.statFps.classList.add("idle");
        }
        if (state.statVoxels) {
            state.statVoxels.textContent = "-";
            state.statVoxels.classList.add("idle");
        }
    }

    function renderStats(detail) {
        if (!detail) return;
        if (state.statFps) {
            state.statFps.textContent = String(Math.max(0, Math.round(detail.fps || 0)));
            state.statFps.classList.remove("idle");
        }
        if (state.statVoxels) {
            const n = detail.voxelCount || 0;
            state.statVoxels.textContent = n.toLocaleString();
            state.statVoxels.classList.remove("idle");
        }
    }

    function kickIdleTimer() {
        state.lastFrameAt = Date.now();
        if (state.idleTimerId != null) {
            clearTimeout(state.idleTimerId);
        }
        state.idleTimerId = setTimeout(function () {
            if (Date.now() - state.lastFrameAt >= IDLE_MS) {
                renderStatsIdle();
            }
        }, IDLE_MS + 25);
    }

    // --- preset button active state -----------------------------------------

    function setActiveButton(id) {
        state.activeButtonId = id;
        for (let i = 0; i < VIEW_BUTTON_IDS.length; i++) {
            const btn = document.getElementById(VIEW_BUTTON_IDS[i]);
            if (!btn) continue;
            if (VIEW_BUTTON_IDS[i] === id) btn.classList.add("active");
            else btn.classList.remove("active");
        }
    }

    function clearActiveButton() {
        if (!state.activeButtonId) return;
        state.activeButtonId = null;
        for (let i = 0; i < VIEW_BUTTON_IDS.length; i++) {
            const btn = document.getElementById(VIEW_BUTTON_IDS[i]);
            if (btn) btn.classList.remove("active");
        }
    }

    // --- viewport drag detection --------------------------------------------
    //
    // Clear the "preset active" highlight as soon as the user orbits or
    // pans. We don't try to introspect renderer state; instead we listen on
    // the viewport container for mousemove while a mouse button is down.

    let viewportMouseDown = false;
    function onViewportMouseDown(ev) {
        // Only primary / middle / right buttons matter for camera drag.
        if (ev.button === 0 || ev.button === 1 || ev.button === 2) {
            viewportMouseDown = true;
        }
    }
    function onViewportMouseUp() {
        viewportMouseDown = false;
    }
    function onViewportMouseMove() {
        if (viewportMouseDown && state.activeButtonId) {
            clearActiveButton();
        }
    }

    // --- button wiring ------------------------------------------------------

    function safeShipPreview() {
        return (typeof window !== "undefined") ? window.shipPreview : null;
    }

    function attachButton(id, handler) {
        const btn = document.getElementById(id);
        if (!btn || btn.dataset.hudBound === "1") return;
        btn.dataset.hudBound = "1";
        btn.addEventListener("click", function (ev) {
            ev.preventDefault();
            handler(btn);
        });
    }

    function wirePresetButtons() {
        for (let i = 0; i < VIEW_BUTTON_IDS.length; i++) {
            const id = VIEW_BUTTON_IDS[i];
            const preset = VIEW_PRESET_OF[id];
            attachButton(id, function (btn) {
                const sp = safeShipPreview();
                if (sp && typeof sp.setView === "function") {
                    sp.setView(preset);
                }
                setActiveButton(btn.id);
            });
        }
        attachButton("btn-view-reset", function () {
            const sp = safeShipPreview();
            if (sp && typeof sp.resetCamera === "function") {
                sp.resetCamera();
            }
            // Reset maps to the perspective preset conceptually.
            setActiveButton("btn-view-persp");
        });
        attachButton("btn-fullscreen", function () {
            const sp = safeShipPreview();
            if (sp && typeof sp.fullscreen === "function") {
                sp.fullscreen();
            }
        });
    }

    // --- viewport mouse listeners ------------------------------------------

    function attachViewportListeners() {
        const viewport = document.getElementById("viewport");
        if (!viewport || viewport.dataset.hudBound === "1") return;
        viewport.dataset.hudBound = "1";
        viewport.addEventListener("mousedown", onViewportMouseDown);
        viewport.addEventListener("mousemove", onViewportMouseMove);
        // Use window for mouseup so we catch releases outside the viewport.
        window.addEventListener("mouseup", onViewportMouseUp);
    }

    // --- subscribe to frames ------------------------------------------------

    function subscribeFrames() {
        if (state.frameUnsub) return;  // already subscribed via shipPreview facade
        const sp = safeShipPreview();
        if (!sp || typeof sp.onFrame !== "function") return;
        state.frameUnsub = sp.onFrame(function (detail) {
            renderStats(detail);
            kickIdleTimer();
        });
    }

    // --- boot ---------------------------------------------------------------

    function cacheDomRefs() {
        state.statFps = document.getElementById("stat-fps");
        state.statVoxels = document.getElementById("stat-voxels");
        const gz = document.getElementById("axis-gizmo");
        if (gz && gz !== state.gizmoCanvas) {
            state.gizmoCanvas = gz;
            try {
                state.gizmoCtx = gz.getContext("2d");
            } catch (e) {
                state.gizmoCtx = null;
            }
        }
    }

    function startGizmoLoop() {
        if (state.gizmoTickId != null) return;
        state.gizmoTickId = setInterval(drawGizmo, GIZMO_TICK_MS);
        // Render once immediately so the gizmo is visible before the first
        // tick elapses.
        drawGizmo();
    }

    function boot() {
        if (state.booted) {
            // Re-run the things that depend on DOM elements that may have
            // just been swapped in by HTMX. Subscriptions and button-bound
            // flags stick around via dataset sentinels.
            cacheDomRefs();
            wirePresetButtons();
            attachViewportListeners();
            subscribeFrames();
            return;
        }
        state.booted = true;
        readTokens();
        cacheDomRefs();
        wirePresetButtons();
        attachViewportListeners();
        subscribeFrames();
        startGizmoLoop();
        // Start in idle state — the first frame event will light things up.
        renderStatsIdle();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
    document.body && document.body.addEventListener("htmx:afterSwap", function () {
        // DOM pieces (stats spans, gizmo, buttons) may be re-rendered.
        // boot() is idempotent; it re-caches refs and re-attaches only
        // handlers that aren't already flagged.
        boot();
    });
})();
