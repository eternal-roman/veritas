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
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from veritas import __version__
from veritas.constitution import build_constitution
from veritas.custody import CustodyStore
from veritas.facilitator import get_facilitator
from veritas.hashing import verify_content_hash
from veritas.identity import build_identity
from veritas.payment_config import get_payment_config
from veritas.pipeline import run_research
from veritas.trust import OutcomeLog, score_service
from veritas.x402 import PriceError, build_402_challenge, build_payment_requirements

app = FastAPI(title="Veritas Research", version=__version__)

RESOURCE_PATH = "/v1/research"
store = CustodyStore()
outcomes = OutcomeLog()


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
        return JSONResponse(status_code=503, content={
            "error": "payment_misconfigured",
            "detail": cfg.config_errors,
        })

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
            return JSONResponse(status_code=500, content={
                "error": "payment_misconfigured", "detail": str(exc),
            })
        requirements_dict = requirements.to_dict()

        header = request.headers.get("X-PAYMENT")
        if not header:
            return JSONResponse(
                status_code=402,
                content=build_402_challenge(cfg.pay_to, cfg.network, cfg.price, RESOURCE_PATH),
            )

        payment_payload = _decode_payment_header(header)
        if payment_payload is None:
            return JSONResponse(status_code=402, content=build_402_challenge(
                cfg.pay_to, cfg.network, cfg.price, RESOURCE_PATH,
                error="X-PAYMENT header is not valid base64-encoded JSON",
            ))

        facilitator = get_facilitator(cfg.facilitator, live=True)
        verification = facilitator.verify(payment_payload, requirements_dict)
        if not verification.is_valid:
            reason = verification.invalid_reason or "payment_invalid"
            # Facilitator outages fail closed as 503 so buyers retry rather
            # than treating the refusal as a permanent payment rejection.
            if reason.startswith(("facilitator_unreachable", "facilitator_http", "facilitator_bad_response")):
                return JSONResponse(status_code=503, content={
                    "error": "payment_verification_unavailable", "detail": reason,
                })
            return JSONResponse(status_code=402, content=build_402_challenge(
                cfg.pay_to, cfg.network, cfg.price, RESOURCE_PATH, error=reason,
            ))

    result = run_research(req.query, max_results=req.max_results)
    record = store.save(result)
    result["custody_receipt"] = record
    outcomes.record(result["status"], bool(result["custody_valid"]), bool(result["billable"]))

    # Retrieval failures are ours, not the buyer's: never settle for them.
    if result["status"] == "unavailable":
        result["payment"] = {"settled": False, "reason": "not_billable_retrieval_unavailable"}
        return JSONResponse(status_code=503, content=result)

    if cfg.require_payment and facilitator is not None:
        settlement = facilitator.settle(payment_payload, requirements_dict)
        result["payment"] = {"settled": settlement.success, **settlement.to_dict()}
        if not settlement.success:
            return JSONResponse(status_code=402, content={
                "error": "settlement_failed",
                "detail": settlement.error_reason,
                "request_id": result["request_id"],
            })
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
        return JSONResponse(status_code=404, content={"error": "receipt_not_found",
                                                      "request_id": request_id})
    return record


@app.get("/v1/trust")
def trust():
    s = score_service()
    return s.to_dict()


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
