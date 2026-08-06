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
import uuid
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
from veritas.facilitator import VERIFICATION_OUTAGE_PREFIXES, get_facilitator
from veritas.hashing import verify_content_hash
from veritas.identity import build_identity
from veritas.ledger import REDELIVERABLE_STATES, Ledger, NonceState
from veritas.payment_config import get_payment_config
from veritas.pipeline import run_research
from veritas.trust import OutcomeLog, score_service
from veritas.x402 import (
    PriceError,
    build_402_challenge,
    build_payment_requirements,
    decode_payment_header,
    extract_nonce,
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
ledger = Ledger()

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


def _challenge(cfg, error: str | None = None) -> JSONResponse:
    kwargs = {"error": error} if error else {}
    return JSONResponse(
        status_code=402,
        content=build_402_challenge(
            cfg.pay_to, cfg.network, cfg.price, resource_url(), **kwargs,
        ),
        headers=PAYMENT_REQUIRED_HEADER,
    )


def _payment_response_header(payment: dict[str, Any]) -> dict[str, str]:
    return {"X-PAYMENT-RESPONSE": base64.b64encode(
        json.dumps(payment).encode()
    ).decode()}


def _settle_and_respond(
    result: dict[str, Any], request_id: str, facilitator, payment_payload,
    requirements_dict, *, replayed: bool = False,
):
    """Attempt settlement for delivered work and answer accordingly.

    Three outcomes, and the middle one is why this is not a boolean:

    * settled — 200 with the deliverable.
    * indeterminate — the facilitator never answered, so the funds may have
      moved. The buyer gets the work and is told the settlement is unresolved;
      withholding it is the one outcome that is certainly wrong, because we may
      already hold their money.
    * failed — the facilitator answered no. 402, no delivery, nothing owed.
    """
    settlement = facilitator.settle(payment_payload, requirements_dict)
    outcome = settlement.outcome
    ledger.record_settlement(
        request_id,
        outcome=outcome,
        transaction=settlement.transaction,
        network=settlement.network,
        payer=settlement.payer,
        reason=settlement.error_reason,
    )
    payment = {"settled": settlement.success, **settlement.to_dict()}
    if replayed:
        payment["replayed"] = True

    if outcome == "failed":
        return JSONResponse(status_code=402, content=error_envelope(
            ErrorCode.SETTLEMENT_FAILED,
            settlement.error_reason,
            request_id=request_id,
        ))

    result = dict(result, payment=payment)
    return JSONResponse(
        status_code=200, content=result,
        headers=_payment_response_header(settlement.to_dict()),
    )


def _resubmitted_authorization(claim, cfg, facilitator, payment_payload, requirements_dict):
    """Answer a payment authorization this instance has already admitted.

    Burning the nonce and returning 409 — the previous behaviour — charged a
    buyer whose connection dropped after settlement and left them with an
    authorization that is single-use on chain, so they could not even re-sign
    it. What they get now depends on what state their request reached.
    """
    reason = claim.reason or "payment_nonce_rejected"
    if reason == "replay_store_unavailable":
        # Fail closed: an unusable guard must not become no guard.
        return JSONResponse(status_code=503, content=error_envelope(
            ErrorCode.REPLAY_PROTECTION_UNAVAILABLE, reason,
        ))
    existing = claim.existing
    if existing is None:
        return JSONResponse(status_code=409, content=error_envelope(
            reason,
            "This payment authorization cannot be admitted. Request a "
            "fresh 402 challenge and sign a new authorization.",
        ))

    if existing.state == NonceState.CLAIMED:
        # The first request is still in flight (or died mid-work). Doing the
        # work again is exactly what the claim exists to prevent.
        return JSONResponse(status_code=409, content=error_envelope(
            ErrorCode.PAYMENT_AUTHORIZATION_IN_PROGRESS,
            "A request against this authorization is already in progress.",
            request_id=existing.request_id,
        ))

    if existing.state == NonceState.ABANDONED:
        return JSONResponse(status_code=409, content=error_envelope(
            ErrorCode.PAYMENT_NONCE_ALREADY_SPENT,
            "The earlier request against this authorization failed on our "
            "side and was not billed. Request a fresh 402 challenge and sign "
            "a new authorization.",
            request_id=existing.request_id,
        ))

    stored = ledger.deliverable(existing.request_id)
    if stored is None:
        return JSONResponse(status_code=409, content=error_envelope(
            ErrorCode.PAYMENT_NONCE_ALREADY_SPENT,
            "This authorization was admitted but its deliverable is no longer "
            "retrievable. Request a fresh 402 challenge.",
            request_id=existing.request_id,
        ))

    if existing.state in REDELIVERABLE_STATES:
        # Already settled, or settled-unknown. Re-settling would present an
        # authorization the chain has burned; deliver what was bought instead.
        attempts = ledger.settlements(existing.request_id)
        last = attempts[-1] if attempts else {}
        payment = {
            "settled": existing.state == NonceState.SETTLED,
            "state": existing.state,
            "transaction": last.get("transaction"),
            "network": last.get("network"),
            "payer": last.get("payer"),
            "error_reason": last.get("reason"),
            "replayed": True,
        }
        return JSONResponse(
            status_code=200, content=dict(stored, payment=payment),
            headers=_payment_response_header(payment),
        )

    # delivered (settlement never recorded) or settlement_failed: the work is
    # done and unpaid, so retry settlement rather than redo the retrieval.
    return _settle_and_respond(
        stored, existing.request_id, facilitator, payment_payload,
        requirements_dict, replayed=True,
    )


@app.post(RESOURCE_PATH)
def research(req: ResearchRequest, request: Request):
    cfg = get_payment_config()
    payment_payload: dict[str, Any] | None = None
    requirements_dict: dict[str, Any] | None = None
    facilitator = None
    deadline: Deadline | None = None
    # Allocated here, not inside the pipeline, so the authorization claim, the
    # custody receipt, the ledger and the response all name the same request
    # (defect R6: `claim` accepted a request_id no caller ever passed).
    request_id = str(uuid.uuid4())

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
            return _challenge(cfg)

        payment_payload = decode_payment_header(header)
        if payment_payload is None:
            return _challenge(cfg, "X-PAYMENT header is not valid base64-encoded JSON")

        facilitator = get_facilitator(cfg.facilitator, live=True)
        verification = facilitator.verify(payment_payload, requirements_dict)
        if not verification.is_valid:
            reason = verification.invalid_reason or "payment_invalid"
            # Facilitator outages fail closed as 503 so buyers retry rather
            # than treating the refusal as a permanent payment rejection.
            if reason.startswith(VERIFICATION_OUTAGE_PREFIXES):
                return JSONResponse(status_code=503, content=error_envelope(
                    ErrorCode.PAYMENT_VERIFICATION_UNAVAILABLE, reason,
                ))
            return _challenge(cfg, reason)

        # Budget the work against the authorization that pays for it. Doing
        # this before the claim means an authorization too short to finish
        # costs the buyer nothing: no work, no burned nonce.
        try:
            deadline = Deadline.for_authorization(
                valid_before=_authorization_valid_before(payment_payload),
                max_work_seconds=MAX_WORK_SECONDS,
            )
        except DeadlineTooShort as exc:
            return _challenge(cfg, f"authorization window too short: {exc}")

        # Claim the authorization after the facilitator accepts it and BEFORE
        # any retrieval pass, so a resubmitted header cannot make us do the
        # work a second time. The claim is never released — the authorization
        # stays live on chain — but it is no longer a dead end: see
        # `_resubmitted_authorization` for what a replay is answered with.
        claim = ledger.claim(
            extract_nonce(payment_payload), request_id,
            network=requirements_dict.get("network"),
            asset=requirements_dict.get("asset"),
            amount=requirements_dict.get("maxAmountRequired"),
            pay_to=requirements_dict.get("payTo"),
            payer=verification.payer,
            price=cfg.price,
        )
        if not claim.claimed:
            return _resubmitted_authorization(
                claim, cfg, facilitator, payment_payload, requirements_dict,
            )

    result = run_research(req.query, max_results=req.max_results, request_id=request_id)

    # The window may have closed while we worked. Settling now would present an
    # expired authorization; the buyer is not charged and is told to retry with
    # a fresh one, which is the honest outcome for our own slowness.
    if deadline is not None and deadline.expired():
        result["billable"] = False
        result["status"] = "unavailable"
        result["refusal_reason"] = "retrieval_unavailable"
        result["error"] = ErrorCode.DEADLINE_EXCEEDED.value
        result["payment"] = {"settled": False, "reason": "deadline_exceeded_before_settlement"}
        ledger.record_delivery(
            request_id, status=result["status"], billable=False,
            custody_root=result.get("custody_root"), query=req.query, response=result,
        )
        outcomes.record(result["status"], bool(result["custody_valid"]), False)
        return JSONResponse(status_code=503, content=result)

    record = store.save(result)
    result["custody_receipt"] = record
    outcomes.record(result["status"], bool(result["custody_valid"]), bool(result["billable"]))

    # Record what we produced BEFORE settlement is attempted, and fsync it. A
    # crash between the two then leaves a durable statement that we owe this
    # buyer a deliverable and may or may not have been paid — which is
    # reconcilable — rather than silence, which is not. Non-billable work
    # abandons the authorization, so the ledger refuses to settle it.
    if cfg.require_payment:
        ledger.record_delivery(
            request_id, status=result["status"], billable=bool(result["billable"]),
            custody_root=result.get("custody_root"), query=req.query, response=result,
        )

    # Retrieval failures are ours, not the buyer's: never settle for them.
    if result["status"] == "unavailable":
        result["payment"] = {"settled": False, "reason": "not_billable_retrieval_unavailable"}
        # The registry code is additive: the full research body stays because
        # the unavailability report is itself the deliverable here.
        result["error"] = ErrorCode.RETRIEVAL_UNAVAILABLE.value
        return JSONResponse(status_code=503, content=result)

    if cfg.require_payment and facilitator is not None:
        return _settle_and_respond(
            result, request_id, facilitator, payment_payload, requirements_dict,
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
