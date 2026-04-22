// preview_renderer.js — cube geometry, GLSL shaders, WebGL renderer + camera.
// Depends on preview_math.js (window.PreviewMath) loaded before this file.
// Exposes window.PreviewRenderer = { makeRenderer, showFallback }.

(function () {
    "use strict";

    // --- cube geometry --------------------------------------------------------
    function buildCubeVerts() {
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
    const VS_WEBGL1 = [
        "precision highp float;",
        "attribute vec3 aPos; attribute vec3 aNormal; attribute vec3 aOffset; attribute vec4 aColor;",
        "uniform mat4 uProj; uniform mat4 uView;",
        "varying vec3 vNormal; varying vec4 vColor;",
        "void main() { vec3 world = aPos + aOffset;",
        "  gl_Position = uProj * uView * vec4(world, 1.0);",
        "  vNormal = aNormal; vColor = aColor; }",
    ].join("\n");

    const FS_WEBGL1 = [
        "precision highp float;",
        "varying vec3 vNormal; varying vec4 vColor;",
        "uniform vec3 uLightDir; uniform float uAmbient;",
        "void main() { float d = max(dot(normalize(vNormal), normalize(uLightDir)), 0.0);",
        "  float intensity = uAmbient + (1.0 - uAmbient) * d;",
        "  gl_FragColor = vec4(vColor.rgb * intensity, vColor.a); }",
    ].join("\n");

    const VS_WEBGL2 = [
        "#version 300 es", "precision highp float;",
        "in vec3 aPos; in vec3 aNormal; in vec3 aOffset; in vec4 aColor;",
        "uniform mat4 uProj; uniform mat4 uView;",
        "out vec3 vNormal; out vec4 vColor;",
        "void main() { vec3 world = aPos + aOffset;",
        "  gl_Position = uProj * uView * vec4(world, 1.0);",
        "  vNormal = aNormal; vColor = aColor; }",
    ].join("\n");

    const FS_WEBGL2 = [
        "#version 300 es", "precision highp float;",
        "in vec3 vNormal; in vec4 vColor;",
        "uniform vec3 uLightDir; uniform float uAmbient;",
        "out vec4 outColor;",
        "void main() { float d = max(dot(normalize(vNormal), normalize(uLightDir)), 0.0);",
        "  float intensity = uAmbient + (1.0 - uAmbient) * d;",
        "  outColor = vec4(vColor.rgb * intensity, vColor.a); }",
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

    function showFallback(canvas) {
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

    // --- the renderer ---------------------------------------------------------
    function makeRenderer(canvas, data) {
        const math = window.PreviewMath;
        const W = data.dims[0], H = data.dims[1], L = data.dims[2];
        const count = data.count;
        const bytes = math.base64ToBytes(data.voxels);
        const i16 = new Int16Array(bytes.buffer, bytes.byteOffset, (bytes.byteLength / 2) | 0);

        const ALPHA_OPAQUE = 0.99;
        const cx = W / 2, cy = H / 2, cz = L / 2;
        let opaqueCount = 0, transCount = 0;
        for (let i = 0; i < count; i++) {
            const role = i16[i * 4 + 3];
            const c = data.colors[String(role)];
            const a = (c && c[3] != null) ? c[3] : 1.0;
            if (a >= ALPHA_OPAQUE) opaqueCount++; else transCount++;
        }

        const opaqueOffsets = new Float32Array(opaqueCount * 3);
        const opaqueColors  = new Float32Array(opaqueCount * 4);
        const transOffsets  = new Float32Array(transCount * 3);
        const transColors   = new Float32Array(transCount * 4);

        let oi = 0, ti = 0;
        for (let i = 0; i < count; i++) {
            const x = i16[i * 4 + 0], y = i16[i * 4 + 1], z = i16[i * 4 + 2];
            const role = i16[i * 4 + 3];
            const c = data.colors[String(role)] || [0.6, 0.6, 0.6, 1.0];
            const a = c[3] != null ? c[3] : 1.0;
            if (a >= ALPHA_OPAQUE) {
                opaqueOffsets[oi * 3] = x - cx; opaqueOffsets[oi * 3 + 1] = y - cy; opaqueOffsets[oi * 3 + 2] = z - cz;
                opaqueColors[oi * 4] = c[0]; opaqueColors[oi * 4 + 1] = c[1]; opaqueColors[oi * 4 + 2] = c[2]; opaqueColors[oi * 4 + 3] = a;
                oi++;
            } else {
                transOffsets[ti * 3] = x - cx; transOffsets[ti * 3 + 1] = y - cy; transOffsets[ti * 3 + 2] = z - cz;
                transColors[ti * 4] = c[0]; transColors[ti * 4 + 1] = c[1]; transColors[ti * 4 + 2] = c[2]; transColors[ti * 4 + 3] = a;
                ti++;
            }
        }

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

        let prog;
        try {
            const vs = compileShader(gl, gl.VERTEX_SHADER, isWebGL2 ? VS_WEBGL2 : VS_WEBGL1);
            const fs = compileShader(gl, gl.FRAGMENT_SHADER, isWebGL2 ? FS_WEBGL2 : FS_WEBGL1);
            prog = linkProgram(gl, vs, fs);
        } catch (e) { console.warn("WebGL init failed:", e); return null; }
        gl.useProgram(prog);

        const cube = buildCubeVerts();
        const posBuf = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
        gl.bufferData(gl.ARRAY_BUFFER, cube.pos, gl.STATIC_DRAW);
        const nrmBuf = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, nrmBuf);
        gl.bufferData(gl.ARRAY_BUFFER, cube.nrm, gl.STATIC_DRAW);

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

        function vad(loc, div) {
            if (isWebGL2) gl.vertexAttribDivisor(loc, div);
            else instancedExt.vertexAttribDivisorANGLE(loc, div);
        }
        gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
        gl.enableVertexAttribArray(aPos); gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 0, 0); vad(aPos, 0);
        gl.bindBuffer(gl.ARRAY_BUFFER, nrmBuf);
        gl.enableVertexAttribArray(aNormal); gl.vertexAttribPointer(aNormal, 3, gl.FLOAT, false, 0, 0); vad(aNormal, 0);
        gl.enableVertexAttribArray(aOffset); vad(aOffset, 1);
        gl.enableVertexAttribArray(aColor); vad(aColor, 1);

        function bindInstanceBuffers(offBuf, colBuf) {
            gl.bindBuffer(gl.ARRAY_BUFFER, offBuf);
            gl.vertexAttribPointer(aOffset, 3, gl.FLOAT, false, 0, 0);
            gl.bindBuffer(gl.ARRAY_BUFFER, colBuf);
            gl.vertexAttribPointer(aColor, 4, gl.FLOAT, false, 0, 0);
        }
        function drawInstances(n) {
            if (n <= 0) return;
            if (isWebGL2) gl.drawArraysInstanced(gl.TRIANGLES, 0, cube.count, n);
            else instancedExt.drawArraysInstancedANGLE(gl.TRIANGLES, 0, cube.count, n);
        }

        const uProj = gl.getUniformLocation(prog, "uProj");
        const uView = gl.getUniformLocation(prog, "uView");
        const uLightDir = gl.getUniformLocation(prog, "uLightDir");
        const uAmbient = gl.getUniformLocation(prog, "uAmbient");

        gl.enable(gl.DEPTH_TEST); gl.enable(gl.CULL_FACE); gl.cullFace(gl.BACK);
        gl.clearColor(0.039, 0.047, 0.067, 0.0);

        const modelSize = Math.hypot(W, H, L);
        const cam = {
            theta: -Math.PI / 3, phi: 0.5, radius: modelSize * 1.1,
            target: [0, 0, 0],
            minRadius: Math.max(W, H, L) * 0.4,
            maxRadius: modelSize * 6,
            fov: Math.PI / 4, near: 0.1, far: modelSize * 20 + 100,
        };

        function computeEye() {
            const cp = Math.cos(cam.phi), sp = Math.sin(cam.phi);
            const ct = Math.cos(cam.theta), st = Math.sin(cam.theta);
            return [cam.target[0] + cam.radius * cp * ct,
                    cam.target[1] + cam.radius * sp,
                    cam.target[2] + cam.radius * cp * st];
        }

        let rafPending = false, contextLost = false;
        let frameCount = 0, frameCountWindowStart = performance.now(), fpsEstimate = 0;
        let frameSubs = [], loadedSubs = [], lastFrameDispatch = 0;
        const FRAME_DISPATCH_MS = 100;
        canvas.__preview = { getFps: function () { return fpsEstimate; }, getCount: function () { return count; } };

        function resizeIfNeeded() {
            const dpr = Math.max(1, window.devicePixelRatio || 1);
            const w = Math.max(1, Math.floor(canvas.clientWidth * dpr));
            const h = Math.max(1, Math.floor(canvas.clientHeight * dpr));
            if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
        }

        const transOffsetsSorted = new Float32Array(transCount * 3);
        const transColorsSorted  = new Float32Array(transCount * 4);
        const transDistSq = new Float32Array(transCount);
        let lastSortDirX = 0, lastSortDirY = 0, lastSortDirZ = 0, transSortValid = false;
        const SORT_REBUILD_COS = Math.cos(15 * Math.PI / 180);

        function maybeResortTranslucent() {
            if (transCount <= 0) return false;
            const eye = computeEye();
            let vx = cam.target[0] - eye[0], vy = cam.target[1] - eye[1], vz = cam.target[2] - eye[2];
            const vlen = Math.hypot(vx, vy, vz) || 1;
            vx /= vlen; vy /= vlen; vz /= vlen;
            if (transSortValid) {
                const dot = vx * lastSortDirX + vy * lastSortDirY + vz * lastSortDirZ;
                if (dot >= SORT_REBUILD_COS) return false;
            }
            const orderArr = new Array(transCount);
            for (let i = 0; i < transCount; i++) {
                const ox = transOffsets[i * 3], oy = transOffsets[i * 3 + 1], oz = transOffsets[i * 3 + 2];
                const dx = ox - eye[0], dy = oy - eye[1], dz = oz - eye[2];
                transDistSq[i] = dx * dx + dy * dy + dz * dz; orderArr[i] = i;
            }
            orderArr.sort(function (a, b) { return transDistSq[b] - transDistSq[a]; });
            for (let i = 0; i < transCount; i++) {
                const src = orderArr[i];
                transOffsetsSorted[i * 3] = transOffsets[src * 3]; transOffsetsSorted[i * 3 + 1] = transOffsets[src * 3 + 1]; transOffsetsSorted[i * 3 + 2] = transOffsets[src * 3 + 2];
                transColorsSorted[i * 4] = transColors[src * 4]; transColorsSorted[i * 4 + 1] = transColors[src * 4 + 1]; transColorsSorted[i * 4 + 2] = transColors[src * 4 + 2]; transColorsSorted[i * 4 + 3] = transColors[src * 4 + 3];
            }
            gl.bindBuffer(gl.ARRAY_BUFFER, offBufTrans); gl.bufferData(gl.ARRAY_BUFFER, transOffsetsSorted, gl.DYNAMIC_DRAW);
            gl.bindBuffer(gl.ARRAY_BUFFER, colBufTrans); gl.bufferData(gl.ARRAY_BUFFER, transColorsSorted, gl.DYNAMIC_DRAW);
            lastSortDirX = vx; lastSortDirY = vy; lastSortDirZ = vz; transSortValid = true;
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
            const up = Math.abs(Math.cos(cam.phi)) < 0.05 ? [0, 0, 1] : [0, 1, 0];
            const view = math.mat4LookAt(eye, cam.target, up);
            const proj = math.mat4Perspective(cam.fov, w / h, cam.near, cam.far);
            gl.useProgram(prog);
            gl.uniformMatrix4fv(uProj, false, proj); gl.uniformMatrix4fv(uView, false, view);
            gl.uniform3f(uLightDir, 0.5, 1.0, 0.35); gl.uniform1f(uAmbient, 0.55);
            gl.disable(gl.BLEND); gl.depthMask(true); gl.enable(gl.DEPTH_TEST);
            bindInstanceBuffers(offBufOpaque, colBufOpaque); drawInstances(opaqueCount);
            if (transCount > 0) {
                maybeResortTranslucent();
                gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
                gl.depthMask(false);
                bindInstanceBuffers(offBufTrans, colBufTrans); drawInstances(transCount);
                gl.depthMask(true); gl.disable(gl.BLEND);
            }
            frameCount++;
            const now = performance.now(), elapsed = now - frameCountWindowStart;
            if (elapsed > 500) { fpsEstimate = (frameCount * 1000) / elapsed; frameCount = 0; frameCountWindowStart = now; }
            if (now - lastFrameDispatch >= FRAME_DISPATCH_MS) {
                lastFrameDispatch = now;
                const detail = { fps: fpsEstimate, voxelCount: count, opaqueCount: opaqueCount, transCount: transCount };
                try { canvas.dispatchEvent(new CustomEvent("ship-preview-stats", { detail: detail })); } catch (e) { /* old browsers */ }
                for (let i = 0; i < frameSubs.length; i++) { try { if (typeof frameSubs[i] === "function") frameSubs[i](detail); } catch (e) { /* swallow */ } }
            }
        }

        function requestDraw() { if (rafPending) return; rafPending = true; requestAnimationFrame(draw); }

        // --- interaction ------------------------------------------------------
        let mode = null, lastX = 0, lastY = 0;
        const ORBIT_SENSITIVITY = 0.008;
        const onContextMenu = function (ev) { ev.preventDefault(); };
        const onMouseDown = function (ev) {
            const isPan = ev.button === 1 || ev.button === 2 || (ev.button === 0 && ev.shiftKey);
            mode = isPan ? "pan" : (ev.button === 0 ? "orbit" : null);
            if (!mode) return;
            lastX = ev.clientX; lastY = ev.clientY;
            canvas.classList.add("dragging");
            if (mode === "pan") canvas.classList.add("panning");
            ev.preventDefault();
        };
        const onMouseMove = function (ev) {
            if (!mode) return;
            const dx = ev.clientX - lastX, dy = ev.clientY - lastY;
            lastX = ev.clientX; lastY = ev.clientY;
            if (mode === "orbit") {
                cam.theta += dx * ORBIT_SENSITIVITY; cam.phi += dy * ORBIT_SENSITIVITY;
                const lim = Math.PI / 2 - 0.01;
                if (cam.phi > lim) cam.phi = lim; if (cam.phi < -lim) cam.phi = -lim;
            } else if (mode === "pan") {
                const eye = computeEye();
                const fx = cam.target[0] - eye[0], fy = cam.target[1] - eye[1], fz = cam.target[2] - eye[2];
                const flen = Math.hypot(fx, fy, fz) || 1;
                const fnx = fx / flen, fny = fy / flen, fnz = fz / flen;
                let rx = fny * 0 - fnz * 1, ry = fnz * 0 - fnx * 0, rz = fnx * 1 - fny * 0;
                const rlen = Math.hypot(rx, ry, rz) || 1;
                rx /= rlen; ry /= rlen; rz /= rlen;
                const ux = ry * fnz - rz * fny, uy = rz * fnx - rx * fnz, uz = rx * fny - ry * fnx;
                const tanHalfFov = Math.tan(cam.fov / 2);
                const pxScaleY = (2 * cam.radius * tanHalfFov) / Math.max(1, canvas.clientHeight);
                const pxScaleX = (2 * cam.radius * tanHalfFov) / Math.max(1, canvas.clientWidth);
                cam.target[0] += -rx * dx * pxScaleX + ux * dy * pxScaleY;
                cam.target[1] += -ry * dx * pxScaleX + uy * dy * pxScaleY;
                cam.target[2] += -rz * dx * pxScaleX + uz * dy * pxScaleY;
            }
            requestDraw();
        };
        const onMouseUp = function () { if (!mode) return; mode = null; canvas.classList.remove("dragging"); canvas.classList.remove("panning"); };
        const onWheel = function (ev) {
            ev.preventDefault();
            cam.radius *= Math.exp(ev.deltaY * 0.0015);
            if (cam.radius < cam.minRadius) cam.radius = cam.minRadius;
            if (cam.radius > cam.maxRadius) cam.radius = cam.maxRadius;
            requestDraw();
        };
        const onDblClick = function () {
            cam.theta = -Math.PI / 3; cam.phi = 0.5; cam.radius = modelSize * 1.1; cam.target = [0, 0, 0];
            requestDraw();
        };

        function setViewPreset(preset) {
            const poleLim = Math.PI / 2 - 0.01;
            if (preset === "persp") { cam.theta = -Math.PI / 3; cam.phi = 0.5; cam.radius = modelSize * 1.1; }
            else if (preset === "top") { cam.theta = 0; cam.phi = poleLim; cam.radius = modelSize * 1.2; }
            else if (preset === "front") { cam.theta = -Math.PI / 2; cam.phi = 0; cam.radius = modelSize * 1.2; }
            else if (preset === "side") { cam.theta = 0; cam.phi = 0; cam.radius = modelSize * 1.2; }
            else return;
            cam.target = [0, 0, 0]; requestDraw();
        }

        const onContextLost = function (ev) {
            ev.preventDefault(); contextLost = true; rafPending = true;
            try { showFallback(canvas); } catch (e) { /* best-effort */ }
        };
        const onContextRestored = function () { /* no-op: fallback already shown */ };

        canvas.addEventListener("contextmenu", onContextMenu);
        canvas.addEventListener("mousedown", onMouseDown);
        window.addEventListener("mousemove", onMouseMove);
        window.addEventListener("mouseup", onMouseUp);
        canvas.addEventListener("wheel", onWheel, { passive: false });
        canvas.addEventListener("dblclick", onDblClick);
        canvas.addEventListener("webglcontextlost", onContextLost);
        canvas.addEventListener("webglcontextrestored", onContextRestored);

        let resizeObserver = null, onWindowResize = null;
        if (typeof ResizeObserver !== "undefined") {
            resizeObserver = new ResizeObserver(function () { requestDraw(); });
            resizeObserver.observe(canvas);
        } else {
            onWindowResize = function () { requestDraw(); };
            window.addEventListener("resize", onWindowResize);
        }
        requestDraw();

        function destroy() {
            canvas.removeEventListener("contextmenu", onContextMenu);
            canvas.removeEventListener("mousedown", onMouseDown);
            window.removeEventListener("mousemove", onMouseMove);
            window.removeEventListener("mouseup", onMouseUp);
            canvas.removeEventListener("wheel", onWheel);
            canvas.removeEventListener("dblclick", onDblClick);
            canvas.removeEventListener("webglcontextlost", onContextLost);
            canvas.removeEventListener("webglcontextrestored", onContextRestored);
            if (resizeObserver) { try { resizeObserver.disconnect(); } catch (e) { /* ignore */ } resizeObserver = null; }
            if (onWindowResize) { window.removeEventListener("resize", onWindowResize); onWindowResize = null; }
            frameSubs = []; loadedSubs = []; contextLost = true; rafPending = true;
        }

        function getCamera() { return { theta: cam.theta, phi: cam.phi, radius: cam.radius, target: [cam.target[0], cam.target[1], cam.target[2]], fov: cam.fov }; }
        function getStats() { return { fps: fpsEstimate, voxelCount: count, opaqueCount: opaqueCount, transCount: transCount }; }
        function onFrame(cb) {
            if (typeof cb !== "function") return function () {};
            frameSubs.push(cb);
            return function () { const idx = frameSubs.indexOf(cb); if (idx !== -1) frameSubs.splice(idx, 1); };
        }
        function onLoaded(cb) {
            if (typeof cb !== "function") return function () {};
            loadedSubs.push(cb);
            return function () { const idx = loadedSubs.indexOf(cb); if (idx !== -1) loadedSubs.splice(idx, 1); };
        }
        function fireLoaded() {
            let genId = null;
            try { const scope = canvas.closest(".result-inner, .result"); if (scope) genId = scope.getAttribute("data-gen-id"); } catch (e) { /* old browsers */ }
            const detail = { voxelCount: count, genId: genId };
            try { canvas.dispatchEvent(new CustomEvent("ship-preview-loaded", { detail: detail })); } catch (e) { /* best-effort */ }
            for (let i = 0; i < loadedSubs.length; i++) { try { if (typeof loadedSubs[i] === "function") loadedSubs[i](detail); } catch (e) { /* swallow */ } }
        }
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
                const off = document.createElement("canvas");
                off.width = Math.max(1, Math.floor(cw * scale));
                off.height = Math.max(1, Math.floor(ch * scale));
                const ctx = off.getContext("2d");
                if (!ctx) return src;
                try { ctx.drawImage(canvas, 0, 0, off.width, off.height); } catch (e) { return src; }
                return off.toDataURL("image/png");
            } catch (e) { return canvas.dataset.previewUrl || ""; }
        }
        function fullscreen() {
            const viewport = document.getElementById("viewport");
            const target = viewport || canvas;
            const req = target.requestFullscreen || target.webkitRequestFullscreen || target.mozRequestFullScreen || target.msRequestFullscreen;
            if (typeof req !== "function") return false;
            try { const ret = req.call(target); if (ret && typeof ret.then === "function") ret.catch(function () {}); return true; } catch (e) { return false; }
        }

        return {
            canvas: canvas, requestDraw: requestDraw, destroy: destroy,
            getFps: function () { return fpsEstimate; }, getCount: function () { return count; },
            setView: setViewPreset, resetCamera: onDblClick,
            getCamera: getCamera, getStats: getStats,
            snapshotPNG: snapshotPNG, fullscreen: fullscreen,
            onFrame: onFrame, onLoaded: onLoaded, fireLoaded: fireLoaded,
        };
    }

    window.PreviewRenderer = { makeRenderer: makeRenderer, showFallback: showFallback };
})();
