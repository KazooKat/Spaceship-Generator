"""Fleet planning — parameter sets for N visually-related ships.

A *fleet* is a collection of ships that share a palette and a degree of
stylistic coherence (common hull + engine archetypes). This module decides
the *parameters* for each ship; it does not build any voxel grids itself.
Callers pass the resulting :class:`GeneratedShip` records into
:func:`spaceship_generator.generator.generate` to actually build each ship.

Design notes
------------
* Deterministic: same :class:`FleetParams` → same list, byte-for-byte.
* Size tiers are centered dimensions with small deterministic jitter so
  fleets of the "same" tier don't produce identical dims.
* ``style_coherence`` linearly interpolates the probability that any given
  ship deviates from the fleet's base hull/engine archetype. Coherence of
  1.0 means every ship shares the same hull + engine style; coherence of
  0.0 means each ship gets an independent random pick.
* Wing style is always chosen per-ship. Coherence intentionally does not
  cover it — fleets often mix wing silhouettes even when hull/engine read
  as a matched set.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .engine_styles import EngineStyle
from .shape import CockpitStyle
from .structure_styles import HullStyle
from .wing_styles import WingStyle

__all__ = [
    "FleetParams",
    "GeneratedShip",
    "SIZE_TIERS",
    "generate_fleet",
]


# ---------------------------------------------------------------------------
# Size tier table
# ---------------------------------------------------------------------------
# Each entry is the *center* (width_max, height_max, length) triple for that
# tier. ``generate_fleet`` applies a small deterministic jitter so repeated
# ships in the same tier aren't identical in dims. "mixed" is handled by
# sampling from this set per-ship.
SIZE_TIERS: dict[str, tuple[int, int, int]] = {
    "small":   (15, 10, 25),
    "mid":     (25, 13, 45),
    "large":   (40, 18, 70),
    "capital": (70, 25, 120),
}

# Bounds around each tier center used to (a) jitter dims and (b) validate that
# a ship reported as being in a tier sits inside those bounds. Chosen so the
# jitter window never crosses into the next tier.
_TIER_TOLERANCE: dict[str, tuple[int, int, int]] = {
    "small":   (3, 2, 4),
    "mid":     (4, 2, 6),
    "large":   (6, 3, 10),
    "capital": (8, 4, 15),
}

# Enums from which per-ship deviations are sampled. Stored as tuples so they
# stay index-stable for deterministic .choice() selection.
_HULL_STYLES: tuple[HullStyle, ...] = tuple(HullStyle)
_ENGINE_STYLES: tuple[EngineStyle, ...] = tuple(EngineStyle)
_WING_STYLES: tuple[WingStyle, ...] = tuple(WingStyle)
_COCKPIT_STYLES: tuple[CockpitStyle, ...] = tuple(CockpitStyle)


@dataclass
class FleetParams:
    """Inputs for :func:`generate_fleet`.

    Attributes
    ----------
    count:
        Number of ships in the fleet. Must be ``>= 0``.
    palette:
        Palette name (e.g. ``"sci_fi_industrial"``). Copied verbatim onto
        every ship so the fleet reads as a matched set colour-wise.
    size_tier:
        One of ``"small"``, ``"mid"``, ``"large"``, ``"capital"``, or
        ``"mixed"``. ``"mixed"`` samples per ship from the four concrete
        tiers with a decreasing-size distribution (escort-heavy).
    style_coherence:
        ``0.0`` → every ship random; ``1.0`` → every ship shares the fleet
        base hull + engine archetype. Must be in ``[0.0, 1.0]``.
    cockpit_coherence:
        Analogous to ``style_coherence`` but for cockpit style. Only
        takes effect when ``weapon_count_per_ship > 0``; otherwise
        ``cockpit_style`` stays ``None`` on every ship and legacy
        determinism is preserved byte-for-byte. Must be in
        ``[0.0, 1.0]``.
    weapon_count_per_ship:
        Number of weapons planned per ship. ``0`` (the default) keeps
        the fleet weapon-free and preserves legacy byte-for-byte output.
        Must be ``>= 0``.
    seed:
        Integer seed. Same seed + same params = same fleet list.
    """

    count: int
    palette: str
    size_tier: str = "mixed"
    style_coherence: float = 0.7
    cockpit_coherence: float = 0.7
    weapon_count_per_ship: int = 0
    seed: int = 0


@dataclass(frozen=True)
class GeneratedShip:
    """One planned ship: parameters only, no voxel grid.

    Pass this to :func:`spaceship_generator.generator.generate` to actually
    build the ship. ``dims`` is ``(width_max, height_max, length)``.

    ``cockpit_style`` is ``None`` whenever the parent
    :class:`FleetParams` had ``weapon_count_per_ship == 0`` (the default);
    in that mode the fleet planner is not asked to reason about cockpits
    and legacy output is preserved byte-for-byte. ``weapon_count`` mirrors
    ``FleetParams.weapon_count_per_ship`` and is ``0`` by default.
    """

    seed: int
    dims: tuple[int, int, int]
    hull_style: HullStyle | None
    engine_style: EngineStyle | None
    wing_style: WingStyle | None
    greeble_density: float
    palette: str
    cockpit_style: CockpitStyle | None = None
    weapon_count: int = 0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate(params: FleetParams) -> None:
    if params.count < 0:
        raise ValueError(f"count must be >= 0; got {params.count!r}")
    if params.size_tier not in SIZE_TIERS and params.size_tier != "mixed":
        allowed = sorted(SIZE_TIERS) + ["mixed"]
        raise ValueError(
            f"size_tier must be one of {allowed}; got {params.size_tier!r}"
        )
    if not 0.0 <= float(params.style_coherence) <= 1.0:
        raise ValueError(
            f"style_coherence must be in [0.0, 1.0]; got {params.style_coherence!r}"
        )
    if not 0.0 <= float(params.cockpit_coherence) <= 1.0:
        raise ValueError(
            f"cockpit_coherence must be in [0.0, 1.0]; got {params.cockpit_coherence!r}"
        )
    if params.weapon_count_per_ship < 0:
        raise ValueError(
            f"weapon_count_per_ship must be >= 0; got {params.weapon_count_per_ship!r}"
        )
    if not isinstance(params.palette, str) or not params.palette:
        raise ValueError("palette must be a non-empty string")


# ---------------------------------------------------------------------------
# Tier helpers
# ---------------------------------------------------------------------------


def _pick_tier(rng: random.Random, size_tier: str) -> str:
    """Return the concrete tier name for one ship."""
    if size_tier != "mixed":
        return size_tier
    # Escort-heavy distribution — small/mid dominate, capitals are rare.
    # Weights are fixed so "mixed" is deterministic under the supplied seed.
    weights = (0.40, 0.35, 0.20, 0.05)  # small, mid, large, capital
    tiers = ("small", "mid", "large", "capital")
    return rng.choices(tiers, weights=weights, k=1)[0]


def _dims_for_tier(rng: random.Random, tier: str) -> tuple[int, int, int]:
    """Return jittered (W, H, L) dims centred on ``SIZE_TIERS[tier]``."""
    cw, ch, cl = SIZE_TIERS[tier]
    jw, jh, jl = _TIER_TOLERANCE[tier]
    w = cw + rng.randint(-jw, jw)
    h = ch + rng.randint(-jh, jh)
    length = cl + rng.randint(-jl, jl)
    # Clamp to ShapeParams minimums so downstream generate() never rejects.
    w = max(4, w)
    h = max(4, h)
    length = max(8, length)
    return (w, h, length)


def dims_in_tier(dims: tuple[int, int, int], tier: str) -> bool:
    """Public helper: does ``dims`` fall inside tier ``tier``'s window?

    Exposed so tests (and callers) can assert tier bounds without having to
    duplicate the tolerance table.
    """
    if tier not in SIZE_TIERS:
        raise ValueError(f"unknown tier: {tier!r}")
    cw, ch, cl = SIZE_TIERS[tier]
    jw, jh, jl = _TIER_TOLERANCE[tier]
    w, h, length = dims
    return (
        cw - jw <= w <= cw + jw
        and ch - jh <= h <= ch + jh
        and cl - jl <= length <= cl + jl
    )


# ---------------------------------------------------------------------------
# Style selection
# ---------------------------------------------------------------------------


def _base_styles(
    rng: random.Random,
) -> tuple[HullStyle, EngineStyle]:
    """Pick the fleet's base hull + engine archetype."""
    hull = rng.choice(_HULL_STYLES)
    engine = rng.choice(_ENGINE_STYLES)
    return hull, engine


def _per_ship_styles(
    rng: random.Random,
    coherence: float,
    base_hull: HullStyle,
    base_engine: EngineStyle,
) -> tuple[HullStyle, EngineStyle]:
    """Return (hull, engine) for one ship, honouring ``coherence``.

    With probability ``coherence`` each dial stays on the base value; with
    probability ``1 - coherence`` it resamples uniformly from the enum.
    Each dial is rolled independently — at 0.5 coherence roughly half the
    fleet will have matched hulls *and* matched engines.
    """
    if rng.random() < coherence:
        hull = base_hull
    else:
        hull = rng.choice(_HULL_STYLES)
    if rng.random() < coherence:
        engine = base_engine
    else:
        engine = rng.choice(_ENGINE_STYLES)
    return hull, engine


def _wing_for_ship(rng: random.Random) -> WingStyle:
    return rng.choice(_WING_STYLES)


def _per_ship_cockpit(
    rng: random.Random,
    coherence: float,
    base_cockpit: CockpitStyle,
) -> CockpitStyle:
    """Return a cockpit style for one ship, honouring ``coherence``.

    Mirrors :func:`_per_ship_styles`: with probability ``coherence`` the
    ship sticks to ``base_cockpit``, otherwise it resamples uniformly
    from the full :class:`CockpitStyle` enum. Consumes exactly one
    random draw when sticking to the base and two when deviating.
    """
    if rng.random() < coherence:
        return base_cockpit
    return rng.choice(_COCKPIT_STYLES)


def _greeble_for_ship(rng: random.Random) -> float:
    """Per-ship greeble density in [0.0, 0.25]."""
    # Round to 3 decimals so dataclass equality/hashing is stable across
    # float representations and so test fixtures read cleanly.
    return round(rng.uniform(0.0, 0.25), 3)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_fleet(params: FleetParams) -> list[GeneratedShip]:
    """Plan a fleet of ``params.count`` ships.

    Returns an empty list when ``params.count == 0``. Otherwise returns
    exactly ``params.count`` :class:`GeneratedShip` records. Each record
    carries the per-ship seed and params needed to feed
    :func:`spaceship_generator.generator.generate`.
    """
    _validate(params)
    if params.count == 0:
        return []

    rng = random.Random(params.seed)
    base_hull, base_engine = _base_styles(rng)
    coherence = float(params.style_coherence)
    cockpit_coherence = float(params.cockpit_coherence)
    weapons_enabled = params.weapon_count_per_ship > 0
    # Only touch the RNG for cockpit selection when weapons are enabled.
    # Keeping the default (weapons off) path RNG-identical preserves
    # byte-for-byte determinism against every pre-existing fleet.
    base_cockpit: CockpitStyle | None = (
        rng.choice(_COCKPIT_STYLES) if weapons_enabled else None
    )

    ships: list[GeneratedShip] = []
    for _i in range(params.count):
        # Per-ship seed is deterministic and decoupled from the style RNG
        # stream so mixing the same fleet in a different order still produces
        # recognisably similar ships for the same index.
        ship_seed = rng.randrange(0, 2**31 - 1)

        tier = _pick_tier(rng, params.size_tier)
        dims = _dims_for_tier(rng, tier)
        hull, engine = _per_ship_styles(rng, coherence, base_hull, base_engine)
        wing = _wing_for_ship(rng)
        greeble = _greeble_for_ship(rng)
        if weapons_enabled:
            assert base_cockpit is not None  # for type-checkers
            cockpit: CockpitStyle | None = _per_ship_cockpit(
                rng, cockpit_coherence, base_cockpit
            )
        else:
            cockpit = None

        ships.append(
            GeneratedShip(
                seed=ship_seed,
                dims=dims,
                hull_style=hull,
                engine_style=engine,
                wing_style=wing,
                greeble_density=greeble,
                palette=params.palette,
                cockpit_style=cockpit,
                weapon_count=params.weapon_count_per_ship,
            )
        )
    return ships
