"""Core data models for Veritas responses."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum


class Status(str, Enum):
    COMPLETED = "completed"
    REFUSED = "refused"
    PARTIAL = "partial"


@dataclass
class Evidence:
    evidence_id: str
    source_url: str
    excerpt: str
    content_hash: str
    retrieved_at: str
    custody_root: Optional[str] = None


@dataclass
class Claim:
    claim_id: str
    statement: str
    posterior: float
    evidence: List[Evidence]
    status: str = "supported"


@dataclass
class VeritasResponse:
    request_id: str
    status: Status
    query: str
    claims: List[Claim]
    refusal_reason: Optional[str] = None
    overall_posterior: float = 0.0
    custody_root: Optional[str] = None
    trust_score: Optional[float] = None
    latency_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        def convert(obj):
            if hasattr(obj, "__dataclass_fields__"):
                return {k: convert(v) for k, v in asdict(obj).items()}
            if isinstance(obj, list):
                return [convert(i) for i in obj]
            if isinstance(obj, Enum):
                return obj.value
            return obj
        return convert(self)
