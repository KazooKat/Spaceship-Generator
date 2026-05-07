"""Convert a ``palettes/*.yaml`` file to a JSON document for tooling.

Complements :mod:`scripts.palette_lint` (per-file validation),
:mod:`scripts.palette_stats` (cross-corpus stats),
:mod:`scripts.palette_diff` (role-by-role diff), and
:mod:`scripts.palette_merge` (palette merging) by emitting the
existing palette dict as a JSON document — useful for downstream
tooling (web UIs, CI checks, language-server plugins) that prefers
JSON over YAML.

The JSON output preserves the schema key order produced by the YAML
loader (``name`` -> ``description`` -> ``blocks`` -> ``preview_colors``)
so the document round-trips semantically: ``json.loads`` of the
emitted document yields the same dict ``yaml.safe_load`` would have
returned for the original YAML.

Without ``--out`` the JSON document is written to stdout and the
banner goes to stderr (so stdout stays a clean JSON stream pipe-able
into ``jq`` / ``python -m json.tool``). With ``--out PATH`` the JSON
is written to that file and progress / banner go to stderr.

Exit codes:
    0  - palette loaded cleanly and the JSON document was emitted
         successfully.
    1  - input palette failed to load (with a diagnostic on stderr).

Usage:
    .venv/Scripts/python scripts/palette_to_json.py \\
        palettes/desert_oasis.yaml
    .venv/Scripts/python scripts/palette_to_json.py \\
        palettes/desert_oasis.yaml --out desert_oasis.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Reuse the YAML loader semantics from ``palette_merge`` / ``palette_diff``
# rather than rolling a parallel reader so any future schema fix to the
# loader is automatically picked up here.
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SRC = REPO_ROOT / "src"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import yaml  # noqa: E402


def _load_palette(path: Path) -> dict:
    """Load a palette YAML, raising ``ValueError`` with a human diagnostic.

    Mirrors the strict variant of the loader used in ``palette_merge``:
    any read / parse / shape failure raises ``ValueError`` so the caller
    can translate the message into an exit-1 stderr line. We want a hard
    failure here — the conversion tool must not silently emit a
    half-formed JSON document if the YAML is broken.
    """
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot read/parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"top-level YAML must be a mapping in {path}")
    return data


def _dump_json(palette: dict) -> str:
    """Serialize the palette dict to a JSON string.

    ``sort_keys=False`` preserves the schema order produced by the YAML
    loader (``name`` -> ``description`` -> ``blocks`` ->
    ``preview_colors`` with REQUIRED_ROLES first inside each mapping)
    so the output mirrors the shape of hand-authored palettes and the
    document round-trips semantically through ``json.loads``.
    """
    return json.dumps(palette, indent=2, sort_keys=False)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Convert a palettes/*.yaml file to a JSON document for "
            "downstream tooling consumption."
        )
    )
    p.add_argument("palette", help="path to palette YAML")
    p.add_argument(
        "--out",
        default=None,
        help=(
            "Optional output path for the JSON document. Without --out, "
            "the JSON is written to stdout (banner to stderr)."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    path = Path(args.palette)

    try:
        palette = _load_palette(path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    json_text = _dump_json(palette)

    name = path.stem
    banner = f"palette_to_json.py — {name}"

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_text, encoding="utf-8")
        print(banner, file=sys.stderr)
        print(f"wrote {out_path}", file=sys.stderr)
    else:
        # Banner goes to stderr in stdout mode so the stdout stream
        # stays a clean JSON document an operator can pipe straight
        # into ``jq`` / ``python -m json.tool``.
        print(banner, file=sys.stderr)
        sys.stdout.write(json_text)
        # Trailing newline so terminal users don't see a smushed prompt
        # but pipe consumers (json.loads) stay happy either way.
        if not json_text.endswith("\n"):
            sys.stdout.write("\n")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
