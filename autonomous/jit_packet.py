"""JIT Disposable Packet (JDP) Protocol.

A self-describing, ephemeral transmission package for agent-to-agent value
exchange: one packet carries the wallet commitment, network, payment
requirements and capability description needed to complete an exchange with no
prior setup between the parties.

Three defects in the prototype are fixed here, because each one broke a stated
design goal:

1. **The persistent identifier was not persistent.** `create_packet` minted a
   fresh salted agent id per packet — including inside `chain_packet` — so the
   "only persistent identifier" changed every message and a chain could not be
   attributed to one agent. Identity is now supplied by the caller and stable
   across a chain.

2. **Packets were unsigned.** `prev_packet_id` was an unauthenticated string,
   so anyone could forge a packet claiming to continue someone's chain. Packets
   are now MAC-signed over their canonical encoding, and chain links are
   verified against the parent's content hash.

3. **`expires_at` was decorative.** It was written and never read. Expiry is
   now enforced by `is_expired()` and rejected in `verify_packet`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


@dataclass
class AgentIdentity:
    """A stable, salted agent identifier plus the key used to sign its packets.

    The salt hides any real-world identifier behind a hash while remaining
    stable, which is what makes chains attributable.
    """
    agent_id: str
    signing_key: bytes

    @classmethod
    def create(cls, base: str = "veritas", salt: Optional[str] = None) -> "AgentIdentity":
        salt = salt or secrets.token_hex(16)
        digest = hashlib.sha256(f"{base}:{salt}".encode()).hexdigest()[:24]
        return cls(agent_id=f"sid:{digest}", signing_key=secrets.token_bytes(32))


@dataclass
class JITPacket:
    """One disposable, self-contained transmission unit."""
    agent_id: str
    packet_id: str
    created_at: str
    expires_at: Optional[str] = None

    # Payment. `pay_to_commitment` carries a hiding commitment instead of a
    # cleartext address so a broadcast offer does not leak the payout wallet.
    pay_to_commitment: Optional[str] = None
    pay_to: Optional[str] = None
    network: str = "eip155:8453"
    price: str = "$0.25"
    facilitator: Optional[str] = None
    asset: Optional[str] = None

    capability: str = "research"
    endpoint_hint: Optional[str] = None
    schema_hint: Optional[Dict[str, Any]] = None

    payload: Optional[Dict[str, Any]] = None
    evidence_hashes: List[str] = field(default_factory=list)

    prev_packet_id: Optional[str] = None
    prev_packet_hash: Optional[str] = None
    chain_root: Optional[str] = None

    disposable: bool = True
    signature: Optional[str] = None

    def _signable(self) -> str:
        """Canonical encoding excluding the signature itself."""
        data = {k: v for k, v in asdict(self).items() if k != "signature"}
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def encode(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def decode(cls, raw: str) -> "JITPacket":
        data = json.loads(raw)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def content_hash(self) -> str:
        return "sha256:" + hashlib.sha256(self._signable().encode()).hexdigest()

    def sign(self, signing_key: bytes) -> "JITPacket":
        self.signature = hmac.new(signing_key, self._signable().encode(), hashlib.sha256).hexdigest()
        return self

    def verify_signature(self, signing_key: bytes) -> bool:
        if not self.signature:
            return False
        expected = hmac.new(signing_key, self._signable().encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.signature)

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        if not self.expires_at:
            return False
        expiry = _parse_iso(self.expires_at)
        if expiry is None:
            return True  # unparseable expiry is treated as expired, not ignored
        return (now or _now_dt()) > expiry


def create_packet(
    identity: AgentIdentity,
    pay_to_commitment: Optional[str] = None,
    pay_to: Optional[str] = None,
    network: str = "eip155:8453",
    price: str = "$0.25",
    facilitator: Optional[str] = None,
    capability: str = "research",
    payload: Optional[Dict[str, Any]] = None,
    prev: Optional[JITPacket] = None,
    ttl_seconds: int = 300,
) -> JITPacket:
    """Create a fresh, disposable, signed JIT packet under a stable identity."""
    now = _now_dt()
    packet = JITPacket(
        agent_id=identity.agent_id,
        packet_id="pkt:" + secrets.token_hex(12),
        created_at=_iso(now),
        expires_at=_iso(now + timedelta(seconds=ttl_seconds)),
        pay_to_commitment=pay_to_commitment,
        pay_to=pay_to,
        network=network,
        price=price,
        facilitator=facilitator,
        capability=capability,
        payload=payload or {},
        prev_packet_id=prev.packet_id if prev else None,
        prev_packet_hash=prev.content_hash() if prev else None,
        chain_root=(prev.chain_root or prev.packet_id) if prev else None,
        disposable=True,
    )
    if packet.chain_root is None:
        packet.chain_root = packet.packet_id
    return packet.sign(identity.signing_key)


def chain_packet(prev: JITPacket, identity: AgentIdentity, **kwargs) -> JITPacket:
    """Create a packet continuing an existing chain, inheriting payment context."""
    return create_packet(
        identity=identity,
        prev=prev,
        pay_to_commitment=kwargs.get("pay_to_commitment", prev.pay_to_commitment),
        pay_to=kwargs.get("pay_to", prev.pay_to),
        network=kwargs.get("network", prev.network),
        price=kwargs.get("price", prev.price),
        facilitator=kwargs.get("facilitator", prev.facilitator),
        capability=kwargs.get("capability", prev.capability),
        payload=kwargs.get("payload"),
        ttl_seconds=kwargs.get("ttl_seconds", 300),
    )


def verify_packet(
    packet: JITPacket,
    signing_key: bytes,
    prev: Optional[JITPacket] = None,
    now: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """Validate signature, expiry and chain linkage. Returns (ok, reason)."""
    if not packet.verify_signature(signing_key):
        return False, "invalid_signature"
    if packet.is_expired(now):
        return False, "expired"
    if prev is not None:
        if packet.prev_packet_id != prev.packet_id:
            return False, "chain_id_mismatch"
        if packet.prev_packet_hash != prev.content_hash():
            return False, "chain_hash_mismatch"
        if packet.agent_id != prev.agent_id:
            return False, "agent_identity_changed"
    return True, "ok"


if __name__ == "__main__":
    identity = AgentIdentity.create("veritas")
    p1 = create_packet(identity, pay_to="0xSeller", payload={"query": "What is x402?"})
    p2 = chain_packet(p1, identity, payload={"result": "..."})
    print("Stable agent id across chain:", p1.agent_id == p2.agent_id)
    print("p2 verifies:", verify_packet(p2, identity.signing_key, prev=p1))
    forged = JITPacket.decode(p2.encode())
    forged.payload = {"result": "tampered"}
    print("Tampered packet rejected:", verify_packet(forged, identity.signing_key, prev=p1))
    expired = create_packet(identity, ttl_seconds=-1)
    print("Expired packet rejected:", verify_packet(expired, identity.signing_key))
