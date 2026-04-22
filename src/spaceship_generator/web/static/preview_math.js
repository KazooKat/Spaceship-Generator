// preview_math.js — tiny mat4/vec3 helpers for the WebGL voxel renderer.
// Exposes functions on window.PreviewMath for use by preview_renderer.js.

(function () {
    "use strict";

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

    // base64 → Uint8Array (browser-safe)
    function base64ToBytes(b64) {
        const binary = atob(b64);
        const len = binary.length;
        const out = new Uint8Array(len);
        for (let i = 0; i < len; i++) out[i] = binary.charCodeAt(i);
        return out;
    }

    window.PreviewMath = {
        mat4Identity: mat4Identity,
        mat4Perspective: mat4Perspective,
        mat4LookAt: mat4LookAt,
        mat4Multiply: mat4Multiply,
        base64ToBytes: base64ToBytes,
    };
})();
