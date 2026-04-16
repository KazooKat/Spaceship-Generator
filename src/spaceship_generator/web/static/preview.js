// Client-side WebGL voxel renderer for the generated ship preview.
//
// Architecture:
//   * Fetches /voxels/<gen_id>.json once after the result partial is swapped in.
//   * Decodes a base64 Int16 buffer of interleaved (x, y, z, role) tuples into
//     two GPU buffers: per-instance offset (vec3) and per-instance color (vec4).
//   * Draws a single unit cube with instanced rendering so 20k voxels cost one
//     draw call. Prefers WebGL2 (native instancing); falls back to WebGL1 +
//     ANGLE_instanced_arrays if needed.
//   * Orbit camera in spherical coordinates around the model's center. Mouse
//     drag updates theta/phi, wheel updates radius, shift-left/middle/right
//     drag pans the target point.
//   * Lighting: one directional light + ambient, with a flat per-face normal
//     produced by a provoking-vertex trick so cube faces shade independently.

(function () {
    "use strict";

    // --- tiny mat4/vec3 helpers -----------------------------------------------

    function mat4Identity() {
        return new Float32Array([
            1, 0, 0, 0,
            0, 1, 0, 0,
            0, 0, 1, 0,
            0, 0, 0, 1,
        ]);
    }

    function mat4Perspective(fovy, aspect, near, far) {
        const f = 1.0 / Math.tan(fovy / 2);
        const nf = 1 / (near - far);
        const out = new Float32Array(16);
        out[0] = f / aspect;
        out[5] = f;
        out[10] = (far + near) * nf;
        out[11] = -1;
        out[14] = (2 * far * near) * nf;
        return out;
    }

    function mat4LookAt(eye, target, up) {
        const ex = eye[0], ey = eye[1], ez = eye[2];
        const cx = target[0], cy = target[1], cz = target[2];
        let zx = ex - cx, zy = ey - cy, zz = ez - cz;
        let zLen = Math.hypot(zx, zy, zz) || 1;
        zx /= zLen; zy /= zLen; zz /= zLen;
        // x = normalize(cross(up, z))
        let xx = up[1] * zz - up[2] * zy;
        let xy = up[2] * zx - up[0] * zz;
        let xz = up[0] * zy - up[1] * zx;
        let xLen = Math.hypot(xx, xy, xz) || 1;
        xx /= xLen; xy /= xLen; xz /= xLen;
        // y = cross(z, x)
        const yx = zy * xz - zz * xy;
        const yy = zz * xx - zx * xz;
        const yz = zx * xy - zy * xx;
        const out = new Float32Array(16);
        out[0] = xx; out[1] = yx; out[2] = zx; out[3] = 0;
        out[4] = xy; out[5] = yy; out[6] = zy; out[7] = 0;
        out[8] = xz; out[9] = yz; out[10] = zz; out[11] = 0;
        out[12] = -(xx * ex + xy * ey + xz * ez);
        out[13] = -(yx * ex + yy * ey + yz * ez);
        out[14] = -(zx * ex + zy * ey + zz * ez);
        out[15] = 1;
        return out;
    }

    function mat4Multiply(a, b) {
        const out = new Float32Array(16);
        for (let i = 0; i < 4; i++) {
            for (let j = 0; j < 4; j++) {
                out[j * 4 + i] =
                    a[0 + i] * b[j * 4 + 0] +
                    a[4 + i] * b[j * 4 + 1] +
                    a[8 + i] * b[j * 4 + 2] +
                    a[12 + i] * b[j * 4 + 3];
            }
        }
        return out;
    }

    // --- cube geometry --------------------------------------------------------
    //
    // 6 faces, 2 triangles each, 6 vertices each. Per-vertex attributes:
    //   position (vec3) at cube corners (0..1 range)
    //   normal   (vec3) face normal (constant per face)
    // Instanced attributes (one per voxel):
    //   offset   (vec3) world-space translation (x, y, z)
    //   color    (vec4) RGBA 0-1
    function buildCubeVerts() {
        // Faces: +X, -X, +Y, -Y, +Z, -Z
        const faces = [
            { n: [1, 0, 0], verts: [[1, 0, 0], [1, 1, 0], [1, 1, 1], [1, 0, 0], [1, 1, 1], [1, 0, 1]] },
            { n: [-1, 0, 0], verts: [[0, 0, 0], [0, 1, 1], [0, 1, 0], [0, 0, 0], [0, 0, 1], [0, 1, 1]] },
            { n: [0, 1, 0], verts: [[0, 1, 0], [0, 1, 1], [1, 1, 1], [0, 1, 0], [1, 1, 1], [1, 1, 0]] },
            { n: [0, -1, 0], verts: [[0, 0, 0], [1, 0, 1], [0, 0, 1], [0, 0, 0], [1, 0, 0], [1, 0, 1]] },
            { n: [0, 0, 1], verts: [[0, 0, 1], [1, 1, 1], [0, 1, 1], [0, 0, 1], [1, 0, 1], [1, 1, 1]] },
            { n: [0, 0, -1], verts: [[0, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, 0], [1, 1, 0], [1, 0, 0]] },
        ];
        const pos = new Float32Array(faces.length * 6 * 3);
        const nrm = new Float32Array(faces.length * 6 * 3);
        let p = 0;
        for (const f of faces) {
            for (const v of f.verts) {
                pos[p] = v[0]; pos[p + 1] = v[1]; pos[p + 2] = v[2];
                nrm[p] = f.n[0]; nrm[p + 1] = f.n[1]; nrm[p + 2] = f.n[2];
                p += 3;
            }
        }
        return { pos: pos, nrm: nrm, count: faces.length * 6 };
    }

    // --- shaders --------------------------------------------------------------
    //
    // Written as GLSL 100 (works on both WebGL1 and WebGL2 in compatibility mode)
    // and promoted to #version 300 es when we detect WebGL2.
    const VS_WEBGL1 = [
        "precision highp float;",
        "attribute vec3 aPos;",
        "attribute vec3 aNormal;",
        "attribute vec3 aOffset;",
        "attribute vec4 aColor;",
        "uniform mat4 uProj;",
        "uniform mat4 uView;",
        "varying vec3 vNormal;",
        "varying vec4 vColor;",
        "void main() {",
        "  vec3 world = aPos + aOffset;",
        "  gl_Position = uProj * uView * vec4(world, 1.0);",
        "  vNormal = aNormal;",
        "  vColor = aColor;",
        "}",
    ].join("\n");

    const FS_WEBGL1 = [
        "precision highp float;",
        "varying vec3 vNormal;",
        "varying vec4 vColor;",
        "uniform vec3 uLightDir;",
        "uniform float uAmbient;",
        "void main() {",
        "  float d = max(dot(normalize(vNormal), normalize(uLightDir)), 0.0);",
        "  float intensity = uAmbient + (1.0 - uAmbient) * d;",
        "  gl_FragColor = vec4(vColor.rgb * intensity, vColor.a);",
        "}",
    ].join("\n");

    const VS_WEBGL2 = [
        "#version 300 es",
        "precision highp float;",
        "in vec3 aPos;",
        "in vec3 aNormal;",
        "in vec3 aOffset;",
        "in vec4 aColor;",
        "uniform mat4 uProj;",
        "uniform mat4 uView;",
        "out vec3 vNormal;",
        "out vec4 vColor;",
        "void main() {",
        "  vec3 world = aPos + aOffset;",
        "  gl_Position = uProj * uView * vec4(world, 1.0);",
        "  vNormal = aNormal;",
        "  vColor = aColor;",
        "}",
    ].join("\n");

    const FS_WEBGL2 = [
        "#version 300 es",
        "precision highp float;",
        "in vec3 vNormal;",
        "in vec4 vColor;",
        "uniform vec3 uLightDir;",
        "uniform float uAmbient;",
        "out vec4 outColor;",
        "void main() {",
        "  float d = max(dot(normalize(vNormal), normalize(uLightDir)), 0.0);",
        "  float intensity = uAmbient + (1.0 - uAmbient) * d;",
        "  outColor = vec4(vColor.rgb * intensity, vColor.a);",
        "}",
    ].join("\n");

    function compileShader(gl, type, src) {
        const sh = gl.createShader(type);
        gl.shaderSource(sh, src);
        gl.compileShader(sh);
        if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
            const info = gl.getShaderInfoLog(sh);
            gl.deleteShader(sh);
            throw new Error("shader compile: " + info);
        }
        return sh;
    }

    function linkProgram(gl, vs, fs) {
        const prog = gl.createProgram();
        gl.attachShader(prog, vs);
        gl.attachShader(prog, fs);
        gl.linkProgram(prog);
        if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
            const info = gl.getProgramInfoLog(prog);
            gl.deleteProgram(prog);
            throw new Error("program link: " + info);
        }
        return prog;
    }

    // --- base64 → Uint8Array (browser-safe) -----------------------------------
    function base64ToBytes(b64) {
        const binary = atob(b64);
        const len = binary.length;
        const out = new Uint8Array(len);
        for (let i = 0; i < len; i++) out[i] = binary.charCodeAt(i);
        return out;
    }

    // --- the renderer ---------------------------------------------------------

    function makeRenderer(canvas, data) {
        // data = { dims:[W,H,L], count, voxels: base64, colors: {roleInt: [r,g,b,a]} }
        const W = data.dims[0], H = data.dims[1], L = data.dims[2];
        const count = data.count;

        const bytes = base64ToBytes(data.voxels);
        // Int16 little-endian, 4 entries per voxel (x, y, z, role).
        const i16 = new Int16Array(bytes.buffer, bytes.byteOffset, (bytes.byteLength / 2) | 0);

        // Build interleaved per-instance arrays.
        const offsets = new Float32Array(count * 3);
        const colors = new Float32Array(count * 4);
        const cx = W / 2, cy = H / 2, cz = L / 2;
        for (let i = 0; i < count; i++) {
            const x = i16[i * 4 + 0];
            const y = i16[i * 4 + 1];
            const z = i16[i * 4 + 2];
            const role = i16[i * 4 + 3];
            // Center the model on origin so the orbit camera looks at (0,0,0).
            offsets[i * 3 + 0] = x - cx;
            offsets[i * 3 + 1] = y - cy;
            offsets[i * 3 + 2] = z - cz;
            const c = data.colors[String(role)] || [0.6, 0.6, 0.6, 1.0];
            colors[i * 4 + 0] = c[0];
            colors[i * 4 + 1] = c[1];
            colors[i * 4 + 2] = c[2];
            colors[i * 4 + 3] = c[3] != null ? c[3] : 1.0;
        }

        // --- GL context selection ---------------------------------------------
        let gl = canvas.getContext("webgl2", { antialias: true, alpha: true });
        let isWebGL2 = !!gl;
        let instancedExt = null;
        if (!gl) {
            gl = canvas.getContext("webgl", { antialias: true, alpha: true })
                || canvas.getContext("experimental-webgl", { antialias: true, alpha: true });
            if (!gl) return null;
            instancedExt = gl.getExtension("ANGLE_instanced_arrays");
            if (!instancedExt) return null;
        }

        const vsSrc = isWebGL2 ? VS_WEBGL2 : VS_WEBGL1;
        const fsSrc = isWebGL2 ? FS_WEBGL2 : FS_WEBGL1;
        let prog;
        try {
            const vs = compileShader(gl, gl.VERTEX_SHADER, vsSrc);
            const fs = compileShader(gl, gl.FRAGMENT_SHADER, fsSrc);
            prog = linkProgram(gl, vs, fs);
        } catch (e) {
            console.warn("WebGL init failed:", e);
            return null;
        }
        gl.useProgram(prog);

        const cube = buildCubeVerts();

        // Static per-vertex buffers
        const posBuf = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
        gl.bufferData(gl.ARRAY_BUFFER, cube.pos, gl.STATIC_DRAW);

        const nrmBuf = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, nrmBuf);
        gl.bufferData(gl.ARRAY_BUFFER, cube.nrm, gl.STATIC_DRAW);

        // Instanced per-voxel buffers
        const offBuf = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, offBuf);
        gl.bufferData(gl.ARRAY_BUFFER, offsets, gl.STATIC_DRAW);

        const colBuf = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, colBuf);
        gl.bufferData(gl.ARRAY_BUFFER, colors, gl.STATIC_DRAW);

        const aPos = gl.getAttribLocation(prog, "aPos");
        const aNormal = gl.getAttribLocation(prog, "aNormal");
        const aOffset = gl.getAttribLocation(prog, "aOffset");
        const aColor = gl.getAttribLocation(prog, "aColor");

        function vertexAttribDivisor(loc, divisor) {
            if (isWebGL2) gl.vertexAttribDivisor(loc, divisor);
            else instancedExt.vertexAttribDivisorANGLE(loc, divisor);
        }

        gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
        gl.enableVertexAttribArray(aPos);
        gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 0, 0);
        vertexAttribDivisor(aPos, 0);

        gl.bindBuffer(gl.ARRAY_BUFFER, nrmBuf);
        gl.enableVertexAttribArray(aNormal);
        gl.vertexAttribPointer(aNormal, 3, gl.FLOAT, false, 0, 0);
        vertexAttribDivisor(aNormal, 0);

        gl.bindBuffer(gl.ARRAY_BUFFER, offBuf);
        gl.enableVertexAttribArray(aOffset);
        gl.vertexAttribPointer(aOffset, 3, gl.FLOAT, false, 0, 0);
        vertexAttribDivisor(aOffset, 1);

        gl.bindBuffer(gl.ARRAY_BUFFER, colBuf);
        gl.enableVertexAttribArray(aColor);
        gl.vertexAttribPointer(aColor, 4, gl.FLOAT, false, 0, 0);
        vertexAttribDivisor(aColor, 1);

        const uProj = gl.getUniformLocation(prog, "uProj");
        const uView = gl.getUniformLocation(prog, "uView");
        const uLightDir = gl.getUniformLocation(prog, "uLightDir");
        const uAmbient = gl.getUniformLocation(prog, "uAmbient");

        gl.enable(gl.DEPTH_TEST);
        gl.enable(gl.CULL_FACE);
        gl.cullFace(gl.BACK);
        gl.clearColor(0.039, 0.047, 0.067, 0.0);

        // Camera state ---------------------------------------------------------
        // Orbit around the model center, which is at world origin after recentering.
        const modelSize = Math.hypot(W, H, L);
        const cam = {
            theta: -Math.PI / 3,       // horizontal angle
            phi: 0.5,                  // vertical angle (0 = horizon)
            radius: modelSize * 1.1,   // distance
            target: [0, 0, 0],
            minRadius: Math.max(W, H, L) * 0.4,
            maxRadius: modelSize * 6,
            fov: Math.PI / 4,
            near: 0.1,
            far: modelSize * 20 + 100,
        };

        function computeEye() {
            // Spherical → cartesian, Y is up.
            const cp = Math.cos(cam.phi);
            const sp = Math.sin(cam.phi);
            const ct = Math.cos(cam.theta);
            const st = Math.sin(cam.theta);
            return [
                cam.target[0] + cam.radius * cp * ct,
                cam.target[1] + cam.radius * sp,
                cam.target[2] + cam.radius * cp * st,
            ];
        }

        // --- render loop ------------------------------------------------------
        let rafPending = false;
        let dpr = Math.max(1, window.devicePixelRatio || 1);
        // Frame-rate measurement for developer tooling.
        let frameCount = 0;
        let frameCountWindowStart = performance.now();
        let fpsEstimate = 0;
        // Expose for devtools: window.__shipPreview.fps()
        canvas.__preview = {
            getFps: function () { return fpsEstimate; },
            getCount: function () { return count; },
        };

        function resizeIfNeeded() {
            const w = Math.max(1, Math.floor(canvas.clientWidth * dpr));
            const h = Math.max(1, Math.floor(canvas.clientHeight * dpr));
            if (canvas.width !== w || canvas.height !== h) {
                canvas.width = w;
                canvas.height = h;
            }
        }

        function draw() {
            rafPending = false;
            resizeIfNeeded();
            const w = canvas.width, h = canvas.height;
            gl.viewport(0, 0, w, h);
            gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

            const eye = computeEye();
            // View "up" is (0,1,0) unless we're near the poles — then fall
            // back to a sideways up so lookAt doesn't produce NaNs.
            const up = Math.abs(Math.cos(cam.phi)) < 1e-3 ? [0, 0, 1] : [0, 1, 0];
            const view = mat4LookAt(eye, cam.target, up);
            const aspect = w / h;
            const proj = mat4Perspective(cam.fov, aspect, cam.near, cam.far);

            gl.useProgram(prog);
            gl.uniformMatrix4fv(uProj, false, proj);
            gl.uniformMatrix4fv(uView, false, view);
            // Light roughly from upper-front-right; matches old matplotlib feel.
            gl.uniform3f(uLightDir, 0.5, 1.0, 0.35);
            gl.uniform1f(uAmbient, 0.55);

            if (isWebGL2) {
                gl.drawArraysInstanced(gl.TRIANGLES, 0, cube.count, count);
            } else {
                instancedExt.drawArraysInstancedANGLE(gl.TRIANGLES, 0, cube.count, count);
            }

            frameCount++;
            const now = performance.now();
            const elapsed = now - frameCountWindowStart;
            if (elapsed > 500) {
                fpsEstimate = (frameCount * 1000) / elapsed;
                frameCount = 0;
                frameCountWindowStart = now;
            }
        }

        function requestDraw() {
            if (rafPending) return;
            rafPending = true;
            requestAnimationFrame(draw);
        }

        // --- interaction ------------------------------------------------------
        let mode = null;  // "orbit" | "pan" | null
        let lastX = 0, lastY = 0;
        const ORBIT_SENSITIVITY = 0.008;  // radians per pixel

        canvas.addEventListener("contextmenu", function (ev) { ev.preventDefault(); });

        canvas.addEventListener("mousedown", function (ev) {
            const isPan = ev.button === 1 || ev.button === 2 || (ev.button === 0 && ev.shiftKey);
            mode = isPan ? "pan" : (ev.button === 0 ? "orbit" : null);
            if (!mode) return;
            lastX = ev.clientX;
            lastY = ev.clientY;
            canvas.classList.add("dragging");
            if (mode === "pan") canvas.classList.add("panning");
            ev.preventDefault();
        });

        window.addEventListener("mousemove", function (ev) {
            if (!mode) return;
            const dx = ev.clientX - lastX;
            const dy = ev.clientY - lastY;
            lastX = ev.clientX;
            lastY = ev.clientY;
            if (mode === "orbit") {
                cam.theta -= dx * ORBIT_SENSITIVITY;
                cam.phi += dy * ORBIT_SENSITIVITY;
                const lim = Math.PI / 2 - 0.01;
                if (cam.phi > lim) cam.phi = lim;
                if (cam.phi < -lim) cam.phi = -lim;
            } else if (mode === "pan") {
                // Pan along the camera's right/up axes, scaled by the current
                // world-space size per pixel so panning feels screen-linear.
                const eye = computeEye();
                const fx = cam.target[0] - eye[0];
                const fy = cam.target[1] - eye[1];
                const fz = cam.target[2] - eye[2];
                const flen = Math.hypot(fx, fy, fz) || 1;
                const fnx = fx / flen, fny = fy / flen, fnz = fz / flen;
                const worldUp = [0, 1, 0];
                // right = normalize(cross(forward, worldUp))
                let rx = fny * worldUp[2] - fnz * worldUp[1];
                let ry = fnz * worldUp[0] - fnx * worldUp[2];
                let rz = fnx * worldUp[1] - fny * worldUp[0];
                const rlen = Math.hypot(rx, ry, rz) || 1;
                rx /= rlen; ry /= rlen; rz /= rlen;
                // up = cross(right, forward)
                const ux = ry * fnz - rz * fny;
                const uy = rz * fnx - rx * fnz;
                const uz = rx * fny - ry * fnx;
                const pxScale = (2 * cam.radius * Math.tan(cam.fov / 2)) / Math.max(1, canvas.clientHeight);
                cam.target[0] -= (rx * dx - ux * dy) * pxScale;
                cam.target[1] -= (ry * dx - uy * dy) * pxScale;
                cam.target[2] -= (rz * dx - uz * dy) * pxScale;
            }
            requestDraw();
        });

        window.addEventListener("mouseup", function () {
            if (!mode) return;
            mode = null;
            canvas.classList.remove("dragging");
            canvas.classList.remove("panning");
        });

        canvas.addEventListener("wheel", function (ev) {
            ev.preventDefault();
            // deltaY > 0 → zoom out
            const factor = Math.exp(ev.deltaY * 0.0015);
            cam.radius *= factor;
            if (cam.radius < cam.minRadius) cam.radius = cam.minRadius;
            if (cam.radius > cam.maxRadius) cam.radius = cam.maxRadius;
            requestDraw();
        }, { passive: false });

        canvas.addEventListener("dblclick", function () {
            cam.theta = -Math.PI / 3;
            cam.phi = 0.5;
            cam.radius = modelSize * 1.1;
            cam.target = [0, 0, 0];
            requestDraw();
        });

        // Re-render on size changes (responsive layout).
        if (typeof ResizeObserver !== "undefined") {
            const ro = new ResizeObserver(function () { requestDraw(); });
            ro.observe(canvas);
        } else {
            window.addEventListener("resize", requestDraw);
        }

        // Kick off the first draw.
        requestDraw();

        return {
            canvas: canvas,
            requestDraw: requestDraw,
            getFps: function () { return fpsEstimate; },
            getCount: function () { return count; },
        };
    }

    // --- bootstrap / HTMX lifecycle -------------------------------------------

    function showFallback(canvas) {
        // Prefer a sibling fallback <img> if one exists.
        const wrap = canvas.parentElement;
        if (!wrap) return;
        const img = wrap.querySelector(".preview-img-fallback");
        if (img) {
            canvas.style.display = "none";
            img.style.display = "block";
            const src = canvas.dataset.previewUrl;
            if (src && !img.getAttribute("src")) img.setAttribute("src", src);
        }
    }

    function initCanvas(canvas) {
        if (!canvas || canvas.dataset.previewBound === "1") return;
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
                const r = makeRenderer(canvas, data);
                if (!r) {
                    showFallback(canvas);
                    return;
                }
                const t1 = performance.now();
                // Attach timing info for debugging via browser devtools.
                canvas.__previewMs = t1 - t0;
                // Mark ready so test/automation code can detect first-paint.
                canvas.dataset.previewReady = "1";
            })
            .catch(function (err) {
                console.warn("preview load failed:", err);
                showFallback(canvas);
            });
    }

    function initAll(root) {
        const scope = root || document;
        const els = scope.querySelectorAll(".preview-canvas[data-voxels-url]");
        els.forEach(initCanvas);
    }

    // Expose a tiny API for app.js and devtools.
    window.SpaceshipPreview = {
        initAll: initAll,
        initCanvas: initCanvas,
    };

    document.addEventListener("DOMContentLoaded", function () { initAll(document); });

    // Re-initialize after an HTMX swap brings in fresh _result.html markup.
    document.body.addEventListener("htmx:afterSwap", function (ev) {
        initAll(ev.target || document);
    });
})();
