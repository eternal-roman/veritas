"""Plane network identity (visa) for control-plane agents.

Issues and verifies **plane visas**: signed identity cards agents hold so
other plane agents can authenticate role + agent_id without a global PKI.

Honesty bound:
- Local/plane only — not a government visa, not Entra, not SPIFFE production.
- Maps *conceptually* to KYA / SIWx / workload identity patterns (GitHub:
  SPIFFE/SPIRE agent identity, Entra agent identity, DID+VC agent wallets).
- Product buyer auth remains SIWx / x402; this is for **plane coordination**.

Visa payload is HMAC-SHA256 over canonical JSON using a plane secret
(``VERITAS_PLANE_IDENTITY_SECRET`` or a path-local secret file for tests).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VISA_KIND = "veritas.plane.visa"
VISA_VERSION = 1


class AgentIdentityError(Exception):
    """Base plane identity error."""


class VisaVerifyError(AgentIdentityError):
    """Visa failed verification."""


def _canonical(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _b64(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(s: str) -> bytes:
    import base64

    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def load_plane_secret(secret: bytes | str | Path | None = None) -> bytes:
    if secret is None:
        env = os.environ.get("VERITAS_PLANE_IDENTITY_SECRET")
        if env:
            return env.encode("utf-8")
        path = Path.cwd() / ".veritas" / "plane_identity.secret"
        if path.is_file():
            return path.read_bytes().strip()
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = hashlib.sha256(os.urandom(32)).digest()
        path.write_bytes(raw)
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return raw
    if isinstance(secret, Path):
        return secret.read_bytes().strip()
    if isinstance(secret, str):
        return secret.encode("utf-8")
    return secret


@dataclass(frozen=True)
class PlaneVisa:
    agent_id: str
    role: str
    issued_at: float
    expires_at: float
    network: str
    claims: dict[str, Any]
    signature: str

    def body_for_sign(self) -> dict[str, Any]:
        return {
            "kind": VISA_KIND,
            "version": VISA_VERSION,
            "agent_id": self.agent_id,
            "role": self.role,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "network": self.network,
            "claims": self.claims,
        }

    def to_dict(self) -> dict[str, Any]:
        d = self.body_for_sign()
        d["signature"] = self.signature
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PlaneVisa:
        return cls(
            agent_id=str(d["agent_id"]),
            role=str(d["role"]),
            issued_at=float(d["issued_at"]),
            expires_at=float(d["expires_at"]),
            network=str(d.get("network", "veritas-plane")),
            claims=dict(d.get("claims") or {}),
            signature=str(d["signature"]),
        )


class PlaneIdentityIssuer:
    """Issue and verify plane visas."""

    def __init__(self, secret: bytes | str | Path | None = None) -> None:
        self._secret = load_plane_secret(secret)

    def issue(
        self,
        agent_id: str,
        role: str,
        *,
        ttl_seconds: int = 86400,
        network: str = "veritas-plane",
        claims: dict[str, Any] | None = None,
        now: float | None = None,
    ) -> PlaneVisa:
        agent_id = agent_id.strip()
        role = role.strip()
        if not agent_id or not role:
            raise AgentIdentityError("agent_id and role required")
        if ttl_seconds <= 0:
            raise AgentIdentityError("ttl must be positive")
        ts = time.time() if now is None else now
        body = {
            "kind": VISA_KIND,
            "version": VISA_VERSION,
            "agent_id": agent_id,
            "role": role,
            "issued_at": ts,
            "expires_at": ts + ttl_seconds,
            "network": network,
            "claims": claims or {},
        }
        sig = _b64(hmac.new(self._secret, _canonical(body), hashlib.sha256).digest())
        return PlaneVisa(
            agent_id=agent_id,
            role=role,
            issued_at=body["issued_at"],
            expires_at=body["expires_at"],
            network=network,
            claims=dict(body["claims"]),
            signature=sig,
        )

    def verify(
        self,
        visa: PlaneVisa | dict[str, Any],
        *,
        now: float | None = None,
        expected_role: str | None = None,
        expected_network: str | None = None,
    ) -> PlaneVisa:
        if isinstance(visa, dict):
            visa = PlaneVisa.from_dict(visa)
        body = visa.body_for_sign()
        expect = _b64(
            hmac.new(self._secret, _canonical(body), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expect, visa.signature):
            raise VisaVerifyError("bad signature")
        ts = time.time() if now is None else now
        if ts > visa.expires_at:
            raise VisaVerifyError("expired")
        if expected_role is not None and visa.role != expected_role:
            raise VisaVerifyError(f"role {visa.role!r} != {expected_role!r}")
        if expected_network is not None and visa.network != expected_network:
            raise VisaVerifyError("wrong network")
        return visa


def bootstrap_plane_roster(
    roles: dict[str, str],
    *,
    secret: bytes | str | Path | None = None,
    ttl_seconds: int = 86400 * 7,
) -> dict[str, dict[str, Any]]:
    """Issue visas for a map of agent_id -> role. Returns visa dicts."""
    issuer = PlaneIdentityIssuer(secret)
    out: dict[str, dict[str, Any]] = {}
    for agent_id, role in roles.items():
        out[agent_id] = issuer.issue(
            agent_id, role, ttl_seconds=ttl_seconds
        ).to_dict()
    return out
