"""Minimal FastAPI surface for Veritas."""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from veritas.pipeline import run_research
from veritas.trust import score_service
from veritas.identity import build_identity

app = FastAPI(title="Veritas Research", version="0.2.0")

class ResearchRequest(BaseModel):
    query: str
    max_age_seconds: Optional[int] = 604800

@app.get("/health")
def health():
    return {"status": "ok", "service": "veritas"}

@app.post("/v1/research")
def research(req: ResearchRequest):
    return run_research(req.query)

@app.get("/v1/trust")
def trust():
    s = score_service()
    return {"overall": s.overall, "recommendation": s.recommendation, "flags": s.flags}

@app.get("/v1/identity")
def identity():
    return build_identity()

@app.get("/.well-known/x402")
def well_known():
    return {
        "version": 1,
        "resources": ["https://api.veritas.example/v1/research"],
        "mcp": "https://mcp.veritas.example",
        "identity": "/v1/identity"
    }
