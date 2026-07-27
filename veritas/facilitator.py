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
from typing import Any, Dict, Optional

DEFAULT_TIMEOUT = 15


@dataclass
class VerificationResult:
    is_valid: bool
    payer: Optional[str] = None
    invalid_reason: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"is_valid": self.is_valid, "payer": self.payer, "invalid_reason": self.invalid_reason}


@dataclass
class SettlementResult:
    success: bool
    transaction: Optional[str] = None
    network: Optional[str] = None
    payer: Optional[str] = None
    error_reason: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "transaction": self.transaction,
            "network": self.network,
            "payer": self.payer,
            "error_reason": self.error_reason,
        }


class FacilitatorClient:
    """Minimal, dependency-free x402 facilitator client."""

    def __init__(self, base_url: str, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode())

    def verify(self, payment_payload: Dict[str, Any], requirements: Dict[str, Any]) -> VerificationResult:
        """Ask the facilitator whether this payment is valid. Fails closed."""
        if not self.base_url:
            return VerificationResult(False, invalid_reason="no_facilitator_configured")
        body = {
            "x402Version": 1,
            "paymentPayload": payment_payload,
            "paymentRequirements": requirements,
        }
        try:
            data = self._post("/verify", body)
        except urllib.error.HTTPError as exc:
            return VerificationResult(False, invalid_reason=f"facilitator_http_{exc.code}")
        except urllib.error.URLError as exc:
            return VerificationResult(False, invalid_reason=f"facilitator_unreachable: {exc.reason}")
        except (json.JSONDecodeError, TimeoutError) as exc:
            return VerificationResult(False, invalid_reason=f"facilitator_bad_response: {exc}")

        return VerificationResult(
            is_valid=bool(data.get("isValid")),
            payer=data.get("payer"),
            invalid_reason=data.get("invalidReason"),
            raw=data,
        )

    def settle(self, payment_payload: Dict[str, Any], requirements: Dict[str, Any]) -> SettlementResult:
        """Capture funds. Only called once a billable result exists."""
        if not self.base_url:
            return SettlementResult(False, error_reason="no_facilitator_configured")
        body = {
            "x402Version": 1,
            "paymentPayload": payment_payload,
            "paymentRequirements": requirements,
        }
        try:
            data = self._post("/settle", body)
        except urllib.error.HTTPError as exc:
            return SettlementResult(False, error_reason=f"facilitator_http_{exc.code}")
        except urllib.error.URLError as exc:
            return SettlementResult(False, error_reason=f"facilitator_unreachable: {exc.reason}")
        except (json.JSONDecodeError, TimeoutError) as exc:
            return SettlementResult(False, error_reason=f"facilitator_bad_response: {exc}")

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

    def verify(self, payment_payload: Dict[str, Any], requirements: Dict[str, Any]) -> VerificationResult:
        if not isinstance(payment_payload, dict) or not payment_payload:
            return VerificationResult(False, invalid_reason="malformed_payload")
        if payment_payload.get("scheme") and payment_payload.get("scheme") != requirements.get("scheme"):
            return VerificationResult(False, invalid_reason="scheme_mismatch")
        return VerificationResult(True, payer=payment_payload.get("payer") or "simulated-payer",
                                  raw={"mode": "simulated"})

    def settle(self, payment_payload: Dict[str, Any], requirements: Dict[str, Any]) -> SettlementResult:
        return SettlementResult(
            success=True,
            transaction="simulated:no-onchain-settlement",
            network=requirements.get("network"),
            payer=payment_payload.get("payer") or "simulated-payer",
            raw={"mode": "simulated"},
        )


def get_facilitator(base_url: str, live: bool) -> FacilitatorClient:
    return FacilitatorClient(base_url) if live else SimulatedFacilitatorClient()
