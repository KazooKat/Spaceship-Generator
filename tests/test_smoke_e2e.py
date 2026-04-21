"""CI wrapper around ``scripts/smoke_e2e.py``.

The full smoke sweep (every palette x every pinned combo) is too slow
to run on every PR — it lives in ``scripts/smoke_e2e.py`` for manual /
nightly use. This test runs a tiny subset (first 2 palettes) so CI still
catches catastrophic breakage on the end-to-end path without ballooning
per-PR wall time.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import smoke_e2e  # noqa: E402


def test_smoke_e2e_subset_passes():
    """Run the smoke script over a 2-palette subset and assert exit 0."""
    exit_code = smoke_e2e.run(sample=2)
    assert exit_code == 0, (
        "smoke_e2e subset returned non-zero; run "
        "`.venv/Scripts/python scripts/smoke_e2e.py --sample 2` locally "
        "to see the failure table."
    )
