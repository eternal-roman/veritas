"""Veritas — prediction-market catalog, x402 settlement, verifiable observe."""

__version__ = "0.13.0"

from .custody import CustodyEvent, CustodyLedger, CustodyStore, verify_chain_records
from .hashing import compute_content_hash, normalize_content, verify_content_hash
from .schema import Status, validate_response

__all__ = [
    "compute_content_hash",
    "verify_content_hash",
    "normalize_content",
    "CustodyLedger",
    "CustodyEvent",
    "CustodyStore",
    "verify_chain_records",
    "Status",
    "validate_response",
]
