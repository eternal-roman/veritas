"""JIT Disposable Packet (JDP) Protocol

A self-describing, ephemeral transmission package for agent-to-agent value exchange.

Design goals (from requirements):
- Single package carries all structured dependencies (wallet, network, payment requirements,
  capability description, evidence hooks)
- Chainable across packets
- Fully distributable value with zero prior setup by sender or receiver
- Salted agent ID is the only persistent identifier
- Everything else is Just-In-Time, transmitted with the message, disposable after use
- Each new transaction brings the components needed to complete, then is disposed

This is a prototype of the envelope format and encoder/decoder.
"""

from __future__ import annotations
import hashlib
import json
import secrets
import time
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def salted_agent_id(base: str = "agent", salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(8)
    raw = f"{base}:{salt}:{int(time.time())}"
    return "sid:" + hashlib.sha256(raw.encode()).hexdigest()[:24]

@dataclass
class JITPacket:
    """One disposable, self-contained transmission unit."""
    # The only persistent-style identifier
    agent_id: str

    # JIT components (new every transmission)
    packet_id: str
    created_at: str
    expires_at: Optional[str] = None

    # Wallet / payment (ephemeral for this exchange)
    pay_to: Optional[str] = None
    network: str = "eip155:8453"
    price: str = "$0.25"
    facilitator: Optional[str] = None
    asset: Optional[str] = None

    # Capability / application structure
    capability: str = "research"
    endpoint_hint: Optional[str] = None
    schema_hint: Optional[Dict[str, Any]] = None

    # Value / content payload (or reference)
    payload: Optional[Dict[str, Any]] = None
    evidence_hashes: List[str] = field(default_factory=list)

    # Chainability
    prev_packet_id: Optional[str] = None
    chain_root: Optional[str] = None

    # Disposable flag
    disposable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def encode(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def decode(cls, raw: str) -> "JITPacket":
        data = json.loads(raw)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def content_hash(self) -> str:
        return "sha256:" + hashlib.sha256(self.encode().encode()).hexdigest()

def create_packet(
    agent_base: str = "veritas",
    pay_to: Optional[str] = None,
    network: str = "eip155:8453",
    price: str = "$0.25",
    facilitator: Optional[str] = None,
    capability: str = "research",
    payload: Optional[Dict[str, Any]] = None,
    prev_packet_id: Optional[str] = None,
    ttl_seconds: int = 300,
) -> JITPacket:
    """Create a fresh, disposable JIT packet."""
    agent_id = salted_agent_id(agent_base)
    packet_id = "pkt:" + secrets.token_hex(12)
    now = time.time()
    expires = datetime.fromtimestamp(now + ttl_seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    return JITPacket(
        agent_id=agent_id,
        packet_id=packet_id,
        created_at=_now(),
        expires_at=expires,
        pay_to=pay_to,
        network=network,
        price=price,
        facilitator=facilitator,
        capability=capability,
        payload=payload or {},
        prev_packet_id=prev_packet_id,
        chain_root=prev_packet_id,  # simple chaining; can be Merkle later
        disposable=True,
    )

def chain_packet(prev: JITPacket, **kwargs) -> JITPacket:
    """Create a new packet that chains from a previous one."""
    return create_packet(
        prev_packet_id=prev.packet_id,
        pay_to=kwargs.get("pay_to", prev.pay_to),
        network=kwargs.get("network", prev.network),
        price=kwargs.get("price", prev.price),
        facilitator=kwargs.get("facilitator", prev.facilitator),
        capability=kwargs.get("capability", prev.capability),
        payload=kwargs.get("payload"),
    )

if __name__ == "__main__":
    p1 = create_packet(pay_to="0xSeller", payload={"query": "What is x402?"})
    print("Packet 1 ID:", p1.packet_id)
    print("Agent ID:", p1.agent_id)
    print("Hash:", p1.content_hash())
    p2 = chain_packet(p1, payload={"result": "..."})
    print("Chained packet prev:", p2.prev_packet_id)
