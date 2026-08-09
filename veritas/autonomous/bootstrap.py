"""Agent self-provisioning bootstrap.

Allows an agent to start Veritas in fully free / zero-human-config mode.
Generates a local deterministic seed for testing and configures free retrieval.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from veritas.payment_config import DEFAULT_FACILITATOR


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
        "retrieval": "zero_key",          # uses veritas/autonomous/zero_key_retrieval.py
        "require_payment": False,        # can be flipped later by the agent
        "pay_to": None,                  # agent can later set its own address
        "facilitator": DEFAULT_FACILITATOR,  # single-sourced with the money path
        "seed_hint": generate_local_seed(agent_id)[:16] + "...",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "notes": "Free mode uses only zero-key sources. Upgrade by setting paid keys or a real receiving wallet."
    }

    config_path = path / "config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config

def apply_to_env(config: dict) -> None:
    """Apply an agent config to the environment the HTTP server reads.

    `bootstrap_free_mode` writes a config file that only the in-process
    control plane consumed; `PaymentConfig.from_env` never saw it, so an
    agent that "provisioned" itself had configured nothing the served
    surface uses. This is the bridge: config keys map onto the VERITAS_*
    variables, and only keys actually present (and non-None) are applied —
    PaymentConfig's own validation still decides free/live/misconfigured.
    """
    os.environ["VERITAS_REQUIRE_PAYMENT"] = (
        "true" if config.get("require_payment") else "false"
    )
    mapping = {
        "pay_to": "VERITAS_PAY_TO",
        "facilitator": "VERITAS_FACILITATOR",
        "network": "VERITAS_NETWORK",
        "price": "VERITAS_PRICE",
    }
    for key, var in mapping.items():
        value = config.get(key)
        if value is not None:
            os.environ[var] = str(value)


def load_config(base_dir: str = ".veritas_agent") -> dict:
    """Return the agent config, bootstrapping free mode if none exists yet."""
    config_path = Path(base_dir) / "config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Corrupt or unreadable config: re-bootstrap rather than crash the
            # agent path. Callers that need to distinguish corruption from a
            # missing file should inspect the path themselves.
            pass
    return bootstrap_free_mode(base_dir=base_dir)

def bootstrap(agent_id: str = "default", base_dir: str = ".veritas_agent") -> dict:
    """Zero-config entry point used by the control plane."""
    return bootstrap_free_mode(agent_id=agent_id, base_dir=base_dir)

def is_free_mode() -> bool:
    return os.getenv("VERITAS_MODE", "free").lower() == "free"

if __name__ == "__main__":
    cfg = bootstrap_free_mode()
    print(json.dumps(cfg, indent=2))
