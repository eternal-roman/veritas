# Veritas Research

High-assurance, agent-native research service with evidence custody, Bayesian updating, x402 payments, and zero-setup JIT transmission.

## Core Capabilities

- **Evidence-first research** with content hashing and append-only custody ledger
- **Bayesian belief updating** and first-class refusal
- **Zero-key free retrieval** (DuckDuckGo + Wikipedia) for agent-native mode
- **x402 payment** with full CAIP-2 multi-network support (free/sim + live)
- **JIT Disposable Packet (JDP)** protocol — self-describing, zero prior setup, disposable after use
- **ZK-style wallet privacy** — commitments + proof-of-knowledge instead of cleartext pay_to in offers
- **Agent bootstrap** with `human_required: false` free path

## Quick start (free / agent-native)

```bash
pip install -r requirements.txt
python -c "from veritas.pipeline import run_research; print(run_research('What is x402?'))"
# or
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Live payments

```bash
export VERITAS_PAY_TO=0xYourWallet
export VERITAS_FACILITATOR=https://pay.openfacilitator.io
export VERITAS_REQUIRE_PAYMENT=true
export VERITAS_NETWORK=eip155:8453
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

See `LIVE_PAYMENTS.md`, `JIT_PACKET.md`, `ZK_WALLET.md`, `WORKFLOW.md`, `ANALYSIS.md`.

## Layout

```
veritas/           # core engine (custody, hashing, Bayesian, pipeline, networks, payment)
autonomous/        # agent-native layer (zero-key retrieval, JIT packet, ZK wallet, bootstrap, facilitator sim)
app/               # FastAPI surface
evaluations/       # harness
tests/
```

## License
Apache-2.0
