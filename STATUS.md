# Veritas Status — Post 3x Review

## Multi-agent high-skepticism review completed

**Strengths retained**
- Append-only custody ledger
- Content hashing
- Bayesian-style updating
- Explicit refusal path
- Clean public repo

**3x improvements implemented**
- Pipeline now emits multiple claims with attached evidence hashes and sequential posterior updates
- FastAPI surface with /v1/research, /v1/trust, /v1/identity, /.well-known/x402
- Trust and identity modules integrated into the API
- Expanded structured evidence handling

**Still required for production value**
- Real multi-source retrieval (search APIs + extraction)
- Calibrated likelihood models instead of simple multipliers
- Live x402 middleware + facilitator settlement
- Public evaluation suite with citation fidelity metrics
- On-chain ERC-8004 registration

**Competitive position**
No dominant high-assurance evidenced-research service with full custody + Bayesian + refusal currently owns the niche. The opening exists only if research quality becomes real. The current package prioritizes trustworthy contracts over hallucinated answers.

## How to run
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
