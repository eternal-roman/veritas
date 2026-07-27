# Veritas Research

Evidence-grounded research service for agents: hash-chained custody, Bayesian
belief updating, explicit refusal, and x402 payment.

## Core guarantee

Veritas distinguishes three outcomes, and the distinction is the product:

| Status | Meaning | Billable |
|--------|---------|----------|
| `completed` | Evidence was found; every claim cites a hash present in the response | Yes |
| `refused` | Sources were reachable and genuinely had nothing relevant | Yes |
| `unavailable` | Retrieval itself failed — we did not observe an absence of evidence, so we do not claim one | **No** |

A service that reports "no evidence exists" when it simply could not reach the
network is not a research service. Veritas never bills for its own outage.

## Capabilities

- **Evidence-first research** with content hashing and an append-only custody ledger
- **Bayesian belief updating** with correlated-source damping (repeat sources from
  one provider are not treated as independent observations)
- **First-class refusal**, measured by discrimination rather than raw refusal rate
- **Zero-key retrieval** (Wikipedia + DuckDuckGo), with provider errors surfaced
- **x402 payment** with real facilitator `verify` / `settle` and fail-closed gating
- **Hiding wallet commitments** so a broadcast offer does not leak the payout address
- **Signed JIT Disposable Packets** with enforced expiry and verified chain linkage

## Quick start (free mode)

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# or use the library
python -c "from veritas.pipeline import run_research; print(run_research('What is x402?'))"
```

Offline / no network:

```python
from veritas.pipeline import run_research
run_research("What is x402?", allow_network=False)   # uses the labelled offline corpus
```

## Live payments

```bash
export VERITAS_PAY_TO=0xYourWallet          # validated as a real EVM address
export VERITAS_FACILITATOR=https://pay.openfacilitator.io
export VERITAS_REQUIRE_PAYMENT=true
export VERITAS_NETWORK=eip155:8453
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

If any of these is invalid the service reports `mode: misconfigured` and returns
503 — it will not quietly serve paid research for free.

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /v1/research` | Run research (402-gated in live mode) |
| `POST /v1/verify` | Independently re-check a published evidence hash |
| `GET /v1/receipts/{id}` | Retrieve a stored custody receipt after the call |
| `GET /v1/trust` | Behaviour-derived trust score (`UNPROVEN` until enough data) |
| `GET /v1/identity` | ERC-8004 style identity document |
| `GET /.well-known/x402` | Discovery + payment requirements |

## Testing

```bash
pip install pytest httpx
python -m pytest tests/ -q
python -m evaluations.harness
```

## Known limitations

Stated plainly, because a truth-telling service should not overstate itself:

- **Retrieval quality is thin.** Wikipedia + DuckDuckGo snippets are not
  competitive with a paid search/extraction stack for general queries.
- **Claims are extractive, not synthesised.** A "claim" is a grounded excerpt,
  not an answer composed across sources.
- **The calibrator is untrained.** It reports `passthrough_untrained` and needs
  labelled outcomes via `record_feedback` before it adjusts anything.
- **The harness runs on a 3-document offline corpus.** Its perfect scores
  demonstrate the invariants hold; they are not a quality benchmark.
- **Solana is not payable.** It is recognised for alias resolution but excluded
  from advertised networks because SPL settlement is not implemented.
- **Wallet commitments are hiding, not zero-knowledge.** Public verification of
  the opening requires the reveal at settlement.

See `LIVE_PAYMENTS.md`, `JIT_PACKET.md`, `ZK_WALLET.md`, `WORKFLOW.md`, `ANALYSIS.md`.

## Layout

```
veritas/           # engine: retrieval, pipeline, custody, hashing, bayesian, x402, facilitator
autonomous/        # agent-native layer: zero-key retrieval, JIT packets, wallet commitments, bootstrap
app/               # FastAPI surface
evaluations/       # harness + CI quality gates
tests/
```

## License
Apache-2.0
