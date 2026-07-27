"""ERC-8004 compatible identity document."""

from datetime import datetime, timezone
import json
from .hashing import compute_content_hash

def build_identity(pay_to: str = "0x0000000000000000000000000000000000000000") -> dict:
    doc = {
        "name": "Veritas Research",
        "description": "High-assurance research with Bayesian Knowledge Ledger, content-hashed evidence, and explicit refusal.",
        "paymentAddress": pay_to,
        "capabilities": ["evidence-grounded-research", "bayesian-updating", "custody-chain", "refusal"],
        "endpoints": {
            "http": "https://api.veritas.example/v1/research",
            "mcp": "https://mcp.veritas.example"
        },
        "x402": {"network": "eip155:8453", "price": "$0.25"},
        "version": "0.1.0",
        "registeredAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }
    doc["content_hash"] = compute_content_hash(json.dumps(doc, sort_keys=True))
    return doc
