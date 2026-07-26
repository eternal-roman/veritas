"""FastAPI surface with live/free payment configuration."""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import os

from veritas.pipeline import run_research
from veritas.trust import score_service
from veritas.identity import build_identity
from veritas.payment_config import get_payment_config

app = FastAPI(title="Veritas Research", version="0.4.0")

class ResearchRequest(BaseModel):
    query: str
    max_age_seconds: Optional[int] = 604800

@app.get("/health")
def health():
    cfg = get_payment_config()
    return {"status": "ok", "service": "veritas", "payment_mode": cfg.mode, "live_ready": cfg.is_live_ready()}

@app.get("/v1/payment-config")
def payment_config():
    return get_payment_config().as_dict()

@app.post("/v1/research")
def research(req: ResearchRequest, request: Request):
    cfg = get_payment_config()

    # Live mode: require payment header (simplified gate; full x402 middleware can replace this)
    if cfg.require_payment:
        payment_header = request.headers.get("X-PAYMENT") or request.headers.get("x-payment")
        if not payment_header:
            # Return 402-style challenge
            return JSONResponse(
                status_code=402,
                content={
                    "error": "Payment Required",
                    "x402Version": 1,
                    "accepts": [{
                        "scheme": "exact",
                        "network": cfg.network,
                        "maxAmountRequired": cfg.price,
                        "payTo": cfg.pay_to,
                        "facilitator": cfg.facilitator,
                    }],
                    "description": "High-assurance research via Veritas",
                },
            )

    result = run_research(req.query)
    result["payment_mode"] = cfg.mode
    return result

@app.get("/v1/trust")
def trust():
    s = score_service()
    return {"overall": s.overall, "recommendation": s.recommendation, "flags": s.flags}

@app.get("/v1/identity")
def identity():
    return build_identity()

@app.get("/.well-known/x402")
def well_known():
    cfg = get_payment_config()
    return {
        "version": 1,
        "resources": ["/v1/research"],
        "payTo": cfg.pay_to if cfg.is_live_ready() else None,
        "facilitator": cfg.facilitator,
        "network": cfg.network,
        "price": cfg.price,
        "mode": cfg.mode,
    }
