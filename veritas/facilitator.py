"""x402 facilitator client: real verification and settlement.

Previously the service granted access to any request carrying a non-empty
`X-PAYMENT` header — `X-PAYMENT: hello` bought unlimited research — and the
configured facilitator URL was never contacted by any code path. This module
performs the two calls the protocol actually requires:

    POST {facilitator}/verify   is this payment payload valid and sufficient?
    POST {facilitator}/settle   move the funds on chain

Design rules:

1. **Fail closed.** Any error — unreachable facilitator, malformed response,
   timeout — denies access. A payment system that grants service when its
   verifier is down is not a payment system.
2. **Verify before work, settle after.** Settlement is only captured once the
   research actually produced a billable result, so an outage on our side is
   never charged to the buyer.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from . import __version__
from .safeurl import UnsafeUrlError, require_http_url

DEFAULT_TIMEOUT = 15

#: Sent on every facilitator call. The reference facilitator (x402.org) sits
#: behind Cloudflare, which rejects the default ``Python-urllib/x.y`` agent
#: with error 1010 (HTTP 403) before the request body is read — so a client
#: that does not identify itself cannot verify or settle against it at all.
#: Observed live 2026-08-08; the 403 surfaced as `facilitator_http_403` and
#: failed closed, which is correct behaviour but permanent, not transient.
USER_AGENT = f"veritas-facilitator-client/{__version__} (+https://github.com/eternal-roman/veritas)"

#: Settlement failures where the facilitator never gave us an answer. The
#: request may have reached the chain, so the outcome is unknown — and "we do
#: not know" is not "it did not happen". Recording these as failures
#: understates revenue and asserts a fact about the chain we did not observe
#: (defect R7). `facilitator_unreachable` is deliberately NOT here: a refused
#: connection or a failed DNS lookup means the request never left, so nothing
#: settled.
INDETERMINATE_SETTLEMENT_REASONS = frozenset({
    "facilitator_timeout",
    "facilitator_bad_response",
})

#: Verification failures that are outages rather than rejections. The caller
#: fails closed with a 503 so buyers retry, instead of telling them their
#: payment was refused.
VERIFICATION_OUTAGE_PREFIXES = (
    "facilitator_unreachable",
    "facilitator_timeout",
    "facilitator_http",
    "facilitator_bad_response",
)


@dataclass
class VerificationResult:
    is_valid: bool
    payer: str | None = None
    invalid_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"is_valid": self.is_valid, "payer": self.payer, "invalid_reason": self.invalid_reason}


@dataclass
class SettlementResult:
    success: bool
    transaction: str | None = None
    network: str | None = None
    payer: str | None = None
    error_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def outcome(self) -> str:
        """`settled`, `indeterminate` or `failed`.

        The distinction is load-bearing: a facilitator that timed out or
        answered unreadably may still have moved the funds, so recording that
        as a failure would understate revenue and would tell the buyer their
        payment did not go through when we do not know that.
        """
        if self.success:
            return "settled"
        reason = self.error_reason or ""
        if reason in INDETERMINATE_SETTLEMENT_REASONS or reason.startswith("facilitator_http_5"):
            return "indeterminate"
        return "failed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "state": self.outcome,
            "transaction": self.transaction,
            "network": self.network,
            "payer": self.payer,
            "error_reason": self.error_reason,
        }


_TRANSPORT_ERRORS = (
    urllib.error.HTTPError,   # checked first: it subclasses URLError
    urllib.error.URLError,
    TimeoutError,
    json.JSONDecodeError,
)


def _transport_reason(exc: BaseException) -> str:
    """Name a transport failure as a bare category.

    Two jobs. It keeps exception text — resolver detail, socket paths — out of
    bodies that reach external buyers (CodeQL: information exposure). And it
    separates "the request never left" from "we never heard back", because
    only the first proves nothing settled.
    """
    if isinstance(exc, urllib.error.HTTPError):
        return f"facilitator_http_{exc.code}"
    if isinstance(exc, TimeoutError):
        return "facilitator_timeout"
    if isinstance(exc, urllib.error.URLError):
        if isinstance(exc.reason, TimeoutError):
            return "facilitator_timeout"
        return "facilitator_unreachable"
    return "facilitator_bad_response"


def _wire_requirements(requirements: dict[str, Any]) -> dict[str, Any]:
    """Translate an internal accepts entry to the x402 v2 PaymentRequirements shape.

    Observed against the live x402.org facilitator on 2026-08-08 (Base
    Sepolia, scheme ``exact``): the facilitator routes handlers by
    ``x402Version`` and registers only v2 for this scheme/network, so a v1
    body is answered with "No facilitator registered". v2 renamed
    ``maxAmountRequired`` to ``amount`` and moved ``resource`` /
    ``description`` / ``mimeType`` out of the requirements object into a
    structured ``resource`` block on the payment payload.
    """
    wire = dict(requirements)
    if "maxAmountRequired" in wire and "amount" not in wire:
        wire["amount"] = wire.pop("maxAmountRequired")
    for moved in ("resource", "description", "mimeType"):
        wire.pop(moved, None)
    return wire


def _wire_payment_payload(
    payment_payload: dict[str, Any], requirements: dict[str, Any]
) -> dict[str, Any]:
    """Translate an internal (v1-shaped) payment payload to the v2 wire shape.

    The inner ``payload`` block — signature plus EIP-3009 authorization — is
    identical between versions and passes through untouched; the recovered
    payer against the live facilitator matched the local signer, so the
    signing path itself needed no change. v2 wraps it with the structured
    ``resource`` and echoes the buyer-selected requirement as ``accepted``.
    """
    return {
        "x402Version": 2,
        "resource": {
            "url": requirements.get("resource", ""),
            "description": requirements.get("description", ""),
            "mimeType": requirements.get("mimeType", "application/json"),
        },
        "accepted": _wire_requirements(requirements),
        "payload": payment_payload.get("payload", {}),
        "extensions": {},
    }


class FacilitatorClient:
    """Minimal, dependency-free x402 facilitator client."""

    def __init__(self, base_url: str, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        # The facilitator URL is operator configuration, but urlopen honours
        # file: and other schemes, so the allowlist is applied here rather than
        # trusted upstream.
        url = require_http_url(f"{self.base_url}{path}")
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        with urllib.request.urlopen(  # nosec B310 - scheme checked by require_http_url
            req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode())

    def verify(self, payment_payload: dict[str, Any], requirements: dict[str, Any]) -> VerificationResult:
        """Ask the facilitator whether this payment is valid. Fails closed."""
        if not self.base_url:
            return VerificationResult(False, invalid_reason="no_facilitator_configured")
        body = {
            "x402Version": 2,
            "paymentPayload": _wire_payment_payload(payment_payload, requirements),
            "paymentRequirements": _wire_requirements(requirements),
        }
        try:
            data = self._post("/verify", body)
        except UnsafeUrlError:
            return VerificationResult(False, invalid_reason="facilitator_url_rejected")
        except _TRANSPORT_ERRORS as exc:
            return VerificationResult(False, invalid_reason=_transport_reason(exc))

        return VerificationResult(
            is_valid=bool(data.get("isValid")),
            payer=data.get("payer"),
            invalid_reason=data.get("invalidReason"),
            raw=data,
        )

    def settle(self, payment_payload: dict[str, Any], requirements: dict[str, Any]) -> SettlementResult:
        """Capture funds. Only called once a billable result exists."""
        if not self.base_url:
            return SettlementResult(False, error_reason="no_facilitator_configured")
        body = {
            "x402Version": 2,
            "paymentPayload": _wire_payment_payload(payment_payload, requirements),
            "paymentRequirements": _wire_requirements(requirements),
        }
        try:
            data = self._post("/settle", body)
        except UnsafeUrlError:
            return SettlementResult(False, error_reason="facilitator_url_rejected")
        except _TRANSPORT_ERRORS as exc:
            return SettlementResult(False, error_reason=_transport_reason(exc))

        return SettlementResult(
            success=bool(data.get("success")),
            transaction=data.get("transaction"),
            network=data.get("network"),
            payer=data.get("payer"),
            error_reason=data.get("errorReason"),
            raw=data,
        )


class SimulatedFacilitatorClient(FacilitatorClient):
    """Deterministic stand-in for free mode and tests.

    Accepts structurally valid payloads and fabricates a settlement reference.
    It is explicitly labelled in every result so simulated settlements can
    never be mistaken for on-chain ones in the ledger.
    """

    def __init__(self, *_args, **_kwargs):
        super().__init__(base_url="", timeout=1)

    def verify(self, payment_payload: dict[str, Any], requirements: dict[str, Any]) -> VerificationResult:
        if not isinstance(payment_payload, dict) or not payment_payload:
            return VerificationResult(False, invalid_reason="malformed_payload")
        if payment_payload.get("scheme") and payment_payload.get("scheme") != requirements.get("scheme"):
            return VerificationResult(False, invalid_reason="scheme_mismatch")
        return VerificationResult(True, payer=payment_payload.get("payer") or "simulated-payer",
                                  raw={"mode": "simulated"})

    def settle(self, payment_payload: dict[str, Any], requirements: dict[str, Any]) -> SettlementResult:
        return SettlementResult(
            success=True,
            transaction="simulated:no-onchain-settlement",
            network=requirements.get("network"),
            payer=payment_payload.get("payer") or "simulated-payer",
            raw={"mode": "simulated"},
        )


def get_facilitator(base_url: str, live: bool) -> FacilitatorClient:
    return FacilitatorClient(base_url) if live else SimulatedFacilitatorClient()
