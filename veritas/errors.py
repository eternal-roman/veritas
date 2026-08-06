"""The API error contract: registered codes, one envelope.

Before this module, the API spoke three shapes: ad-hoc `{"error": <string>}`
bodies, x402-spec 402 challenges whose `error` field is free text, and a 503
retrieval-unavailable path that returned the research body with no `error`
key at all. Codes were inline literals, so nothing stopped a rename from
silently breaking every consumer.

This module is the single registry. Every non-402 error response is built by
`error_envelope` with a code from `ErrorCode`, and `GET /v1/errors` serves
the registry so an agent can learn the failure surface before paying.

The deliberate exception: 402 bodies keep the x402 challenge shape
(`x402Version`, `accepts`, free-text `error`) because that envelope belongs
to the x402 specification, not to this service.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    PAYMENT_MISCONFIGURED = "payment_misconfigured"
    PAYMENT_VERIFICATION_UNAVAILABLE = "payment_verification_unavailable"
    PAYMENT_NONCE_MISSING = "payment_nonce_missing"
    PAYMENT_NONCE_MALFORMED = "payment_nonce_malformed"
    PAYMENT_NONCE_ALREADY_SPENT = "payment_nonce_already_spent"
    REPLAY_PROTECTION_UNAVAILABLE = "replay_protection_unavailable"
    SETTLEMENT_FAILED = "settlement_failed"
    RETRIEVAL_UNAVAILABLE = "retrieval_unavailable"
    RECEIPT_NOT_FOUND = "receipt_not_found"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    INVALID_REQUEST = "invalid_request"


ERROR_REGISTRY: dict[str, dict[str, Any]] = {
    ErrorCode.PAYMENT_MISCONFIGURED.value: {
        "status": 503,
        "meaning": "Payment is required but the service's payment configuration is invalid; nothing is served rather than serving for free.",
        "retriable": False,
    },
    ErrorCode.PAYMENT_VERIFICATION_UNAVAILABLE.value: {
        "status": 503,
        "meaning": "The payment facilitator could not be reached or answered malformed; the payment was not judged invalid.",
        "retriable": True,
    },
    ErrorCode.PAYMENT_NONCE_MISSING.value: {
        "status": 409,
        "meaning": "The payment payload carries no usable authorization nonce, so replay protection cannot admit it.",
        "retriable": False,
    },
    ErrorCode.PAYMENT_NONCE_MALFORMED.value: {
        "status": 409,
        "meaning": "The authorization nonce is not a 32-byte hex value.",
        "retriable": False,
    },
    ErrorCode.PAYMENT_NONCE_ALREADY_SPENT.value: {
        "status": 409,
        "meaning": "This payment authorization was already used; request a fresh 402 challenge and sign a new authorization.",
        "retriable": False,
    },
    ErrorCode.REPLAY_PROTECTION_UNAVAILABLE.value: {
        "status": 503,
        "meaning": "The replay guard's store is unusable; the request is refused rather than served unguarded.",
        "retriable": True,
    },
    ErrorCode.SETTLEMENT_FAILED.value: {
        "status": 402,
        "meaning": "The payment verified but settlement failed; the work was done and not delivered, and the buyer was not charged.",
        "retriable": True,
    },
    ErrorCode.RETRIEVAL_UNAVAILABLE.value: {
        "status": 503,
        "meaning": "Retrieval itself failed; this is the service's failure, reported as unavailable and never billed. The full research body accompanies this code.",
        "retriable": True,
    },
    ErrorCode.RECEIPT_NOT_FOUND.value: {
        "status": 404,
        "meaning": "No custody receipt is stored under the requested request_id.",
        "retriable": False,
    },
    ErrorCode.DEADLINE_EXCEEDED.value: {
        "status": 503,
        "meaning": "The work outran the payment authorization window, so nothing was settled and nothing is owed. Request a fresh challenge and sign a new authorization.",
        "retriable": True,
    },
    ErrorCode.INVALID_REQUEST.value: {
        "status": 422,
        "meaning": "The request body failed validation; detail lists the failing fields.",
        "retriable": False,
    },
}


def error_envelope(code: ErrorCode | str, detail: Any = None, **extra: Any) -> dict[str, Any]:
    """Build the one error body shape: {"error": <code>, "detail": ..., **extra}."""
    value = code.value if isinstance(code, ErrorCode) else str(code)
    body: dict[str, Any] = {"error": value}
    if detail is not None:
        body["detail"] = detail
    body.update(extra)
    return body
