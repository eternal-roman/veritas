"""Bootstrap plane agents: visas + VAAT stipends.

Run: ``python -m veritas.plane_bootstrap``

Does **not** touch x402 or product settlement.
"""

from __future__ import annotations

import json
from pathlib import Path

from veritas.agent_identity import bootstrap_plane_roster
from veritas.agent_money import AgentMoneyLedger

# Default roster: 7 watchers + tracks. Prefer ``python -m veritas.agent_economy``.
DEFAULT_ROSTER: dict[str, str] = {
    "overseer": "overseer",
    "conductor": "conductor",
    "steward": "steward",
    "scout": "scout",
    "pruner": "pruner",
    "flywheel": "flywheel",
    "researcher": "researcher",
    "architect": "architect",
    "git_agent": "git_agent",
    "optimizer": "optimizer",
    "mesh_runner": "mesh_runner",
    "unblock": "unblock",
    "money_loop": "money_loop",
    "multiparty_trust": "multiparty_trust",
    "product_worth": "product_worth",
    "discovery_density": "discovery_density",
    "multi_tenant": "multi_tenant",
    "legal_identity": "legal_identity",
    "network_effects": "network_effects",
}

STIPEND_VAAT = 1000


def bootstrap(
    base_dir: Path | str | None = None,
    *,
    stipend: int = STIPEND_VAAT,
) -> dict:
    import hashlib
    import os

    base = Path(base_dir) if base_dir else Path.cwd() / ".veritas"
    base.mkdir(parents=True, exist_ok=True)
    money_path = base / "agent_money.sqlite3"
    secret_path = base / "plane_identity.secret"
    visa_path = base / "plane_visas.json"

    led = AgentMoneyLedger(money_path)
    for agent_id, role in DEFAULT_ROSTER.items():
        led.register(agent_id, meta={"role": role})
        if led.balance(agent_id) == 0:
            led.mint(agent_id, stipend, memo=f"stipend:{role}")
    led.verify_chain()
    snap = led.snapshot()
    led.close()

    from veritas.agent_identity import _read_secret_file, _write_secret_file

    if secret_path.is_file():
        raw = _read_secret_file(secret_path)
    else:
        raw = hashlib.sha256(os.urandom(32)).digest()
        _write_secret_file(secret_path, raw)
    visas = bootstrap_plane_roster(DEFAULT_ROSTER, secret=raw)
    visa_path.write_text(
        json.dumps(visas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return {
        "money": snap,
        "visa_count": len(visas),
        "paths": {
            "money": str(money_path),
            "visas": str(visa_path),
            "secret": str(secret_path),
        },
        "not_x402_settlement": True,
    }


def main() -> None:
    out = bootstrap()
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
