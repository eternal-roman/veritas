"""FastAPI surface: discovery, x402-gated research, and verification.

Run it with the installed console script or uvicorn directly:

    veritas-server
    python -m uvicorn veritas.server:app
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from veritas import __version__
from veritas.constitution import build_constitution
from veritas.custody import CustodyStore
from veritas.deadline import Deadline, DeadlineTooShort
from veritas.discovery import LLMS_TXT
from veritas.errors import ERROR_REGISTRY, ErrorCode, error_envelope
from veritas.facilitator import get_facilitator
from veritas.hashing import verify_content_hash
from veritas.identity import build_identity
from veritas.payment_config import get_payment_config
from veritas.pipeline import run_research
from veritas.replay import SpentNonceStore, extract_nonce
from veritas.trust import OutcomeLog, score_service
from veritas.x402 import (
    PriceError,
    build_402_challenge,
    build_payment_requirements,
    decode_payment_header,
    payment_authorization,
)

app = FastAPI(title="Veritas Research", version=__version__)

RESOURCE_PATH = "/v1/research"

# Ceiling on retrieval work for one paid request, independent of how long the
# buyer's authorization happens to run.
MAX_WORK_SECONDS = 25


def _authorization_valid_before(payload: dict[str, Any]) -> float:
    """The buyer's authorization expiry, or a conservative default.

    A payload we cannot read a `validBefore` from is budgeted as if the window
    were the protocol's advertised maximum, so a malformed value can shorten
    the budget but never extend it.
    """
    authorization = payment_authorization(payload) or {}
    raw = authorization.get("validBefore") or authorization.get("valid_before")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return time.time() + DEFAULT_AUTHORIZATION_SECONDS


DEFAULT_AUTHORIZATION_SECONDS = 60


def resource_url() -> str:
    """The absolute URL of the paid resource, as x402 expects in `resource`.

    Falls back to the bare path only when no public URL is configured, which
    live mode refuses (see veritas/payment_config.py) — so a published
    challenge always names something a counterparty can dial.
    """
    base = (os.getenv("VERITAS_PUBLIC_URL") or "").strip().rstrip("/")
    return f"{base}{RESOURCE_PATH}" if base else RESOURCE_PATH


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
    deadline: Deadline | None = None

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
                resource=resource_url(),
            )
        except PriceError:
            # Misconfiguration must not silently become free service. The
            # exception text describes server-side configuration, so it stays
            # out of the response body (CodeQL: information exposure); the
            # operator inspects config via /v1/payment-config, not this error.
            return JSONResponse(
                status_code=500,
                content=error_envelope(
                    ErrorCode.PAYMENT_MISCONFIGURED,
                    "price configuration rejected at challenge construction",
                ),
            )
        requirements_dict = requirements.to_dict()

        header = request.headers.get("X-PAYMENT")
        if not header:
            return JSONResponse(
                status_code=402,
                content=build_402_challenge(cfg.pay_to, cfg.network, cfg.price, resource_url()),
                headers=PAYMENT_REQUIRED_HEADER,
            )

        payment_payload = decode_payment_header(header)
        if payment_payload is None:
            return JSONResponse(status_code=402, content=build_402_challenge(
                cfg.pay_to, cfg.network, cfg.price, resource_url(),
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
                cfg.pay_to, cfg.network, cfg.price, resource_url(), error=reason,
            ), headers=PAYMENT_REQUIRED_HEADER)

        # Replay protection (roadmap 0.4). The nonce is claimed after the
        # facilitator accepts the payment and BEFORE any retrieval pass, so a
        # resubmitted header cannot make us do the work a second time. The
        # claim is never released: the authorization stays live on chain, so
        # re-admitting it would restore the double-work this prevents.
        # Budget the work against the authorization that pays for it. Doing
        # this before the nonce claim means an authorization too short to
        # finish costs the buyer nothing: no work, no burned nonce.
        try:
            deadline = Deadline.for_authorization(
                valid_before=_authorization_valid_before(payment_payload),
                max_work_seconds=MAX_WORK_SECONDS,
            )
        except DeadlineTooShort as exc:
            return JSONResponse(status_code=402, content=build_402_challenge(
                cfg.pay_to, cfg.network, cfg.price, resource_url(),
                error=f"authorization window too short: {exc}",
            ), headers=PAYMENT_REQUIRED_HEADER)

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

    # The window may have closed while we worked. Settling now would present an
    # expired authorization; the buyer is not charged and is told to retry with
    # a fresh one, which is the honest outcome for our own slowness.
    if deadline is not None and deadline.expired():
        result["billable"] = False
        result["status"] = "unavailable"
        result["refusal_reason"] = "retrieval_unavailable"
        result["error"] = ErrorCode.DEADLINE_EXCEEDED.value
        result["payment"] = {"settled": False, "reason": "deadline_exceeded_before_settlement"}
        outcomes.record(result["status"], bool(result["custody_valid"]), False)
        return JSONResponse(status_code=503, content=result)

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
        "resources": [{"resource": resource_url(), "method": "POST"}],
        "facilitator": cfg.facilitator,
        "network": cfg.network,
        "mode": cfg.mode,
        # An empty accepts is an honest "no offer"; configured_price is the
        # price that would apply in live mode — config, not an offer.
        "accepts": [],
        "configured_price": cfg.price,
        # Discovery must be self-traversing: one document reaches every
        # machine-readable surface. Relative paths, so no base URL is faked.
        "links": {
            "identity": "/v1/identity",
            "trust": "/v1/trust",
            "constitution": "/v1/constitution",
            "errors": "/v1/errors",
            "schema": "/v1/schema",
            "openapi": "/openapi.json",
            "llms": "/llms.txt",
        },
    }
    if cfg.is_live_ready():
        try:
            body["accepts"] = [build_payment_requirements(
                cfg.pay_to, cfg.network, cfg.price, resource_url(),
            ).to_dict()]
        except PriceError:
            # Category only, same as the /v1/research path: the exception
            # text describes server-side configuration.
            body["error"] = "payment_misconfigured: price configuration rejected"
    return body


@app.get("/llms.txt")
def llms_txt():
    """Agent-readable discovery index; the repo-root llms.txt mirrors this."""
    return PlainTextResponse(LLMS_TXT)


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
