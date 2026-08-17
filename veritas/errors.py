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
    PAYMENT_REQUEST_ID_ALREADY_CLAIMED = "payment_request_id_already_claimed"
    PAYMENT_AUTHORIZATION_IN_PROGRESS = "payment_authorization_in_progress"
    PAYMENT_AUTHORIZATION_BOUND_TO_ANOTHER_REQUEST = "payment_authorization_bound_to_another_request"
    REPLAY_PROTECTION_UNAVAILABLE = "replay_protection_unavailable"
    SETTLEMENT_FAILED = "settlement_failed"
    RETRIEVAL_UNAVAILABLE = "retrieval_unavailable"
    RECEIPT_NOT_FOUND = "receipt_not_found"
    RECEIPT_GONE = "receipt_gone"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    REQUEST_TOO_LARGE = "request_too_large"
    RATE_LIMITED = "rate_limited"
    SERVICE_OVERLOADED = "service_overloaded"
    NOT_READY = "not_ready"
    INTERNAL_ERROR = "internal_error"
    CREDITS_INSUFFICIENT = "credits_insufficient"
    SIWX_INVALID = "siwx_invalid"
    SESSION_INVALID = "session_invalid"
    CREDITS_TOPUP_UNAVAILABLE = "credits_topup_unavailable"
    ESCROW_LOCK_NOT_FOUND = "escrow_lock_not_found"
    ESCROW_REFUSED = "escrow_refused"
    ESCROW_SETTLEMENT_UNAVAILABLE = "escrow_settlement_unavailable"
    SIGNALS_UNAVAILABLE = "signals_unavailable"
    SIGNALS_REFUSED = "signals_refused"


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
        "meaning": "This payment authorization was used for a request that cannot be re-delivered; request a fresh 402 challenge and sign a new authorization. A request that was delivered is replayed with its deliverable instead of this error.",
        "retriable": False,
    },
    ErrorCode.PAYMENT_REQUEST_ID_ALREADY_CLAIMED.value: {
        "status": 409,
        "meaning": "A different authorization is already recorded against this request id. Retry with a fresh request.",
        "retriable": True,
    },
    ErrorCode.PAYMENT_AUTHORIZATION_BOUND_TO_ANOTHER_REQUEST.value: {
        "status": 409,
        "meaning": "This payment authorization already bought a different request. Resubmitting it returns that request's deliverable; it cannot buy a second, different one. Request a fresh 402 challenge for the new question. request_id names the request it did buy.",
        "retriable": False,
    },
    ErrorCode.PAYMENT_AUTHORIZATION_IN_PROGRESS.value: {
        "status": 409,
        "meaning": "A request against this payment authorization is still running. Wait for it to finish and resubmit the same authorization to collect the deliverable; do not sign a new one. If repeated resubmissions keep returning this error, the original request likely died mid-work — nothing was settled, and a fresh authorization is the way forward.",
        "retriable": True,
    },
    ErrorCode.REPLAY_PROTECTION_UNAVAILABLE.value: {
        "status": 503,
        "meaning": "The replay guard's store is unusable; the request is refused rather than served unguarded.",
        "retriable": True,
    },
    ErrorCode.SETTLEMENT_FAILED.value: {
        "status": 402,
        "meaning": "The facilitator answered and refused settlement; the work was done, is held, and was not delivered. Nothing was charged. On /v1/research and /v1/notarize, resubmitting the same authorization once the cause is fixed returns the held deliverable without re-running the work. On /v1/credits/topup there is no held deliverable and replays are refused — sign a fresh authorization. A settlement we simply never heard back about is NOT this error: it returns 200 with payment.state == 'indeterminate', because the funds may have moved.",
        "retriable": True,
    },
    ErrorCode.RETRIEVAL_UNAVAILABLE.value: {
        "status": 503,
        "meaning": "Retrieval itself failed; this is the service's failure, reported as unavailable and never billed. The full research body accompanies this code.",
        "retriable": True,
    },
    ErrorCode.RECEIPT_NOT_FOUND.value: {
        "status": 404,
        "meaning": "No custody receipt was ever stored under the requested request_id. Distinct from receipt_gone: this id is not known to have existed.",
        "retriable": False,
    },
    ErrorCode.RECEIPT_GONE.value: {
        "status": 410,
        "meaning": "A custody receipt for this request_id existed and was deleted by retention. The id is known; the body is not recoverable. Distinct from receipt_not_found (never seen).",
        "retriable": False,
    },
    ErrorCode.DEADLINE_EXCEEDED.value: {
        "status": 503,
        "meaning": "The work outran the payment authorization window, so nothing was settled and nothing is owed. Request a fresh challenge and sign a new authorization.",
        "retriable": True,
    },
    ErrorCode.INVALID_REQUEST.value: {
        "status": 422,
        "meaning": "The request body or parameters failed validation; detail lists the failing fields.",
        "retriable": False,
    },
    ErrorCode.NOT_FOUND.value: {
        "status": 404,
        "meaning": "The requested surface does not exist in the current configuration. Receipts use the more specific receipt_not_found / receipt_gone pair.",
        "retriable": False,
    },
    ErrorCode.UNAUTHORIZED.value: {
        "status": 401,
        "meaning": "The request carried a credential for a token-gated surface and it did not match. Session problems use siwx_invalid / session_invalid.",
        "retriable": False,
    },
    ErrorCode.REQUEST_TOO_LARGE.value: {
        "status": 413,
        "meaning": "The request body exceeds the accepted size; it was refused rather than read. Send less content.",
        "retriable": False,
    },
    ErrorCode.RATE_LIMITED.value: {
        "status": 429,
        "meaning": "Too many requests from this caller in the current window. Retry-After gives the wait in seconds. Liveness checks are never rate limited.",
        "retriable": True,
    },
    ErrorCode.SERVICE_OVERLOADED.value: {
        "status": 503,
        "meaning": "Every concurrent research slot is in use. The request was shed immediately rather than queued, so no work was done, no payment authorization was claimed and nothing is owed. Retry-After gives a suggested wait.",
        "retriable": True,
    },
    ErrorCode.NOT_READY.value: {
        "status": 503,
        "meaning": "The process is alive but cannot serve — typically invalid payment configuration. Returned by /readyz only; it is a signal for a load balancer, not for a buyer.",
        "retriable": True,
    },
    ErrorCode.INTERNAL_ERROR.value: {
        "status": 500,
        "meaning": "An unhandled server-side error. The cause is deliberately not described: the exception text names internals. Nothing was billed. If it recurs, the service is broken, not the request.",
        "retriable": True,
    },
    ErrorCode.CREDITS_INSUFFICIENT.value: {
        "status": 402,
        "meaning": "SIWx session is valid but prepaid credit balance cannot cover this request. Top up via POST /v1/credits/topup (x402) or pay per request with X-PAYMENT.",
        "retriable": False,
    },
    ErrorCode.SIWX_INVALID.value: {
        "status": 401,
        "meaning": "The SIWx message or signature did not verify (domain/uri/chain mismatch, expired challenge, or bad signature).",
        "retriable": False,
    },
    ErrorCode.SESSION_INVALID.value: {
        "status": 401,
        "meaning": "X-VERITAS-SESSION is missing, unknown, or expired. Obtain a new session via POST /v1/siwx/verify.",
        "retriable": False,
    },
    ErrorCode.CREDITS_TOPUP_UNAVAILABLE.value: {
        "status": 503,
        "meaning": "Credit top-up requires live payment configuration and a settled x402 authorization. Free/misconfigured modes cannot invent credits.",
        "retriable": True,
    },
    ErrorCode.ESCROW_LOCK_NOT_FOUND.value: {
        "status": 404,
        "meaning": "No escrow lock exists under the requested lock_id, or the id is not a 64-hex digest.",
        "retriable": False,
    },
    ErrorCode.ESCROW_REFUSED.value: {
        "status": 409,
        "meaning": "The lock, release, or forfeit could not proceed (malformed authorization, nonce replay, wrong state, or facilitator refusal). The lock is unchanged on a facilitator refusal so a later collect can retry.",
        "retriable": False,
    },
    ErrorCode.ESCROW_SETTLEMENT_UNAVAILABLE.value: {
        "status": 503,
        "meaning": "Forfeit submit requires live payment configuration. Free mode does not invent a simulated settlement.",
        "retriable": True,
    },
    ErrorCode.SIGNALS_UNAVAILABLE.value: {
        "status": 503,
        "meaning": "Every named prediction-market venue failed to answer. Nothing was stored.",
        "retriable": True,
    },
    ErrorCode.SIGNALS_REFUSED.value: {
        "status": 422,
        "meaning": "The signals request named an unknown venue or an empty query.",
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
