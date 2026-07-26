"""Veritas Research - High-assurance evidenced research for agents."""

__version__ = "0.1.0"

from .hashing import compute_content_hash, verify_content_hash, normalize_content
from .custody import CustodyLedger, CustodyEvent
from .bayesian import BayesianBelief, update_belief
from .schema import Evidence, Claim, VeritasResponse

__all__ = [
    "compute_content_hash",
    "verify_content_hash",
    "normalize_content",
    "CustodyLedger",
    "CustodyEvent",
    "BayesianBelief",
    "update_belief",
    "Evidence",
    "Claim",
    "VeritasResponse",
]
