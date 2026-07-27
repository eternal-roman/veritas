"""FastAPI surface: discovery, x402-gated research, and verification.

Run it with the installed console script or uvicorn directly:

    veritas-server
    python -m uvicorn veritas.server:app
"""

from __future__ import annotations

import base64
import binascii
import json
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from veritas import __version__
from veritas.constitution import build_constitution
from veritas.custody import CustodyStore
from veritas.errors import ERROR_REGISTRY, ErrorCode, error_envelope
from veritas.facilitator import get_facilitator
from veritas.hashing import verify_content_hash
from veritas.identity import build_identity
from veritas.payment_config import get_payment_config
from veritas.pipeline import run_research
from veritas.replay import SpentNonceStore, extract_nonce
from veritas.trust import OutcomeLog, score_service
from veritas.x402 import PriceError, build_402_challenge, build_payment_requirements

app = FastAPI(title="Veritas Research", version=__version__)

RESOURCE_PATH = "/v1/research"
store = CustodyStore()
outcomes = OutcomeLog()
nonces = SpentNonceStore()

# 402 bodies are x402-spec-shaped, not registry envelopes; the header marks
# the protocol so a client can recognise the challenge without parsing.
PAYMENT_REQUIRED_HEADER = {"Payment-Required": "x402"}


@app.exception_handler(RequestValidationError)
def invalid_request_handler(request: Request, exc: RequestValidationError):
    """422s previously leaked FastAPI's raw shape, unlike every other error."""
    return JSONResponse(
        status_code=422,
        content=error_envelope(ErrorCode.INVALID_REQUEST, jsonable_encoder(exc.errors())),
    )


class ResearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    max_results: int = Field(default=5, ge=1, le=10)


class VerifyRequest(BaseModel):
    content: str
    content_hash: str


def _decode_payment_header(raw: str) -> dict[str, Any] | None:
    """Decode the base64-JSON X-PAYMENT header, tolerating raw JSON.

    Returns None when the header cannot be interpreted, which the caller
    treats as an invalid payment (fail closed).
    """
    if not raw:
        return None
    try:
        decoded = base64.b64decode(raw, validate=True).decode("utf-8")
        payload = json.loads(decoded)
        return payload if isinstance(payload, dict) else None
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        pass
    try:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        return None


@app.get("/health")
def health():
    cfg = get_payment_config()
    return {
        "status": "ok",
        "service": "veritas",
        "version": app.version,
        "payment_mode": cfg.mode,
        "live_ready": cfg.is_live_ready(),
    }


@app.get("/v1/payment-config")
def payment_config():
    return get_payment_config().as_dict()


@app.post(RESOURCE_PATH)
def research(req: ResearchRequest, request: Request):
    cfg = get_payment_config()
    payment_payload: dict[str, Any] | None = None
    requirements_dict: dict[str, Any] | None = None
    facilitator = None

    # Payment was demanded but the configuration is invalid. Refuse to serve
    # rather than silently falling back to giving the paid service away.
    if cfg.mode == "misconfigured":
        return JSONResponse(
            status_code=503,
            content=error_envelope(ErrorCode.PAYMENT_MISCONFIGURED, cfg.config_errors),
        )

    if cfg.require_payment:
        try:
            requirements = build_payment_requirements(
                pay_to=cfg.pay_to,
                network=cfg.network,
                price=cfg.price,
                resource=RESOURCE_PATH,
            )
        except PriceError as exc:
            # Misconfiguration must not silently become free service.
            return JSONResponse(
                status_code=500,
                content=error_envelope(ErrorCode.PAYMENT_MISCONFIGURED, str(exc)),
            )
        requirements_dict = requirements.to_dict()

        header = request.headers.get("X-PAYMENT")
        if not header:
            return JSONResponse(
                status_code=402,
                content=build_402_challenge(cfg.pay_to, cfg.network, cfg.price, RESOURCE_PATH),
                headers=PAYMENT_REQUIRED_HEADER,
            )

        payment_payload = _decode_payment_header(header)
        if payment_payload is None:
            return JSONResponse(status_code=402, content=build_402_challenge(
                cfg.pay_to, cfg.network, cfg.price, RESOURCE_PATH,
                error="X-PAYMENT header is not valid base64-encoded JSON",
            ), headers=PAYMENT_REQUIRED_HEADER)

        facilitator = get_facilitator(cfg.facilitator, live=True)
        verification = facilitator.verify(payment_payload, requirements_dict)
        if not verification.is_valid:
            reason = verification.invalid_reason or "payment_invalid"
            # Facilitator outages fail closed as 503 so buyers retry rather
            # than treating the refusal as a permanent payment rejection.
            if reason.startswith(("facilitator_unreachable", "facilitator_http", "facilitator_bad_response")):
                return JSONResponse(status_code=503, content=error_envelope(
                    ErrorCode.PAYMENT_VERIFICATION_UNAVAILABLE, reason,
                ))
            return JSONResponse(status_code=402, content=build_402_challenge(
                cfg.pay_to, cfg.network, cfg.price, RESOURCE_PATH, error=reason,
            ), headers=PAYMENT_REQUIRED_HEADER)

        # Replay protection (roadmap 0.4). The nonce is claimed after the
        # facilitator accepts the payment and BEFORE any retrieval pass, so a
        # resubmitted header cannot make us do the work a second time. The
        # claim is never released: the authorization stays live on chain, so
        # re-admitting it would restore the double-work this prevents.
        claim = nonces.claim(extract_nonce(payment_payload))
        if not claim.claimed:
            reason = claim.reason or "payment_nonce_rejected"
            if reason.startswith("replay_store_unavailable"):
                # Fail closed: an unusable guard must not become no guard.
                return JSONResponse(status_code=503, content=error_envelope(
                    ErrorCode.REPLAY_PROTECTION_UNAVAILABLE, reason,
                ))
            return JSONResponse(status_code=409, content=error_envelope(
                reason,
                "This payment authorization cannot be admitted. Request a "
                "fresh 402 challenge and sign a new authorization.",
            ))

    result = run_research(req.query, max_results=req.max_results)
    record = store.save(result)
    result["custody_receipt"] = record
    outcomes.record(result["status"], bool(result["custody_valid"]), bool(result["billable"]))

    # Retrieval failures are ours, not the buyer's: never settle for them.
    if result["status"] == "unavailable":
        result["payment"] = {"settled": False, "reason": "not_billable_retrieval_unavailable"}
        # The registry code is additive: the full research body stays because
        # the unavailability report is itself the deliverable here.
        result["error"] = ErrorCode.RETRIEVAL_UNAVAILABLE.value
        return JSONResponse(status_code=503, content=result)

    if cfg.require_payment and facilitator is not None:
        settlement = facilitator.settle(payment_payload, requirements_dict)
        result["payment"] = {"settled": settlement.success, **settlement.to_dict()}
        if not settlement.success:
            return JSONResponse(status_code=402, content=error_envelope(
                ErrorCode.SETTLEMENT_FAILED,
                settlement.error_reason,
                request_id=result["request_id"],
            ))
        return JSONResponse(
            status_code=200,
            content=result,
            headers={"X-PAYMENT-RESPONSE": base64.b64encode(
                json.dumps(settlement.to_dict()).encode()
            ).decode()},
        )

    result["payment"] = {"settled": False, "mode": cfg.mode, "reason": "free_mode"}
    return result


@app.post("/v1/verify")
def verify(req: VerifyRequest):
    """Let any agent independently re-check an evidence hash we published."""
    ok, detail = verify_content_hash(req.content, req.content_hash)
    return {"valid": ok, **detail}


@app.get("/v1/receipts/{request_id}")
def receipt(request_id: str):
    """Retrieve a stored custody record so results stay auditable after the call."""
    record = store.load(request_id)
    if record is None:
        return JSONResponse(status_code=404, content=error_envelope(
            ErrorCode.RECEIPT_NOT_FOUND, request_id=request_id,
        ))
    return record


@app.get("/v1/trust")
def trust():
    s = score_service()
    return s.to_dict()


@app.get("/v1/schema")
def schema():
    """The wire contract as JSON Schema, generated from veritas.schema."""
    from veritas.schema import response_json_schema

    return {
        "response": response_json_schema(),
        "error_envelope": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "VeritasErrorEnvelope",
            "type": "object",
            "required": ["error"],
            "properties": {
                "error": {"type": "string", "enum": sorted(ERROR_REGISTRY)},
                "detail": {},
            },
            "description": (
                "All non-402 error responses. 402s use the x402 challenge "
                "shape instead; see /v1/errors."
            ),
        },
        "openapi": "/openapi.json",
    }


@app.get("/v1/errors")
def errors():
    """The registered failure surface, so an agent can learn it before paying."""
    return {
        "errors": ERROR_REGISTRY,
        "exceptions": {
            "payment_challenge": (
                "402 responses use the x402 challenge shape (x402Version, accepts, "
                "free-text error), owned by the x402 spec rather than this registry."
            ),
        },
    }


@app.get("/v1/constitution")
def constitution():
    """The venue constitution: enforced-or-aspirational articles, free to read."""
    return build_constitution()


@app.get("/v1/identity")
def identity():
    cfg = get_payment_config()
    return build_identity(pay_to=cfg.pay_to, network=cfg.network, price=cfg.price)


@app.get("/.well-known/x402")
def well_known():
    cfg = get_payment_config()
    body: dict[str, Any] = {
        "x402Version": 1,
        "resources": [{"resource": RESOURCE_PATH, "method": "POST"}],
        "facilitator": cfg.facilitator,
        "network": cfg.network,
        "mode": cfg.mode,
    }
    if cfg.is_live_ready():
        try:
            body["accepts"] = [build_payment_requirements(
                cfg.pay_to, cfg.network, cfg.price, RESOURCE_PATH,
            ).to_dict()]
        except PriceError as exc:
            body["error"] = f"payment_misconfigured: {exc}"
    return body


def main() -> None:
    """Console entry point (`veritas-server`)."""
    import uvicorn

    uvicorn.run(
        "veritas.server:app",
        host=os.getenv("VERITAS_HOST", "127.0.0.1"),
        port=int(os.getenv("VERITAS_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
