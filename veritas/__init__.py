"""Veritas Research - High-assurance evidenced research for agents."""

__version__ = "0.5.0"

from .hashing import compute_content_hash, verify_content_hash, normalize_content
from .custody import CustodyLedger, CustodyEvent, CustodyStore, verify_chain_records
from .bayesian import BayesianBelief, update_belief
from .schema import Evidence, Claim, VeritasResponse, Status, validate_response
from .retrieval import RetrievalResult, RetrievalError, StaticCorpusRetriever, default_retriever
from .pipeline import run_research

__all__ = [
    "compute_content_hash",
    "verify_content_hash",
    "normalize_content",
    "CustodyLedger",
    "CustodyEvent",
    "CustodyStore",
    "verify_chain_records",
    "BayesianBelief",
    "update_belief",
    "Evidence",
    "Claim",
    "VeritasResponse",
    "Status",
    "validate_response",
    "RetrievalResult",
    "RetrievalError",
    "StaticCorpusRetriever",
    "default_retriever",
    "run_research",
]
