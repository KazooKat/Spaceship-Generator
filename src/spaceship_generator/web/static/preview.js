// Client-side WebGL voxel renderer for the generated ship preview.
//
// Architecture:
//   * Fetches /voxels/<gen_id>.json once after the result partial is swapped in.
//   * Decodes a base64 Int16 buffer of interleaved (x, y, z, role) tuples into
//     per-instance offset (vec3) and color (vec4) buffers, split into an
//     opaque group (alpha >= 0.99) and a translucent group (alpha < 0.99).
//   * Draws a single unit cube with instanced rendering so 20k voxels cost one
//     draw call per pass. Prefers WebGL2 (native instancing); falls back to
//     WebGL1 + ANGLE_instanced_arrays if needed.
//   * Two-pass render: opaque voxels first with depth writes enabled, then
//     translucent voxels (glass, ice, honey, slime) with alpha blending and
//     depth writes disabled so they don't occlude each other.
//   * Orbit camera in spherical coordinates around the model's center. Mouse
//     drag updates theta/phi, wheel updates radius, shift-left/middle/right
//     drag pans the target point with drag-to-scroll behavior.
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

        // Partition voxels into opaque (alpha >= ALPHA_OPAQUE) and translucent
        // (alpha < ALPHA_OPAQUE). Opaque voxels draw first with depth writes
        // enabled; translucent voxels draw second with blending and depth
        // writes disabled so they don't occlude each other in arbitrary
        // order.
        const ALPHA_OPAQUE = 0.99;
        const cx = W / 2, cy = H / 2, cz = L / 2;

        // First pass: count opaque vs translucent so we can allocate tightly.
        let opaqueCount = 0;
        let transCount = 0;
        for (let i = 0; i < count; i++) {
            const role = i16[i * 4 + 3];
            const c = data.colors[String(role)];
            const a = (c && c[3] != null) ? c[3] : 1.0;
            if (a >= ALPHA_OPAQUE) opaqueCount++;
            else transCount++;
        }

        const opaqueOffsets = new Float32Array(opaqueCount * 3);
        const opaqueColors = new Float32Array(opaqueCount * 4);
        const transOffsets = new Float32Array(transCount * 3);
        const transColors = new Float32Array(transCount * 4);

        // Second pass: populate the split buffers. Center model on origin.
        let oi = 0, ti = 0;
        for (let i = 0; i < count; i++) {
            const x = i16[i * 4 + 0];
            const y = i16[i * 4 + 1];
            const z = i16[i * 4 + 2];
            const role = i16[i * 4 + 3];
            const c = data.colors[String(role)] || [0.6, 0.6, 0.6, 1.0];
            const a = c[3] != null ? c[3] : 1.0;
            if (a >= ALPHA_OPAQUE) {
                opaqueOffsets[oi * 3 + 0] = x - cx;
                opaqueOffsets[oi * 3 + 1] = y - cy;
                opaqueOffsets[oi * 3 + 2] = z - cz;
                opaqueColors[oi * 4 + 0] = c[0];
                opaqueColors[oi * 4 + 1] = c[1];
                opaqueColors[oi * 4 + 2] = c[2];
                opaqueColors[oi * 4 + 3] = a;
                oi++;
            } else {
                transOffsets[ti * 3 + 0] = x - cx;
                transOffsets[ti * 3 + 1] = y - cy;
                transOffsets[ti * 3 + 2] = z - cz;
                transColors[ti * 4 + 0] = c[0];
                transColors[ti * 4 + 1] = c[1];
                transColors[ti * 4 + 2] = c[2];
                transColors[ti * 4 + 3] = a;
                ti++;
            }
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

        // Instanced per-voxel buffers — one pair per opacity pass.
        const offBufOpaque = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, offBufOpaque);
        gl.bufferData(gl.ARRAY_BUFFER, opaqueOffsets, gl.STATIC_DRAW);

        const colBufOpaque = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, colBufOpaque);
        gl.bufferData(gl.ARRAY_BUFFER, opaqueColors, gl.STATIC_DRAW);

        const offBufTrans = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, offBufTrans);
        gl.bufferData(gl.ARRAY_BUFFER, transOffsets, gl.STATIC_DRAW);

        const colBufTrans = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, colBufTrans);
        gl.bufferData(gl.ARRAY_BUFFER, transColors, gl.STATIC_DRAW);

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

        // The per-instance aOffset / aColor attributes are re-bound to the
        // appropriate (opaque / translucent) buffers each pass inside draw().
        gl.enableVertexAttribArray(aOffset);
        vertexAttribDivisor(aOffset, 1);
        gl.enableVertexAttribArray(aColor);
        vertexAttribDivisor(aColor, 1);

        function bindInstanceBuffers(offBuf, colBuf) {
            gl.bindBuffer(gl.ARRAY_BUFFER, offBuf);
            gl.vertexAttribPointer(aOffset, 3, gl.FLOAT, false, 0, 0);
            gl.bindBuffer(gl.ARRAY_BUFFER, colBuf);
            gl.vertexAttribPointer(aColor, 4, gl.FLOAT, false, 0, 0);
        }

        function drawInstances(n) {
            if (n <= 0) return;
            if (isWebGL2) {
                gl.drawArraysInstanced(gl.TRIANGLES, 0, cube.count, n);
            } else {
                instancedExt.drawArraysInstancedANGLE(gl.TRIANGLES, 0, cube.count, n);
            }
        }

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
        let contextLost = false;
        // Frame-rate measurement for developer tooling.
        let frameCount = 0;
        let frameCountWindowStart = performance.now();
        let fpsEstimate = 0;

        // UI subscribers. onFrame fires ~10Hz with current stats; onLoaded
        // fires once when buffers have been uploaded and the first draw is
        // scheduled. Both are drained in destroy() to avoid leaking closures
        // across HTMX canvas swaps.
        let frameSubs = [];
        let loadedSubs = [];
        let lastFrameDispatch = 0;
        const FRAME_DISPATCH_MS = 100;  // ~10Hz throttle
        // Expose for devtools: window.__shipPreview.fps()
        canvas.__preview = {
            getFps: function () { return fpsEstimate; },
            getCount: function () { return count; },
        };

        function resizeIfNeeded() {
            // Re-read devicePixelRatio each frame so moving the window to a
            // display with a different DPI updates crispness correctly.
            const dpr = Math.max(1, window.devicePixelRatio || 1);
            const w = Math.max(1, Math.floor(canvas.clientWidth * dpr));
            const h = Math.max(1, Math.floor(canvas.clientHeight * dpr));
            if (canvas.width !== w || canvas.height !== h) {
                canvas.width = w;
                canvas.height = h;
            }
        }

        // --- translucent back-to-front sort ---------------------------------
        //
        // For correct alpha blending, translucent voxels must be drawn
        // back-to-front from the camera's viewpoint. Sorting every frame is
        // wasteful when the camera is still, so we only re-sort when the
        // view direction has rotated more than ~15° since the last sort
        // (cosine threshold). Typical scenes have <2000 translucent voxels
        // so even a full sort is cheap; we still throttle to avoid
        // churning GPU buffers every frame during smooth orbits.
        const transOffsetsSorted = new Float32Array(transCount * 3);
        const transColorsSorted = new Float32Array(transCount * 4);
        const transDistSq = new Float32Array(transCount);
        let lastSortDirX = 0, lastSortDirY = 0, lastSortDirZ = 0;
        let transSortValid = false;
        const SORT_REBUILD_COS = Math.cos(15 * Math.PI / 180);

        function maybeResortTranslucent() {
            if (transCount <= 0) return false;
            const eye = computeEye();
            // Direction from camera toward target (normalized).
            let vx = cam.target[0] - eye[0];
            let vy = cam.target[1] - eye[1];
            let vz = cam.target[2] - eye[2];
            const vlen = Math.hypot(vx, vy, vz) || 1;
            vx /= vlen; vy /= vlen; vz /= vlen;
            if (transSortValid) {
                const dot = vx * lastSortDirX + vy * lastSortDirY + vz * lastSortDirZ;
                if (dot >= SORT_REBUILD_COS) return false;  // still fresh
            }
            // Compute squared distance from eye to each instance, then
            // sort an index permutation so the farthest voxel draws first.
            const orderArr = new Array(transCount);
            for (let i = 0; i < transCount; i++) {
                const ox = transOffsets[i * 3 + 0];
                const oy = transOffsets[i * 3 + 1];
                const oz = transOffsets[i * 3 + 2];
                const dx = ox - eye[0];
                const dy = oy - eye[1];
                const dz = oz - eye[2];
                transDistSq[i] = dx * dx + dy * dy + dz * dz;
                orderArr[i] = i;
            }
            orderArr.sort(function (a, b) { return transDistSq[b] - transDistSq[a]; });
            for (let i = 0; i < transCount; i++) {
                const src = orderArr[i];
                transOffsetsSorted[i * 3 + 0] = transOffsets[src * 3 + 0];
                transOffsetsSorted[i * 3 + 1] = transOffsets[src * 3 + 1];
                transOffsetsSorted[i * 3 + 2] = transOffsets[src * 3 + 2];
                transColorsSorted[i * 4 + 0] = transColors[src * 4 + 0];
                transColorsSorted[i * 4 + 1] = transColors[src * 4 + 1];
                transColorsSorted[i * 4 + 2] = transColors[src * 4 + 2];
                transColorsSorted[i * 4 + 3] = transColors[src * 4 + 3];
            }
            gl.bindBuffer(gl.ARRAY_BUFFER, offBufTrans);
            gl.bufferData(gl.ARRAY_BUFFER, transOffsetsSorted, gl.DYNAMIC_DRAW);
            gl.bindBuffer(gl.ARRAY_BUFFER, colBufTrans);
            gl.bufferData(gl.ARRAY_BUFFER, transColorsSorted, gl.DYNAMIC_DRAW);
            lastSortDirX = vx; lastSortDirY = vy; lastSortDirZ = vz;
            transSortValid = true;
            return true;
        }

        function draw() {
            rafPending = false;
            if (contextLost) return;
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

            // Pass 1: opaque voxels with standard depth buffering.
            gl.disable(gl.BLEND);
            gl.depthMask(true);
            gl.enable(gl.DEPTH_TEST);
            bindInstanceBuffers(offBufOpaque, colBufOpaque);
            drawInstances(opaqueCount);

            // Pass 2: translucent voxels with alpha blending. Depth test
            // stays on so we don't draw behind solid geometry, but depth
            // writes are disabled so translucent voxels don't occlude each
            // other awkwardly. Re-sort back-to-front when the camera
            // direction has changed more than ~15° since the last sort.
            if (transCount > 0) {
                maybeResortTranslucent();
                gl.enable(gl.BLEND);
                gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
                gl.depthMask(false);
                bindInstanceBuffers(offBufTrans, colBufTrans);
                drawInstances(transCount);
                // Restore state for the next frame / any later draws.
                gl.depthMask(true);
                gl.disable(gl.BLEND);
            }

            frameCount++;
            const now = performance.now();
            const elapsed = now - frameCountWindowStart;
            if (elapsed > 500) {
                fpsEstimate = (frameCount * 1000) / elapsed;
                frameCount = 0;
                frameCountWindowStart = now;
            }

            // Broadcast stats to any attached HUD at ~10Hz. Dispatch a
            // DOM CustomEvent on the canvas and also call subscriber
            // callbacks registered via window.shipPreview.onFrame.
            if (now - lastFrameDispatch >= FRAME_DISPATCH_MS) {
                lastFrameDispatch = now;
                const detail = {
                    fps: fpsEstimate,
                    voxelCount: count,
                    opaqueCount: opaqueCount,
                    transCount: transCount,
                };
                try {
                    canvas.dispatchEvent(new CustomEvent("ship-preview-stats", { detail: detail }));
                } catch (e) { /* no CustomEvent in very old browsers */ }
                for (let i = 0; i < frameSubs.length; i++) {
                    const cb = frameSubs[i];
                    if (typeof cb === "function") {
                        try { cb(detail); } catch (e) { /* swallow subscriber errors */ }
                    }
                }
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

        // All listeners are captured as named consts so destroy() can
        // removeEventListener them cleanly. HTMX swaps in a fresh canvas on
        // every "Generate" click; without this cleanup the window-level
        // mousemove/mouseup (and the fallback resize) handlers from old
        // renderers keep firing forever with stale canvas references.

        const onContextMenu = function (ev) { ev.preventDefault(); };

        const onMouseDown = function (ev) {
            const isPan = ev.button === 1 || ev.button === 2 || (ev.button === 0 && ev.shiftKey);
            mode = isPan ? "pan" : (ev.button === 0 ? "orbit" : null);
            if (!mode) return;
            lastX = ev.clientX;
            lastY = ev.clientY;
            canvas.classList.add("dragging");
            if (mode === "pan") canvas.classList.add("panning");
            ev.preventDefault();
        };

        const onMouseMove = function (ev) {
            if (!mode) return;
            const dx = ev.clientX - lastX;
            const dy = ev.clientY - lastY;
            lastX = ev.clientX;
            lastY = ev.clientY;
            if (mode === "orbit") {
                // Orbit: drag-right rotates the camera to the right
                // (theta increases). Inverse of the original convention
                // per user preference.
                cam.theta += dx * ORBIT_SENSITIVITY;
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
                // Use separate X/Y screen-to-world scales. The previous
                // single pxScale used clientHeight for both axes, which
                // distorted horizontal pan on wide viewports.
                // tan(fov/2) is the vertical half-angle; scale X by width
                // and Y by height independently.
                const targetDist = cam.radius;
                const tanHalfFov = Math.tan(cam.fov / 2);
                const pxScaleY = (2 * targetDist * tanHalfFov) / Math.max(1, canvas.clientHeight);
                const pxScaleX = (2 * targetDist * tanHalfFov) / Math.max(1, canvas.clientWidth);
                // Pan convention (user-preferred): horizontal drag moves
                // the target along the camera's right axis in the
                // opposite direction of dx so the camera "walks" with the
                // cursor. Per-axis pxScale kept for square-correct
                // sensitivity on non-square canvases.
                cam.target[0] += -rx * dx * pxScaleX + ux * dy * pxScaleY;
                cam.target[1] += -ry * dx * pxScaleX + uy * dy * pxScaleY;
                cam.target[2] += -rz * dx * pxScaleX + uz * dy * pxScaleY;
            }
            requestDraw();
        };

        const onMouseUp = function () {
            if (!mode) return;
            mode = null;
            canvas.classList.remove("dragging");
            canvas.classList.remove("panning");
        };

        const onWheel = function (ev) {
            ev.preventDefault();
            // deltaY > 0 → zoom out
            const factor = Math.exp(ev.deltaY * 0.0015);
            cam.radius *= factor;
            if (cam.radius < cam.minRadius) cam.radius = cam.minRadius;
            if (cam.radius > cam.maxRadius) cam.radius = cam.maxRadius;
            requestDraw();
        };

        const onDblClick = function () {
            cam.theta = -Math.PI / 3;
            cam.phi = 0.5;
            cam.radius = modelSize * 1.1;
            cam.target = [0, 0, 0];
            requestDraw();
        };

        // --- view presets (additive, sign-agnostic) --------------------------
        //
        // Presets set cam.theta / cam.phi absolutely rather than via deltas so
        // the user's preferred orbit / pan sign conventions above remain the
        // sole authority over drag-direction semantics.
        function setViewPreset(preset) {
            const poleLim = Math.PI / 2 - 0.01;
            switch (preset) {
                case "persp":
                    cam.theta = -Math.PI / 3;
                    cam.phi = 0.5;
                    cam.radius = modelSize * 1.1;
                    break;
                case "top":
                    cam.theta = 0;
                    cam.phi = poleLim;
                    cam.radius = modelSize * 1.2;
                    break;
                case "front":
                    cam.theta = -Math.PI / 2;
                    cam.phi = 0;
                    cam.radius = modelSize * 1.2;
                    break;
                case "side":
                    cam.theta = 0;
                    cam.phi = 0;
                    cam.radius = modelSize * 1.2;
                    break;
                default:
                    return;
            }
            cam.target = [0, 0, 0];
            requestDraw();
        }

        // Context-loss handling. On loss, suppress further draws (GL calls
        // against a lost context throw INVALID_OPERATION) and surface the
        // static fallback image if one is available. Full re-initialization
        // on restore (recompile shader, re-upload all buffers) is
        // nontrivial, so we leave the PNG fallback in place and keep
        // contextLost=true for this renderer instance.
        const onContextLost = function (ev) {
            ev.preventDefault();
            contextLost = true;
            rafPending = true;
            try { showFallback(canvas); } catch (e) { /* best-effort */ }
        };
        const onContextRestored = function () {
            // No-op: we already switched to the PNG fallback in
            // onContextLost. Future draws stay suppressed.
        };

        canvas.addEventListener("contextmenu", onContextMenu);
        canvas.addEventListener("mousedown", onMouseDown);
        window.addEventListener("mousemove", onMouseMove);
        window.addEventListener("mouseup", onMouseUp);
        canvas.addEventListener("wheel", onWheel, { passive: false });
        canvas.addEventListener("dblclick", onDblClick);
        canvas.addEventListener("webglcontextlost", onContextLost);
        canvas.addEventListener("webglcontextrestored", onContextRestored);

        // Re-render on size changes (responsive layout).
        let resizeObserver = null;
        let onWindowResize = null;
        if (typeof ResizeObserver !== "undefined") {
            resizeObserver = new ResizeObserver(function () { requestDraw(); });
            resizeObserver.observe(canvas);
        } else {
            onWindowResize = function () { requestDraw(); };
            window.addEventListener("resize", onWindowResize);
        }

        // Kick off the first draw.
        requestDraw();

        function destroy() {
            // Remove every listener this renderer attached. Called by
            // initCanvas() before a replacement renderer binds to a new
            // canvas after an HTMX swap.
            canvas.removeEventListener("contextmenu", onContextMenu);
            canvas.removeEventListener("mousedown", onMouseDown);
            window.removeEventListener("mousemove", onMouseMove);
            window.removeEventListener("mouseup", onMouseUp);
            canvas.removeEventListener("wheel", onWheel);
            canvas.removeEventListener("dblclick", onDblClick);
            canvas.removeEventListener("webglcontextlost", onContextLost);
            canvas.removeEventListener("webglcontextrestored", onContextRestored);
            if (resizeObserver) {
                try { resizeObserver.disconnect(); } catch (e) { /* ignore */ }
                resizeObserver = null;
            }
            if (onWindowResize) {
                window.removeEventListener("resize", onWindowResize);
                onWindowResize = null;
            }
            // Drop any HUD subscribers bound to this renderer. The HUD
            // re-subscribes when a new canvas init binds new window.shipPreview
            // closures after an HTMX swap.
            frameSubs = [];
            loadedSubs = [];
            // Mark lost so any late raf callbacks short-circuit.
            contextLost = true;
            rafPending = true;
        }

        // --- HUD-facing helpers ---------------------------------------------

        function getCamera() {
            return {
                theta: cam.theta,
                phi: cam.phi,
                radius: cam.radius,
                target: [cam.target[0], cam.target[1], cam.target[2]],
                fov: cam.fov,
            };
        }

        function getStats() {
            return {
                fps: fpsEstimate,
                voxelCount: count,
                opaqueCount: opaqueCount,
                transCount: transCount,
            };
        }

        function onFrame(cb) {
            if (typeof cb !== "function") return function () {};
            frameSubs.push(cb);
            return function unsubscribe() {
                const idx = frameSubs.indexOf(cb);
                if (idx !== -1) frameSubs.splice(idx, 1);
            };
        }

        function onLoaded(cb) {
            if (typeof cb !== "function") return function () {};
            loadedSubs.push(cb);
            return function unsubscribe() {
                const idx = loadedSubs.indexOf(cb);
                if (idx !== -1) loadedSubs.splice(idx, 1);
            };
        }

        // Called by initCanvas() after buffer upload completes so the HUD
        // can refresh its voxel-count readout and thumbnails.
        function fireLoaded() {
            let genId = null;
            try {
                const scope = canvas.closest(".result-inner, .result");
                if (scope) genId = scope.getAttribute("data-gen-id");
            } catch (e) { /* no closest() in very old browsers */ }
            const detail = { voxelCount: count, genId: genId };
            try {
                canvas.dispatchEvent(new CustomEvent("ship-preview-loaded", { detail: detail }));
            } catch (e) { /* best-effort */ }
            for (let i = 0; i < loadedSubs.length; i++) {
                const cb = loadedSubs[i];
                if (typeof cb === "function") {
                    try { cb(detail); } catch (e) { /* swallow */ }
                }
            }
        }

        // Produce a PNG data URL at (approximately) the requested size.
        // Strategy: read the live GL canvas via toDataURL; if a target size
        // differs from the current canvas, downscale via a 2D offscreen.
        // If the context was lost, fall back to the static PNG fallback URL
        // stored on the canvas dataset by app.js.
        //
        // Caveat: the GL context is created without preserveDrawingBuffer,
        // so the browser may have cleared the backbuffer before toDataURL
        // runs. Calling draw() immediately before toDataURL reliably works
        // on Chromium / Firefox / Safari in practice because the clear
        // happens at the next composite boundary, not synchronously after
        // draw. The empty-image case falls back to the server-rendered PNG
        // URL stored on canvas.dataset.previewUrl.
        function snapshotPNG(size) {
            if (contextLost) return canvas.dataset.previewUrl || "";
            try {
                draw();
                const src = canvas.toDataURL("image/png");
                if (!src || src === "data:,") return canvas.dataset.previewUrl || "";
                if (!size || size <= 0) return src;
                const target = Math.max(1, Math.floor(size));
                const cw = canvas.width, ch = canvas.height;
                if (target >= cw && target >= ch) return src;
                const scale = Math.min(target / cw, target / ch);
                const outW = Math.max(1, Math.floor(cw * scale));
                const outH = Math.max(1, Math.floor(ch * scale));
                const off = document.createElement("canvas");
                off.width = outW;
                off.height = outH;
                const ctx = off.getContext("2d");
                if (!ctx) return src;
                // Paint the original dataURL into the offscreen via an <img>
                // synchronously-ish: the data URL is already in memory so the
                // image decodes near-immediately, but we still have to wait
                // for onload. Return a promise? Simpler: draw the GL canvas
                // directly — drawImage can take a canvas source.
                try {
                    ctx.drawImage(canvas, 0, 0, outW, outH);
                } catch (e) {
                    return src;
                }
                return off.toDataURL("image/png");
            } catch (e) {
                return canvas.dataset.previewUrl || "";
            }
        }

        function fullscreen() {
            const viewport = document.getElementById("viewport");
            const target = viewport || canvas;
            const req = target.requestFullscreen
                || target.webkitRequestFullscreen
                || target.mozRequestFullScreen
                || target.msRequestFullscreen;
            if (typeof req !== "function") return false;
            try {
                const ret = req.call(target);
                // Some vendors return a Promise, others undefined. Suppress
                // any rejection so we don't log noisy errors when the user
                // cancels the fullscreen request.
                if (ret && typeof ret.then === "function") {
                    ret.catch(function () { /* ignore */ });
                }
                return true;
            } catch (e) {
                return false;
            }
        }

        return {
            canvas: canvas,
            requestDraw: requestDraw,
            destroy: destroy,
            getFps: function () { return fpsEstimate; },
            getCount: function () { return count; },
            // HUD / Interactions API ------------------------------------------
            setView: setViewPreset,
            resetCamera: onDblClick,
            getCamera: getCamera,
            getStats: getStats,
            snapshotPNG: snapshotPNG,
            fullscreen: fullscreen,
            onFrame: onFrame,
            onLoaded: onLoaded,
            fireLoaded: fireLoaded,
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
        if (!canvas) return;
        // If this canvas already has a live renderer (e.g. HTMX re-ran the
        // afterSwap hook on a container that included it, or the same node
        // is being re-initialized), tear it down first so we don't
        // double-bind window-level listeners. Clearing previewBound lets
        // the same canvas node be re-initialized with fresh state.
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
                const r = makeRenderer(canvas, data);
                if (!r) {
                    showFallback(canvas);
                    return;
                }
                canvas.__renderer = r;
                const t1 = performance.now();
                // Attach timing info for debugging via browser devtools.
                canvas.__previewMs = t1 - t0;
                // Mark ready so test/automation code can detect first-paint.
                canvas.dataset.previewReady = "1";
                // Point window.shipPreview at the newest renderer so the HUD
                // and Interactions agent see live camera / stats / events.
                bindGlobalShipPreview(r);
                // Fire the loaded event after the global is bound so any
                // synchronous onLoaded subscriber added via the global sees
                // the same renderer it will later query for stats.
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
        const els = scope.querySelectorAll(".preview-canvas[data-voxels-url]");
        els.forEach(initCanvas);
    }

    // Expose a tiny API for app.js and devtools.
    window.SpaceshipPreview = {
        initAll: initAll,
        initCanvas: initCanvas,
    };

    // --- window.shipPreview (HUD / Interactions API) ------------------------
    //
    // A stable global facade that delegates to the currently-active renderer.
    // HTMX swaps replace the canvas on every generate; bindGlobalShipPreview
    // (called from the fetch `.then` handler) re-points these closures at the
    // new renderer. Subscribers added to the facade before any renderer
    // exists are buffered and re-attached on first bind.
    let activeRenderer = null;
    const pendingFrameSubs = [];
    const pendingLoadedSubs = [];

    function bindGlobalShipPreview(renderer) {
        activeRenderer = renderer;
        // Re-attach any subscribers that were registered before a renderer
        // existed (or while between renderers). We leave the pending arrays
        // in place so a subsequent swap re-binds them to the next renderer
        // too — HUD wants its subscription to survive generation cycles.
        for (let i = 0; i < pendingFrameSubs.length; i++) {
            try { renderer.onFrame(pendingFrameSubs[i]); } catch (e) { /* ignore */ }
        }
        for (let i = 0; i < pendingLoadedSubs.length; i++) {
            try { renderer.onLoaded(pendingLoadedSubs[i]); } catch (e) { /* ignore */ }
        }
    }

    window.shipPreview = {
        setView: function (preset) {
            if (activeRenderer && typeof activeRenderer.setView === "function") {
                activeRenderer.setView(preset);
            }
        },
        resetCamera: function () {
            if (activeRenderer && typeof activeRenderer.resetCamera === "function") {
                activeRenderer.resetCamera();
            }
        },
        getCamera: function () {
            return (activeRenderer && typeof activeRenderer.getCamera === "function")
                ? activeRenderer.getCamera()
                : null;
        },
        getStats: function () {
            return (activeRenderer && typeof activeRenderer.getStats === "function")
                ? activeRenderer.getStats()
                : null;
        },
        snapshotPNG: function (size) {
            if (activeRenderer && typeof activeRenderer.snapshotPNG === "function") {
                return activeRenderer.snapshotPNG(size);
            }
            return "";
        },
        fullscreen: function () {
            if (activeRenderer && typeof activeRenderer.fullscreen === "function") {
                return activeRenderer.fullscreen();
            }
            // Fall back to requesting fullscreen on the viewport directly so
            // the HUD button still does something useful before first load.
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
            if (activeRenderer && typeof activeRenderer.onFrame === "function") {
                activeRenderer.onFrame(cb);
            }
            return function unsubscribe() {
                const idx = pendingFrameSubs.indexOf(cb);
                if (idx !== -1) pendingFrameSubs.splice(idx, 1);
                // No way to detach from a destroyed renderer; its frameSubs
                // are already cleared. The current renderer's frameSubs
                // retain this cb until it's destroyed, which is acceptable
                // because the user closure is idempotent per-frame.
            };
        },
        onLoaded: function (cb) {
            if (typeof cb !== "function") return function () {};
            pendingLoadedSubs.push(cb);
            if (activeRenderer && typeof activeRenderer.onLoaded === "function") {
                activeRenderer.onLoaded(cb);
            }
            return function unsubscribe() {
                const idx = pendingLoadedSubs.indexOf(cb);
                if (idx !== -1) pendingLoadedSubs.splice(idx, 1);
            };
        },
    };

    document.addEventListener("DOMContentLoaded", function () { initAll(document); });

    // Re-initialize after an HTMX swap brings in fresh _result.html markup.
    document.body.addEventListener("htmx:afterSwap", function (ev) {
        initAll(ev.target || document);
    });
})();
