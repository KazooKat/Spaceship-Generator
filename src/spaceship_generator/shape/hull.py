"""Hull placement — tapered ellipsoid-of-revolution along Z."""

from __future__ import annotations

import numpy as np

from ..palette import Role
from ..structure_styles import (
    HullStyle,
    blended_hull_radii,
    hull_rx_ry_scale,
    profile_fn,
)
from .core import ShapeParams

# Maximum hull-noise displacement, in cells, at amplitude == 1.0. The
# post-pass clamps the final silhouette perturbation to ±this many cells
# so even a "max noise" run stays a recognizable spaceship rather than a
# blob of asteroid debris.
_HULL_NOISE_MAX_DISPLACEMENT = 2


def _place_hull(grid: np.ndarray, rng: np.random.Generator, params: ShapeParams) -> None:
    """Fill a tapered ellipsoid-of-revolution along Z with HULL voxels.

    The taper profile, and the X/Y radius scaling, are picked per
    :attr:`ShapeParams.structure_style`. ``FRIGATE`` preserves the original
    behavior exactly.
    """
    W, H, L = grid.shape
    cx, cy = (W - 1) / 2.0, (H - 1) / 2.0

    # Slight random thickness variation per axis so not every ship is identical.
    thickness = 0.9 + rng.random() * 0.1

    # Style dispatchers: profile function + rx/ry scale multipliers.
    profile_f = profile_fn(params.structure_style)
    rx_scale, ry_scale = hull_rx_ry_scale(params.structure_style)

    for z in range(L):
        t = z / max(L - 1, 1)          # 0 at rear, 1 at nose
        profile = profile_f(t)         # [0..1] bell-ish
        rx = max(0.5, (W * 0.5 - 0.5) * profile * thickness * rx_scale)
        ry = max(
            0.5, (H * 0.5 - 0.5) * profile * thickness * 0.7 * ry_scale
        )  # flatter than wide

        for x in range(W):
            for y in range(H):
                dx = (x - cx) / rx
                dy = (y - cy) / ry
                if dx * dx + dy * dy <= 1.0:
                    grid[x, y, z] = Role.HULL


def _place_hull_blend(
    grid: np.ndarray,
    rng: np.random.Generator,
    front: HullStyle,
    rear: HullStyle,
    *,
    midband: float = 0.25,
) -> None:
    """Stamp HULL voxels by blending two :class:`HullStyle` profiles along Z.

    Mirrors :func:`_place_hull`'s thickness jitter so the blended hull keeps
    the same family of subtle per-seed variation, but the per-Z radii are
    sourced from :func:`blended_hull_radii` rather than a single style. The
    blend is a cosine-weighted ramp centred at ``z = L/2`` over ``midband``
    of the length (default 25%); outside the ramp each end is the pure
    style. The ``rng`` argument supplies the same thickness jitter as the
    legacy hull placer so determinism with the rest of the pipeline holds.
    """
    if not isinstance(front, HullStyle):
        raise ValueError(
            f"_place_hull_blend expects HullStyle for front; got "
            f"{type(front).__name__}"
        )
    if not isinstance(rear, HullStyle):
        raise ValueError(
            f"_place_hull_blend expects HullStyle for rear; got "
            f"{type(rear).__name__}"
        )

    W, H, L = grid.shape
    cx, cy = (W - 1) / 2.0, (H - 1) / 2.0

    # Match the legacy hull's thickness jitter so the RNG stream stays in
    # lockstep with everything downstream — keeps the seed contract intact.
    thickness = 0.9 + rng.random() * 0.1

    for z in range(L):
        t = z / max(L - 1, 1)
        rx_factor, ry_factor = blended_hull_radii(
            front, rear, t, midband=midband
        )
        rx = max(0.5, (W * 0.5 - 0.5) * thickness * rx_factor)
        ry = max(0.5, (H * 0.5 - 0.5) * thickness * 0.7 * ry_factor)
        for x in range(W):
            for y in range(H):
                dx = (x - cx) / rx
                dy = (y - cy) / ry
                if dx * dx + dy * dy <= 1.0:
                    grid[x, y, z] = Role.HULL


def _hash_noise_field(W: int, H: int, L: int, sub_seed: int) -> np.ndarray:
    """Return a ``(W, H, L)`` ``float32`` noise field in ``[-1, 1]``.

    Cheap deterministic per-cell hash noise — no fancy gradient interpolation
    (we only need a stable pseudo-random scalar at every cell), but enough
    spatial coherence for a believable "asteroid pitting" look because the
    hash is salted by the integer cell coordinates and the caller's
    ``sub_seed`` (derived from the main pipeline seed). This is byte-stable
    across NumPy versions: no floating-point hashing.
    """
    # Build a single int64 mix per cell: xs * P1 + ys * P2 + zs * P3 + sub.
    # Primes chosen to fit signed int64 (so they round-trip through NumPy
    # arithmetic without OverflowError); the exact constants don't matter
    # for distribution quality — the XOR-shift mixer below scrambles them.
    xs = np.arange(W, dtype=np.int64).reshape(W, 1, 1)
    ys = np.arange(H, dtype=np.int64).reshape(1, H, 1)
    zs = np.arange(L, dtype=np.int64).reshape(1, 1, L)
    h = (
        xs * np.int64(73856093)
        + ys * np.int64(19349663)
        + zs * np.int64(83492791)
        + np.int64(sub_seed)
    )
    # XOR-shift mixer (Murmur-style finalizer constants trimmed to fit int64).
    h ^= (h >> np.int64(33))
    h = h * np.int64(2246822519)  # 0x85EBCA77
    h ^= (h >> np.int64(29))
    h = h * np.int64(3266489917)  # 0xC2B2AE3D
    h ^= (h >> np.int64(32))
    # Map the unsigned bottom 24 bits to ``[-1, 1]`` so the field is
    # symmetric around zero and quantization is granular enough that the
    # ``threshold`` cutoffs below behave smoothly.
    u = (h & np.int64(0xFFFFFF)).astype(np.float32) / np.float32(0xFFFFFF)
    return (u * np.float32(2.0) - np.float32(1.0))


def _apply_hull_noise(
    grid: np.ndarray, rng: np.random.Generator, params: ShapeParams
) -> None:
    """Distort the hull membrane with deterministic procedural noise.

    No-op when ``params.hull_noise == 0`` (the caller already short-circuits
    that case to keep the legacy pipeline byte-identical). For ``> 0``:

    * Cells already classified as :attr:`Role.HULL` whose 6-neighbourhood
      touches :attr:`Role.EMPTY` form the *inner shell*. A subset of that
      shell is eroded (rewritten to ``EMPTY``) where the noise field dips
      low enough.
    * Cells classified as ``EMPTY`` adjacent to ``HULL`` form the *outer
      band*. A subset is filled with ``HULL`` where the noise field rises
      high enough.

    The cutoff ``threshold = 1.0 - amplitude`` shrinks toward zero (more
    cells flipped) as amplitude grows. To bound the silhouette displacement
    the iteration runs at most :data:`_HULL_NOISE_MAX_DISPLACEMENT` times —
    each iteration can only move the boundary by one cell so the cumulative
    perturbation stays within ±2 cells. Cockpit / engine / wing voxels are
    never overwritten because the post-pass runs *before* those parts are
    placed.

    Determinism: the noise sub-seed is drawn from ``rng`` (which itself is
    seeded from the main pipeline seed), so two runs with the same
    ``(seed, hull_noise)`` pair produce byte-identical grids. The single
    ``rng.integers`` draw also keeps downstream RNG consumers in lockstep
    with the legacy pipeline whenever ``hull_noise > 0`` is opted into.
    """
    amplitude = float(params.hull_noise)
    if amplitude <= 0.0:
        # Belt-and-braces: caller already guards this, but never run on a
        # zero amplitude — we promise byte-identical output for the default.
        return

    # Iterations: 0 < amp <= 0.5 → 1 iter, 0.5 < amp <= 1.0 → 2 iters.
    iters = max(1, int(round(amplitude * _HULL_NOISE_MAX_DISPLACEMENT)))
    iters = min(iters, _HULL_NOISE_MAX_DISPLACEMENT)
    threshold = float(np.float32(1.0 - amplitude))

    # Single rng draw → derived sub-seed for the noise field. Doing exactly
    # one draw keeps the contract simple: if hull_noise > 0 the caller
    # consumes one extra ``rng`` integer, regardless of grid size or how
    # many iterations we end up running.
    sub_seed = int(rng.integers(0, 2**63 - 1, dtype=np.int64))

    W, H, L = grid.shape
    noise = _hash_noise_field(W, H, L, sub_seed)

    for it in range(iters):
        hull_mask = grid == Role.HULL
        if not hull_mask.any():
            return

        # 6-neighbourhood dilation of the empty mask gives "cells touching
        # at least one empty neighbour"; intersected with hull_mask that's
        # the inner shell (one-voxel-deep boundary on the hull side).
        empty_mask = grid == Role.EMPTY
        empty_dilated = np.zeros_like(empty_mask)
        empty_dilated[:, :, :] = empty_mask
        empty_dilated[1:, :, :] |= empty_mask[:-1, :, :]
        empty_dilated[:-1, :, :] |= empty_mask[1:, :, :]
        empty_dilated[:, 1:, :] |= empty_mask[:, :-1, :]
        empty_dilated[:, :-1, :] |= empty_mask[:, 1:, :]
        empty_dilated[:, :, 1:] |= empty_mask[:, :, :-1]
        empty_dilated[:, :, :-1] |= empty_mask[:, :, 1:]

        # Outer band: EMPTY cells with at least one HULL 6-neighbour.
        hull_dilated = np.zeros_like(hull_mask)
        hull_dilated[:, :, :] = hull_mask
        hull_dilated[1:, :, :] |= hull_mask[:-1, :, :]
        hull_dilated[:-1, :, :] |= hull_mask[1:, :, :]
        hull_dilated[:, 1:, :] |= hull_mask[:, :-1, :]
        hull_dilated[:, :-1, :] |= hull_mask[:, 1:, :]
        hull_dilated[:, :, 1:] |= hull_mask[:, :, :-1]
        hull_dilated[:, :, :-1] |= hull_mask[:, :, 1:]

        inner_shell = hull_mask & empty_dilated
        outer_band = empty_mask & hull_dilated

        # Vary the noise field per iteration so two passes don't reinforce
        # exactly the same cells (which would just dilate by 2 in lockstep
        # with the ``noise > threshold`` cells). XOR-flipping the sign
        # gives a different mask without recomputing the field.
        if it == 0:
            field = noise
        else:
            field = -noise

        erode = inner_shell & (field < -threshold)
        grow = outer_band & (field > threshold)

        # Apply: erosion first so a cell flipped to EMPTY this iteration
        # cannot also be re-flipped to HULL by ``grow`` in the same pass
        # (``grow`` was computed against the pre-erosion ``empty_mask``).
        if erode.any():
            grid[erode] = Role.EMPTY
        if grow.any():
            grid[grow] = Role.HULL
