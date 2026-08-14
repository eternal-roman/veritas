"""Personal agent account: identity + wallets + interest-bound skills.

One local record an arriving agent creates with ``veritas-agent enroll``
(or ``init`` / ``up``, which enroll automatically):

1. **Identity** — plane DID + HMAC visa (local coordination, not ERC-8004 / SPIFFE).
2. **Wallets** — commerce address (x402 ``pay_to``, funding external) and
   plane VAAT (not on-chain settlement).
3. **Skills** — catalog entries derived from declared interests, hashed to
   the identity and commerce wallet so the binding is checkable.

Honesty bound: this is a local agent home, not an account server, not KYC,
and not on-chain identity. Unknown interests are recorded unmapped rather
than invented into capabilities.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from veritas.agent_economy import AgentEconomy
from veritas.hashing import compute_content_hash

ACCOUNT_SCHEMA = "veritas.agent.account.v1"
ACCOUNT_NAME = "account.json"
DEFAULT_HOME = ".veritas_agent"
DEFAULT_AGENT_ID = "self"
DEFAULT_ROLE = "agent"
DEFAULT_INTERESTS: tuple[str, ...] = ("research", "verify")
DEFAULT_STIPEND = 100

# Interest keyword → catalog skill id.
INTEREST_ALIASES: dict[str, str] = {
    "search": "research",
    "lookup": "research",
    "check": "verify",
    "vet": "diligence",
    "purchase": "buy",
    "pay": "buy",
    "serve": "sell",
    "host": "sell",
    "notary": "notarize",
    "operate": "ops",
    "operator": "ops",
}

# Capabilities that already exist in this package. Interests map here or stay unmapped.
SKILL_CATALOG: dict[str, dict[str, str]] = {
    "research": {
        "title": "Evidence-grounded research",
        "command": "veritas-mcp",
        "http": "POST /v1/research",
        "note": "Paid on HTTP; MCP is the local free-mode engine",
    },
    "verify": {
        "title": "Independent receipt / origin verification",
        "command": "veritas-verify",
        "http": "POST /v1/verify",
        "note": "Vendor veritas/verifier.py to audit without installing the server",
    },
    "diligence": {
        "title": "Vet a seller from published documents",
        "command": "veritas-diligence",
        "http": "",
        "note": "Exit 0 pass / 1 fail / 2 unverifiable / 3 bad input",
    },
    "audit": {
        "title": "Audit an attested pack against its origin",
        "command": "veritas-audit",
        "http": "",
        "note": "Exit 0 confirmed / 1 diverged / 2 unobserved / 3 bad input",
    },
    "buy": {
        "title": "Buyer journey: discover, diligence, unpaid probe",
        "command": "veritas-buy",
        "http": "",
        "note": "Never settles payment",
    },
    "sell": {
        "title": "Serve research paid to this agent's commerce wallet",
        "command": "veritas-agent up --paid",
        "http": "POST /v1/research",
        "note": "Requires a funded wallet and a reachable facilitator",
    },
    "notarize": {
        "title": "Observe-once evidence notary",
        "command": "",
        "http": "POST /v1/notarize",
        "note": "Same payment gates as research; unavailable is not billable",
    },
    "ops": {
        "title": "Operator ledger reports",
        "command": "veritas-ops",
        "http": "",
        "note": "JSON from this instance's ledger; reconcile-chain is report-only",
    },
    "warranty": {
        "title": "Falsifiable warranties (W0)",
        "command": "",
        "http": "",
        "note": "veritas.warranty — bonds are signed commitments, not escrow (G12)",
    },
    "standing": {
        "title": "Composed standing from records you hold",
        "command": "",
        "http": "",
        "note": "veritas.standing — curated sets remain possible (G11)",
    },
}


class AgentAccountError(Exception):
    """Account enroll / load failure."""


def resolve_home(base_dir: str | Path | None = None) -> Path:
    if base_dir is not None:
        return Path(base_dir)
    env = os.environ.get("VERITAS_AGENT_HOME")
    if env:
        return Path(env)
    return Path(DEFAULT_HOME)


def account_path(base_dir: str | Path | None = None) -> Path:
    return resolve_home(base_dir) / ACCOUNT_NAME


def normalize_interest(raw: str) -> tuple[str, bool]:
    """Return (skill_id_or_raw, mapped)."""
    key = raw.strip().lower().replace(" ", "_").replace("-", "_")
    if not key:
        raise AgentAccountError("empty interest")
    if key in SKILL_CATALOG:
        return key, True
    alias = INTEREST_ALIASES.get(key)
    if alias:
        return alias, True
    return key, False


def bind_skills(
    interests: list[str],
    *,
    agent_id: str,
    did: str,
    commerce_address: str | None,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    bound: list[dict[str, Any]] = []
    for raw in interests:
        skill_id, mapped = normalize_interest(raw)
        if skill_id in seen:
            continue
        seen.add(skill_id)
        payload: dict[str, Any] = {
            "id": skill_id,
            "mapped": mapped,
            "declared_as": raw.strip(),
        }
        if mapped:
            payload.update(SKILL_CATALOG[skill_id])
        else:
            payload["note"] = "no catalog skill; recorded as interest only"
        binding = {
            "agent_id": agent_id,
            "did": did,
            "commerce_address": commerce_address,
            "skill_id": skill_id,
        }
        payload["binding_hash"] = compute_content_hash(
            json.dumps(binding, sort_keys=True)
        )
        bound.append(payload)
    return bound


def load_account(base_dir: str | Path | None = None) -> dict[str, Any] | None:
    path = account_path(base_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise AgentAccountError(f"unreadable account at {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != ACCOUNT_SCHEMA:
        raise AgentAccountError(f"unrecognized account schema at {path}")
    return data


def _parse_interests(raw: list[str] | str | None) -> list[str]:
    if raw is None:
        return list(DEFAULT_INTERESTS)
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(",")]
        return [p for p in parts if p] or list(DEFAULT_INTERESTS)
    cleaned = [str(p).strip() for p in raw if str(p).strip()]
    return cleaned or list(DEFAULT_INTERESTS)


def enroll_account(
    base_dir: str | Path | None = None,
    *,
    agent_id: str | None = None,
    role: str | None = None,
    interests: list[str] | str | None = None,
    commerce_address: str | None = None,
    stipend: int = DEFAULT_STIPEND,
) -> dict[str, Any]:
    """Create or refresh the local account. Idempotent on the same agent_id."""
    home = resolve_home(base_dir)
    home.mkdir(parents=True, exist_ok=True)

    existing = None
    try:
        existing = load_account(home)
    except AgentAccountError:
        existing = None

    aid = (agent_id or (existing or {}).get("agent_id") or DEFAULT_AGENT_ID).strip()
    if not aid:
        raise AgentAccountError("agent_id required")
    arole = (role or (existing or {}).get("role") or DEFAULT_ROLE).strip() or DEFAULT_ROLE

    declared = _parse_interests(interests)
    if existing and interests is None:
        prior = existing.get("interests") or []
        if isinstance(prior, list) and prior:
            declared = [str(x) for x in prior]

    if commerce_address is None:
        commerce_address = (existing or {}).get("wallets", {}).get("commerce", {}).get(
            "address"
        )
    if commerce_address is None:
        try:
            from veritas.autonomous.wallet import ensure_wallet

            commerce_address = ensure_wallet(base_dir=str(home)).address
        except ValueError:
            commerce_address = None

    eco = AgentEconomy(home)
    try:
        acc = eco.ensure_agent(aid, arole, stipend=stipend)
        plane_balance = acc.balance_vaat
        did = acc.did
        plane_id = acc.plane_id
        visa = acc.visa
    finally:
        eco.close()

    skills = bind_skills(
        declared, agent_id=aid, did=did, commerce_address=commerce_address
    )
    body = {
        "schema": ACCOUNT_SCHEMA,
        "agent_id": aid,
        "role": arole,
        "did": did,
        "plane_id": plane_id,
        "interests": declared,
        "skills": skills,
        "wallets": {
            "commerce": {
                "address": commerce_address,
                "note": (
                    "x402 pay_to; funding the wallet and public TLS remain external"
                    if commerce_address
                    else "not provisioned (install the 'signing' extra)"
                ),
            },
            "plane": {
                "currency": "VAAT",
                "balance": plane_balance,
                "not_x402_settlement": True,
            },
        },
        "visa": visa,
        "not_x402_settlement": True,
        "next": {
            "whoami": "veritas-agent whoami",
            "sell": "veritas-agent up",
            "buy": "veritas-buy <seller-url>",
            "local_tools": "veritas-mcp",
        },
    }
    body["binding_hash"] = compute_content_hash(
        json.dumps(
            {
                "agent_id": aid,
                "did": did,
                "commerce_address": commerce_address,
                "skill_ids": [s["id"] for s in skills],
            },
            sort_keys=True,
        )
    )
    body["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if existing and existing.get("created_at"):
        body["created_at"] = existing["created_at"]
    else:
        body["created_at"] = body["updated_at"]

    path = home / ACCOUNT_NAME
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return body


def whoami_document(base_dir: str | Path | None = None) -> dict[str, Any]:
    acc = load_account(base_dir)
    if acc is None:
        return {
            "enrolled": False,
            "schema": ACCOUNT_SCHEMA,
            "next": "veritas-agent enroll --id <name> --interests research,buy,verify",
            "catalog": sorted(SKILL_CATALOG),
        }
    return {"enrolled": True, **acc}


def catalog_document() -> dict[str, Any]:
    return {
        "schema": ACCOUNT_SCHEMA,
        "skills": SKILL_CATALOG,
        "aliases": INTEREST_ALIASES,
        "defaults": list(DEFAULT_INTERESTS),
    }
