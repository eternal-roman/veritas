"""Veritas Research - High-assurance evidenced research for agents."""

__version__ = "0.6.0"

from .bayesian import BayesianBelief, update_belief
from .custody import CustodyEvent, CustodyLedger, CustodyStore, verify_chain_records
from .hashing import compute_content_hash, normalize_content, verify_content_hash
from .pipeline import run_research
from .retrieval import RetrievalError, RetrievalResult, StaticCorpusRetriever, default_retriever
from .schema import Claim, Evidence, Status, VeritasResponse, validate_response

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
