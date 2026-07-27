"""ERC-8004 compatible identity document."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from . import __version__
from .constitution import CONSTITUTION_VERSION
from .hashing import compute_content_hash

DEFAULT_BASE_URL = "https://api.veritas.example"


def build_identity(
    pay_to: str = "0x0000000000000000000000000000000000000000",
    network: str = "eip155:8453",
    price: str = "$0.25",
    base_url: str | None = None,
) -> dict[str, Any]:
    base = (base_url or os.getenv("VERITAS_PUBLIC_URL", DEFAULT_BASE_URL)).rstrip("/")

    doc: dict[str, Any] = {
        "name": "Veritas Research",
        "description": (
            "Evidence-grounded research with a hash-chained custody ledger, "
            "Bayesian belief updating, and explicit refusal."
        ),
        "paymentAddress": pay_to,
        "capabilities": [
            "evidence-grounded-research",
            "bayesian-updating",
            "custody-chain",
            "refusal",
            "independent-hash-verification",
        ],
        "endpoints": {
            "research": f"{base}/v1/research",
            "verify": f"{base}/v1/verify",
            "receipts": f"{base}/v1/receipts/{{request_id}}",
            "identity": f"{base}/v1/identity",
            "constitution": f"{base}/v1/constitution",
            "wellKnown": f"{base}/.well-known/x402",
        },
        "x402": {"network": network, "price": price},
        "constitution": {
            "version": CONSTITUTION_VERSION,
            "endpoint": f"{base}/v1/constitution",
        },
        "version": __version__,
    }

    # Hash the stable document only. The previous version folded `registeredAt`
    # into the hashed body, so the identity hash changed on every call and could
    # not be used to detect tampering.
    doc["content_hash"] = compute_content_hash(json.dumps(doc, sort_keys=True))
    doc["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return doc
