"""ERC-8004 compatible identity document."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from . import __version__
from .constitution import CONSTITUTION_VERSION
from .hashing import compute_content_hash


def build_identity(
    pay_to: str = "0x0000000000000000000000000000000000000000",
    network: str = "eip155:8453",
    price: str = "$0.25",
    base_url: str | None = None,
) -> dict[str, Any]:
    # The previous version defaulted to https://api.veritas.example — a
    # reserved domain nobody can dial — so a default deployment advertised
    # endpoints that could never resolve. With no configured base URL the
    # document now carries relative paths and says so, which is honest and
    # still self-traversing for a client that already reached the service.
    configured = base_url or os.getenv("VERITAS_PUBLIC_URL") or None
    base = configured.rstrip("/") if configured else ""

    # Capabilities and description must match the served path (pipeline +
    # custody + support counts). Bayesian belief updating was removed from the
    # product surface (see veritas/support.py and pipeline.py) — advertising it
    # here was a discovery-document lie that survived the Phase T retract.
    doc: dict[str, Any] = {
        "name": "Veritas Research",
        "description": (
            "Evidence-grounded research with a hash-chained custody ledger, "
            "recomputable support counts, and explicit refusal."
        ),
        "paymentAddress": pay_to,
        "capabilities": [
            "evidence-grounded-research",
            "evidence-notarization",
            "custody-chain",
            "support-counts",
            "refusal",
            "independent-hash-verification",
            "origin-refetch-verification",
            "evidence-record-attestation-verify",
            "portable-evidence-pack",
            "merkle-evidence-log",
            "prepaid-credit-sessions",
        ],
        "base_url_configured": configured is not None,
        # The complete surface lives at /v1/hooks; these are the endpoints an
        # identity consumer most needs, and a sync test keeps every one of
        # them registered there (no phantom, no omission of a paid product).
        "endpoints": {
            "research": f"{base}/v1/research",
            "notarize": f"{base}/v1/notarize",
            "verify": f"{base}/v1/verify",
            "attestations_verify": f"{base}/v1/attestations/verify",
            "packs_verify": f"{base}/v1/packs/verify",
            "evidence_log": f"{base}/v1/log",
            "evidence_log_proof": f"{base}/v1/log/proof",
            "evidence_log_verify": f"{base}/v1/log/verify",
            "receipts": f"{base}/v1/receipts/{{request_id}}",
            "evidence": f"{base}/v1/evidence/{{content_hash}}",
            "trust": f"{base}/v1/trust",
            "schema": f"{base}/v1/schema",
            "errors": f"{base}/v1/errors",
            "payment_config": f"{base}/v1/payment-config",
            "siwx_challenge": f"{base}/v1/siwx/challenge",
            "siwx_verify": f"{base}/v1/siwx/verify",
            "credits": f"{base}/v1/credits",
            "credits_topup": f"{base}/v1/credits/topup",
            "identity": f"{base}/v1/identity",
            "constitution": f"{base}/v1/constitution",
            "hooks": f"{base}/v1/hooks",
            "llms": f"{base}/llms.txt",
            "adopt": f"{base}/adopt.json",
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
