"""Bootstrap plane agents: visas + VAAT stipends.

Run: ``python -m veritas.plane_bootstrap``

Thin wrapper around ``bootstrap_economy`` with the plane stipend (1000).
Does **not** touch x402 or product settlement.
"""

from __future__ import annotations

import json
from pathlib import Path

from veritas.agent_economy import FULL_ROSTER, bootstrap_economy

# Single roster: the plane economy is the source of truth.
DEFAULT_ROSTER: dict[str, str] = FULL_ROSTER

STIPEND_VAAT = 1000


def bootstrap(
    base_dir: Path | str | None = None,
    *,
    stipend: int = STIPEND_VAAT,
) -> dict:
    out = bootstrap_economy(base_dir, stipend=stipend, roster=DEFAULT_ROSTER)
    paths = out["paths"]
    return {
        "money": out["money"],
        "visa_count": len(out["accounts"]),
        "paths": {
            "money": paths["money"],
            "visas": paths["visas"],
            "secret": paths["secret"],
        },
        "not_x402_settlement": True,
    }


def main() -> None:
    out = bootstrap()
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
