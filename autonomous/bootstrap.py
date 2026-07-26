"""Agent self-provisioning bootstrap.

Allows an agent to start Veritas in fully free / zero-human-config mode.
Generates a local deterministic seed for testing and configures free retrieval.
"""

from __future__ import annotations
import os
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

def generate_local_seed(agent_id: str = "default") -> str:
    """Deterministic local seed for development / agent-controlled instances.
    In production an agent should use its own secure key management.
    """
    raw = f"veritas-agent-{agent_id}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    return hashlib.sha256(raw.encode()).hexdigest()

def bootstrap_free_mode(agent_id: str = "default", base_dir: str = ".veritas_agent") -> dict:
    """Create a free-mode configuration that requires no external paid keys."""
    path = Path(base_dir)
    path.mkdir(parents=True, exist_ok=True)

    config = {
        "mode": "free",
        "agent_id": agent_id,
        "retrieval": "zero_key",          # uses autonomous/zero_key_retrieval.py
        "require_payment": False,        # can be flipped later by the agent
        "pay_to": None,                  # agent can later set its own address
        "facilitator": "https://pay.openfacilitator.io",  # public free facilitator option
        "seed_hint": generate_local_seed(agent_id)[:16] + "...",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "notes": "Free mode uses only zero-key sources. Upgrade by setting paid keys or a real receiving wallet."
    }

    config_path = path / "config.json"
    config_path.write_text(json.dumps(config, indent=2))
    return config

def is_free_mode() -> bool:
    return os.getenv("VERITAS_MODE", "free").lower() == "free"

if __name__ == "__main__":
    cfg = bootstrap_free_mode()
    print(json.dumps(cfg, indent=2))
