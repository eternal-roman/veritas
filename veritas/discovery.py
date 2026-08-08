"""Agent-readable discovery index, served at /llms.txt.

The content lives here as code so it ships in the wheel and is served by the
running service; the repo-root `llms.txt` is a rendering of this constant and
a test keeps the two identical (the same pattern that keeps CONSTITUTION.md
in sync with veritas/constitution.py). Paths listed here are checked against
the live app by tests — this index is not allowed to advertise endpoints that
do not exist.
"""

from __future__ import annotations

LLMS_TXT = """\
# Veritas Research

Evidence-grounded research service for agents: hash-chained custody, Bayesian
belief updating, explicit refusal, and x402 payment. The service separates
"no evidence exists" from "I could not look" and never bills for its own
failure.

## Endpoints

- /.well-known/x402: discovery document (payment requirements, links to every surface below)
- /v1/identity: identity document with stable content hash
- /v1/constitution: the venue constitution — norms with enforcement pointers or an explicit aspirational marker
- /v1/research: POST — the paid product; returns 402 with an accepts array in live mode, retry with an X-PAYMENT header or spend prepaid credits via X-VERITAS-SESSION
- /v1/notarize: POST — observe-once evidence notary for a URL; same payment gates as research (X-PAYMENT or X-VERITAS-SESSION); stores evidence text with a retention class; unavailable is non-billable
- /v1/siwx/challenge: POST — issue a SIWx challenge for credit-session establishment
- /v1/siwx/verify: POST — verify SIWx signature and receive an X-VERITAS-SESSION token
- /v1/credits: GET — prepaid credit balance for the SIWx session
- /v1/credits/topup: POST — settle one x402 payment and grant credits (live mode only; free mode refuses)
- /v1/verify: POST — re-check a published content_hash against content you supply (convenience; not origin re-fetch — see P7)
- /v1/attestations/verify: POST — free check of an N1.1 EIP-191 EvidenceRecord attestation (bound fields + signature; not on-chain)
- /v1/receipts/{request_id}: durable custody receipt
- /v1/trust: behaviour-derived trust score; reports UNPROVEN below 10 recorded outcomes
- /v1/schema: the wire contract as JSON Schema
- /v1/errors: registered error codes with status and retriability
- /openapi.json: OpenAPI description of this API
- /health: liveness plus payment mode (never rate limited)
- /readyz: readiness — 503 when the process is alive but cannot serve

## Install and run

pip install "veritas-research @ git+https://github.com/eternal-roman/veritas"
veritas-server

## Source and norms

Repository: https://github.com/eternal-roman/veritas
Constitution rendering: CONSTITUTION.md — venue architecture: ECOSYSTEM.md
"""
