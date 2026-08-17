# Veritas

**A multi-agent commerce venue: Kalshi/Polymarket catalog, x402 settlement, and escrowed bonds. Catalog pull is the sold observe SKU. It is not a truth arbiter, and it never charges you for its own failure.**

[![CI](https://github.com/eternal-roman/veritas/actions/workflows/ci.yml/badge.svg)](https://github.com/eternal-roman/veritas/actions/workflows/ci.yml)
[![CodeQL](https://github.com/eternal-roman/veritas/actions/workflows/codeql.yml/badge.svg)](https://github.com/eternal-roman/veritas/actions/workflows/codeql.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![x402](https://img.shields.io/badge/payments-x402-8A2BE2.svg)](https://x402.org)

Markets already price claims. Veritas stores those prices as evidence, with
hash-chained custody a caller can verify, and settles agent-to-agent over
[x402](https://x402.org). It is not an arbiter of truth.

**Status: working software, unproven economics.** Invariants below are tested
and CI-gated. On-chain settlement exists only in operator-run testnet arcs
against the real facilitator (count and evidence:
`docs/program/fable/settlement/`). No unsolicited buyer has paid. There is no
public seller URL. See [Known limitations](#known-limitations) and [ROADMAP.md](ROADMAP.md).

```bash
pip install "veritas-research[signing] @ git+https://github.com/eternal-roman/veritas"
veritas-agent adopt --id self --interests signals,verify
veritas-agent up
```

A stranger agent with only this repository fetches
[`adopt.json`](https://raw.githubusercontent.com/eternal-roman/veritas/main/adopt.json).
There is no public seller URL. Enroll creates a USDC-capable wallet and a
wallet-signed identity card; it does not fund the wallet or list the service.

## Core guarantee

The distinction is the product:

| Status | Meaning | Billable |
|--------|---------|----------|
| `completed` | Evidence found; every claim cites a hash in the response | Yes |
| `refused` | Sources reachable; nothing relevant | Yes |
| `unavailable` | Retrieval failed — we did not observe an absence | **No** |

A service that reports "no evidence exists" when it could not reach the
network is not a research service. Veritas never bills its own outage.

## Why an agent would choose this

**Check the work without trusting us.** Re-run `veritas.custody.verify_chain_records`
on the delivered chain — local, on bytes already in hand.

`POST /v1/verify` with **`url` + `content_hash`** (or a receipt `request_id`)
re-fetches the origin through the notary and compares the extracted body hash
(P7 origin binding). Legacy `content` + `content_hash` is `binding: caller_supplied`
— arithmetic, not independent verification. A later re-fetch may diverge if
the page changed; that is mismatch, not fraud proof. Nothing here is on-chain
settlement.

**Rules we can be held to.** The [venue constitution](CONSTITUTION.md) marks
each article enforced or aspirational; a test rejects anything in between.
Open gaps are listed there. `/v1/trust` scores independently verified
audits; GET without those records is UNPROVEN. Warranty bonds that carry
an EIP-3009 lock are collectable via `settle_forfeit` (G12); omitting a
lock stays `signed_commitment_not_escrow`. Research does not auto-attach
a warranty. Mainnet collect is unproven.

**No human on the adopt path.** `/.well-known/x402` reaches every surface;
`/v1/schema` and `/v1/errors` are the contract; payment is x402. `veritas-agent
up` provisions config and wallet and serves. Public TLS is the operator's
(see `docs/deploy/PUBLIC_HOST.md`).

## Capabilities

- **Prediction-market signals** (`veritas/signals.py`) — public Kalshi and Polymarket book snapshots stored through the evidence channel. `POST /v1/signals` returns arithmetic analysis (min/max/mean, venue disagreement). `GET /v1/signals/history` is the time series. The snapshot attests a price at a time, not that an event happened.
- **Evidence-first observe** — custody chain delivered with the response. Research does not auto-attach a warranty.
- **Countable support** — independent domains, providers, verdict (not a confidence score)
- **First-class refusal** — below-threshold evidence is `irrelevant_evidence`, not an answer
- **Per-source licence and attribution** — unknown stays unknown
- **Tiered retrieval** — Wikipedia official extracts; keyed Serper when configured (snippets, then observed); DDG Instant Answer otherwise. Search hits re-observed through `notary.observe` on the served path. Errors surfaced.
- **x402** — real facilitator verify/settle, fail-closed; replay returns the paid deliverable, never a second pass
- **Durable ledger** (`veritas/ledger.py`) — authorize → fsync delivery → settle; no reply is `indeterminate`
- **Survival records** (`veritas-audit`) — third-party `confirmed` / `diverged` / `unobserved`; counts per auditor key, self-audits excluded. Diligence vets documents; survival vets history. Survival reports are `surviving` only against an auditor publication; `/v1/trust` is independent-audit sourced
- **Falsifiable commerce W0/W1** (`veritas/warranty.py`, `veritas/escrow.py`) — seller-authored D0 predicates, bonded stake, challenge window; `fired` / `not_fired` / `undecidable`; no predicate → class `U`. An EIP-3009 lock is collectable via `settle_forfeit`; omitting it stays `signed_commitment_not_escrow`. Not a vault contract. See `docs/program/FALSIFIABLE_COMMERCE.md`
- **Diligence** (`veritas-diligence <url>`) — 402 must match advertised payee/network/asset/price; L1 articles must name enforcement; a seller claiming no gaps fails. `0` pass / `1` fail / `2` unverifiable. SSRF-guarded. None of this proves delivery
- **Standalone verifier** (`veritas-verify receipt.json`) — one file, zero deps, imports nothing from `veritas`. Differential test vs the engine. Consistent records ≠ we contacted the named URLs

## Install

```bash
pip install "veritas-research @ git+https://github.com/eternal-roman/veritas"

# clone (not on PyPI; release workflow exists, PyPI project is not configured):
pip install -e ".[signing,dev]"

# container binds 0.0.0.0; bare console script binds 127.0.0.1
docker build -t veritas-research . && docker run -p 8000:8000 veritas-research
```

Python >= 3.10, pip >= 24.1. Wheel is one package (`veritas`) plus
`veritas-server` / `veritas-agent`. Smoke-test:

```bash
python -c "from veritas.signals import METHOD; print(METHOD)"
```

## Quick start (free mode)

```bash
veritas-agent up                 # config + wallet + serve
veritas-ops revenue              # JSON
veritas-ops reconcile            # records only, not the chain
veritas-server                   # VERITAS_HOST / VERITAS_PORT to bind
```

```python
from veritas.signals import SignalStore
SignalStore().list()  # latest snapshot per market; prices, not verdicts
```

## Catalog

`GET /v1/signals` is the latest snapshot per market. `POST /v1/signals` pulls
Kalshi and Polymarket (payment-gated in live mode). `veritas-ops signals-ingest`
pulls a watchlist. A dead venue is unavailable, not an empty book.

## Live payments

This is the config that has settled on-chain (operator-run, chain-confirmed;
`docs/program/fable/settlement/`). Base Sepolia and the x402.org facilitator
are the shipped defaults — first three lines are required:

```bash
export VERITAS_PAY_TO=0xYourWallet
export VERITAS_REQUIRE_PAYMENT=true
export VERITAS_PUBLIC_URL=https://your.host
export VERITAS_NETWORK=eip155:84532             # default
export VERITAS_FACILITATOR=https://x402.org/facilitator
veritas-server
```

Mainnet (`eip155:8453`) is unproven. `veritas-agent` refuses `--paid` on
mainnet without `--i-understand-this-is-real-money`. Invalid config →
`mode: misconfigured` → 503; it will not quietly serve paid work for free.

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /v1/research` | Removed (410). Use `POST /v1/signals` |
| `POST /v1/signals` | Catalog pull (402 in live mode); GET is free |
| `POST /v1/notarize` | Observe-once URL notary; same payment gates |
| `POST /v1/verify` | Origin re-fetch (`url`+`content_hash` or `request_id`) |
| `GET /v1/receipts/{id}` | Durable custody receipt (research questions redacted) |
| `GET /v1/evidence/{hash}` | Stored excerpt for a published content hash |
| `POST /v1/escrow` · `GET /v1/escrow/{id}` | Lock an EIP-3009 authorization; GET omits the signature |
| `POST /v1/escrow/{id}/release` | Loopback-only; never submits |
| `POST /v1/escrow/{id}/forfeit` | Re-run the challenge; submit only if it fired (live facilitator) |
| `GET /v1/signals` · `POST /v1/signals` | Prediction-market snapshots + arithmetic analysis (prices, not verdicts) |
| `GET /v1/signals/history` | Time-ordered snapshots of one venue market |
| `GET /v1/trust` | UNPROVEN from the operator log |
| `POST /v1/trust` | Score caller-supplied verified audit records |
| `GET /v1/schema` · `/v1/errors` · `/v1/constitution` | Contract, errors, norms |
| `GET /v1/identity` | ERC-8004-style identity |
| `GET /v1/hooks` | Every surface (HTTP, MCP, CLI exits, headers, stores); no push |
| `GET /v1/operator` | Payment config + local account |
| `POST /v1/operator/enroll` | Loopback-only enroll (`veritas-agent enroll`) |
| `GET /ui` | Human viewer of the same snapshot; enroll form is loopback-only |
| `GET /.well-known/x402` | Discovery + payment requirements |

Local MCP: register `veritas-mcp` as an stdio server (free-mode engine; paid
access is HTTP).

## Testing

```bash
pip install -e ".[signing,dev]"
python -m pytest tests/ -q
python -m veritas.evaluations.catalog
ruff check veritas tests
```

## Known limitations

- **Retrieval is observe-then-excerpt, not a paid search stack.** Wikipedia
  extracts are official API plaintext. Serper/DDG remain snippets until
  `notary.observe` replaces the body.
- **There is no public seller URL.** `docs/deploy/PUBLIC_HOST.md` is the
  operator runbook. This repository does not claim a live host.
- **Settlement is operator-run testnet only.** Count and evidence:
  `docs/program/fable/settlement/` and `docs/program/STATE.md`. Mainnet: none.
  Unsolicited buyers: none.
- **Synthesis is lexical-NLI gated, not LLM-grade.** Extractive claims remain
  the default; a synthesized claim emits only when its tokens appear in the
  cited excerpts.
- **Shared state is opt-in.** Unset `VERITAS_DATABASE_URL` keeps per-instance
  SQLite under `$VERITAS_RUNTIME_DIR` (default
  `~/.local/share/veritas/runtime`; `veritas-agent` uses `{base-dir}/runtime`).
  Multi-host HA is the operator's Postgres.
- **Calibrator is untrained and unused.** Reports `passthrough_untrained`.
- **Harness is a 3-document offline corpus.** Perfect scores prove invariants, not quality.
- **Solana is not payable.** Recognised for aliasing, excluded from advertised networks.
- **Wallet commitments hide; they are not zero-knowledge.** Public verify needs the reveal.
- **Self-provisioned wallets are owner-only on POSIX only.** On Windows / no-mode filesystems
  a `WalletPermissionWarning` names the unprotected file — treat as development-only.

## What we removed, and why

An audit found claims the served path did not support. The claims and the
code went together:

- **Bayesian posterior and per-claim confidence.** The hypothesis was the raw
  query (a question has no truth value); constants were typed; the posterior
  could only rise, so `low_confidence` refusal was unreachable; two
  contradictions both pushed it up. Confidence was list position.
  `veritas/support.py` publishes recomputable counts instead.
- **Metasearch tier.** Scraped Google/Bing/Yandex through a shuffling
  aggregator while labelling every result `duckduckgo`.
- **Offline corpus on the live path.** Fixture text carried real third-party
  URLs and a hash. It never appeared at those URLs. Corpus is now
  `veritas://fixture/*` and offline-only.

See `AGENTS.md` (how to work here, including live-settlement field notes) and
`docs/design/` (prototype notes).

## Layout

```
veritas/               # installable package (the wheel)
  signals.py           # catalog pull, store, analyze
  custody.py hashing.py schema.py
  x402.py facilitator.py payment_config.py networks.py
  server.py            # FastAPI (`veritas-server`)
  agent_account.py     # enroll / whoami / skills
  autonomous/          # wallet, bootstrap, local facilitator (G13 open)
  evaluations/         # catalog honesty + payment model
tests/                 # not in the wheel
```

## License
Apache-2.0
