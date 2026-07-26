"""Append-only hash-chain custody ledger (blockchain-style)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_record(record: dict) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class CustodyEvent:
    event_type: str          # created | transformed | verified | reviewed | updated
    actor: str
    timestamp: str
    prev_hash: Optional[str]
    payload: Dict[str, Any]
    event_hash: str = ""

    def compute_hash(self) -> str:
        data = {
            "event_type": self.event_type,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "payload": self.payload,
        }
        return _hash_record(data)


class CustodyLedger:
    """Append-only ledger. Any mutation of past events breaks the chain."""

    def __init__(self):
        self.events: List[CustodyEvent] = []

    def append(self, event_type: str, actor: str, payload: Dict[str, Any]) -> CustodyEvent:
        prev_hash = self.events[-1].event_hash if self.events else None
        event = CustodyEvent(
            event_type=event_type,
            actor=actor,
            timestamp=_now(),
            prev_hash=prev_hash,
            payload=payload,
        )
        event.event_hash = event.compute_hash()
        self.events.append(event)
        return event

    def verify_chain(self) -> bool:
        if not self.events:
            return True
        for i, event in enumerate(self.events):
            if event.event_hash != event.compute_hash():
                return False
            if i == 0:
                if event.prev_hash is not None:
                    return False
            else:
                if event.prev_hash != self.events[i - 1].event_hash:
                    return False
        return True

    def root_hash(self) -> Optional[str]:
        return self.events[-1].event_hash if self.events else None

    def to_list(self) -> List[Dict[str, Any]]:
        return [asdict(e) for e in self.events]
