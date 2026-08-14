# Veritas Research

**A research API for AI agents that refuses to guess — and never charges you
when it fails.**

[![CI](https://github.com/eternal-roman/veritas/actions/workflows/ci.yml/badge.svg)](https://github.com/eternal-roman/veritas/actions/workflows/ci.yml)
[![CodeQL](https://github.com/eternal-roman/veritas/actions/workflows/codeql.yml/badge.svg)](https://github.com/eternal-roman/veritas/actions/workflows/codeql.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![x402](https://img.shields.io/badge/payments-x402-8A2BE2.svg)](https://x402.org)

Every answer carries a hash-chained custody record the caller can verify,
per-source licence and attribution, and a status that separates *"I looked
and found nothing"* from *"I could not look."* Payment is [x402](https://x402.org):
one query, no account, no API key, no human.

**Status: working software, unproven economics.** Invariants below are tested
and CI-gated. On-chain settlement exists only in operator-run testnet arcs
against the real facilitator (count and evidence:
`docs/program/fable/settlement/`). No unsolicited buyer has paid. Retrieval is
snippet-grade. See [Known limitations](#known-limitations) and [ROADMAP.md](ROADMAP.md).

```bash
pip install "veritas-research @ git+https://github.com/eternal-roman/veritas"
veritas-agent enroll --id self --interests research,verify
veritas-agent up
```

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
Open gaps are listed there, including that `/v1/trust` is still computed by
us from our own records.

**No human on the adopt path.** `/.well-known/x402` reaches every surface;
`/v1/schema` and `/v1/errors` are the contract; payment is x402. `veritas-agent
up` provisions config and wallet and serves.

## Capabilities

- **Evidence-first research** — custody chain delivered with the response
- **Countable support** — independent domains, providers, verdict (not a confidence score)
- **First-class refusal** — below-threshold evidence is `irrelevant_evidence`, not an answer
- **Per-source licence and attribution** — unknown stays unknown
- **Tiered retrieval** — keyed Serper when configured; Wikipedia + DDG IA otherwise; errors surfaced
- **x402** — real facilitator verify/settle, fail-closed; replay returns the paid deliverable, never a second pass
- **Durable ledger** (`veritas/ledger.py`) — authorize → fsync delivery → settle; no reply is `indeterminate`
- **Survival records** (`veritas-audit`) — third-party `confirmed` / `diverged` / `unobserved`; counts per auditor key, self-audits excluded. Diligence vets documents; survival vets history. Held sets may be curated (G11); `/v1/trust` is still self-reported (G10)
- **Falsifiable commerce W0** (`veritas/warranty.py`) — seller-authored D0 predicates, bonded stake, challenge window; `fired` / `not_fired` / `undecidable`; no predicate → class `U`. Bonds are signed commitments, not escrow (G12). See `docs/program/FALSIFIABLE_COMMERCE.md`
- **Diligence** (`veritas-diligence <url>`) — 402 must match advertised payee/network/asset/price; L1 articles must name enforcement; a seller claiming no gaps fails. `0` pass / `1` fail / `2` unverifiable. SSRF-guarded. None of this proves delivery
- **Standalone verifier** (`veritas-verify receipt.json`) — one file, zero deps, imports nothing from `veritas`. Differential test vs the engine. Consistent records ≠ we contacted the named URLs
- **Privacy prototypes** — hiding-wallet commitments and JIT packets in `veritas/autonomous/`; experiments (`docs/design/`)

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
python -c "from veritas.pipeline import run_research; print(run_research('What is x402?', allow_network=False)['status'])"
```

## Quick start (free mode)

```bash
veritas-agent up                 # config + wallet + serve
veritas-ops revenue              # JSON
veritas-ops reconcile            # records only, not the chain
veritas-server                   # VERITAS_HOST / VERITAS_PORT to bind
```

```python
from veritas.pipeline import run_research
run_research("What is x402?", allow_network=False)  # labelled offline corpus
```

## Retrieval

Zero-key (Wikipedia + DuckDuckGo) needs no config. To rank a keyed provider:

```bash
export VERITAS_SERPER_API_KEY=...   # or SERPER_API_KEY
```

Keys are env config, never payload: header to the provider only, never in
responses, errors, custody, or receipts (`tests/test_providers.py`). No key →
provider not registered. A keyed outage degrades to the next tier with the
error in `retrieval.errors`.

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
| `POST /v1/research` | Research (402 in live mode) |
| `POST /v1/notarize` | Observe-once URL notary; same payment gates |
| `POST /v1/verify` | Origin re-fetch (`url`+`content_hash` or `request_id`) |
| `GET /v1/receipts/{id}` | Durable custody receipt |
| `GET /v1/trust` | Behaviour score; `UNPROVEN` until enough data |
| `GET /v1/schema` · `/v1/errors` · `/v1/constitution` | Contract, errors, norms |
| `GET /v1/identity` | ERC-8004-style identity |
| `GET /v1/hooks` | Every surface (HTTP, MCP, CLI exits, headers, stores); no push |
| `GET /.well-known/x402` | Discovery + payment requirements |

Local MCP: register `veritas-mcp` as an stdio server (free-mode engine; paid
access is HTTP).

## Testing

```bash
pip install -e ".[signing,dev]"
python -m pytest tests/ -q
python -m veritas.evaluations.harness
ruff check veritas tests
```

## Known limitations

- **Retrieval is thin.** Wikipedia and Instant Answer snippets are not a paid search stack.
- **Settlement is operator-run testnet only.** Count and evidence:
  `docs/program/fable/settlement/` and `docs/program/STATE.md`. Mainnet: none.
  Unsolicited buyers: none.
- **Claims are extractive.** Grounded excerpts, not answers composed across sources.
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
  pipeline.py          # single engine: retrieval -> relevance -> hashing -> custody
  retrieval.py custody.py hashing.py support.py schema.py
  x402.py facilitator.py payment_config.py networks.py
  server.py            # FastAPI (`veritas-server`)
  agent_account.py     # enroll / whoami / skills
  autonomous/          # zero-key retrieval, wallet, bootstrap; JIT/hiding-wallet experiments
  evaluations/         # harness + CI gates
tests/                 # not in the wheel
```

## License
Apache-2.0
