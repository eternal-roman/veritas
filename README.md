# Veritas

**A self-hosted agent-to-agent seller of prediction-market books.**
It pulls public [Kalshi](https://kalshi.com) and [Polymarket](https://polymarket.com)
prices, stores the latest snapshot per market as hash-chained evidence, and
sells that catalog pull over [x402](https://x402.org). A snapshot is a price
at a time — not a verdict, not a forecast, not a truth claim.

There is no research Q&A product. `POST /v1/research` is 410.

[![CI](https://github.com/eternal-roman/veritas/actions/workflows/ci.yml/badge.svg)](https://github.com/eternal-roman/veritas/actions/workflows/ci.yml)
[![CodeQL](https://github.com/eternal-roman/veritas/actions/workflows/codeql.yml/badge.svg)](https://github.com/eternal-roman/veritas/actions/workflows/codeql.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![x402](https://img.shields.io/badge/payments-x402-8A2BE2.svg)](https://x402.org)

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
Enroll creates a USDC-capable wallet and a wallet-signed identity card; it
does not fund the wallet or list the service.

## What you actually get

| Surface | What it does | Paid? |
|---------|--------------|-------|
| `GET /v1/signals` | Latest stored snapshot per market. Optional `q` searches the store | Free |
| `POST /v1/signals` | Pull Kalshi / Polymarket now, persist, return arithmetic on the books | Yes, in live mode ($0.01 x402 or credits) |
| `GET /v1/signals/history` | Newest-first time series for one venue market | Free |
| `POST /v1/notarize` | Observe a URL once and store the body under a content hash | Same payment gates |
| `veritas-agent pull-signals` | Fetch another agent's catalog over identity-pinned TLS (no public CA) | Peer’s price, if any |

A dead venue is `unavailable` (not billed). A search miss is an empty list,
not a dump of the open book. Catalog pull does not auto-attach a warranty.

## Core guarantee

| Status | Meaning | Billable |
|--------|---------|----------|
| `completed` | The pull or observe finished; every published hash is in the response | Yes |
| `refused` | Venues or origin were reachable; nothing matched | Yes |
| `unavailable` | The fetch failed — we did not observe an absence | **No** |

A seller that reports “empty catalog” when Kalshi or Polymarket could not be
reached is lying. Veritas never bills its own outage.

## Why an agent would choose this

**Check the work without trusting us.** Re-run `veritas.custody.verify_chain_records`
on the delivered chain — local, on bytes already in hand.

`POST /v1/verify` with **`url` + `content_hash`** (or a receipt `request_id`)
re-fetches the origin through the notary and compares the extracted body hash.
Legacy `content` + `content_hash` is `binding: caller_supplied` — arithmetic,
not independent verification. A later re-fetch may diverge if the page
changed; that is mismatch, not fraud proof.

**Rules we can be held to.** The [venue constitution](CONSTITUTION.md) marks
each article enforced or aspirational; a test rejects anything in between.
`/v1/trust` scores independently verified audits; GET without those records
is UNPROVEN. Warranty bonds that carry an EIP-3009 lock are collectable via
`settle_forfeit` (G12); omitting a lock stays `signed_commitment_not_escrow`.
Mainnet collect is unproven.

**No human on the adopt path.** `/.well-known/x402` reaches every surface;
`/v1/schema` and `/v1/errors` are the contract; payment is x402. `veritas-agent
up` provisions config and wallet and serves. Public TLS is the operator's
(see `docs/deploy/PUBLIC_HOST.md`). Two agents on a LAN connect with
`--allow-local` and pin the presented cert to the peer card.

## Also in the wheel

- **x402** — real facilitator verify/settle, fail-closed; replay returns the paid deliverable, never a second pass
- **Durable ledger** (`veritas/ledger.py`) — authorize → fsync delivery → settle; no reply is `indeterminate`
- **Diligence** (`veritas-diligence <url>`) — 402 must match advertised payee/network/asset/price. `0` pass / `1` fail / `2` unverifiable. Pass ≠ will deliver
- **Survival records** (`veritas-audit`) — third-party `confirmed` / `diverged` / `unobserved`
- **Standalone verifier** (`veritas-verify receipt.json`) — one file, zero deps
- **Falsifiable commerce** (`veritas/warranty.py`, `veritas/escrow.py`) — seller-authored predicates and optional EIP-3009 locks. Not a vault contract

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

The PyPI/distribution name is still `veritas-research`. That is the package
name, not the product.

## Quick start (free mode)

```bash
veritas-agent up                 # config + wallet + serve
veritas-ops signals-ingest       # pull a watchlist into the local store
veritas-ops revenue              # JSON
veritas-ops reconcile            # records only, not the chain
veritas-server                   # VERITAS_HOST / VERITAS_PORT to bind
```

```python
from veritas.signals import SignalStore
SignalStore().list()  # latest snapshot per market; prices, not verdicts
```

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
| `POST /v1/signals` | Catalog pull (402 in live mode) |
| `GET /v1/signals` | Latest snapshot per market; `q` searches the store (free) |
| `GET /v1/signals/history` | Newest-first history of one venue market |
| `POST /v1/research` | Removed (410). Use `POST /v1/signals` |
| `POST /v1/notarize` | Observe-once URL notary; same payment gates |
| `POST /v1/verify` | Origin re-fetch (`url`+`content_hash` or `request_id`) |
| `GET /v1/receipts/{id}` | Durable custody receipt (query stored as hash only) |
| `GET /v1/evidence/{hash}` | Stored excerpt for a published content hash |
| `POST /v1/escrow` · `GET /v1/escrow/{id}` | Lock an EIP-3009 authorization; GET omits the signature |
| `POST /v1/escrow/{id}/release` | Loopback-only; never submits |
| `POST /v1/escrow/{id}/forfeit` | Re-run the challenge; submit only if it fired (live facilitator) |
| `GET /v1/trust` | UNPROVEN from the operator log |
| `POST /v1/trust` | Score caller-supplied verified audit records |
| `GET /v1/schema` · `/v1/errors` · `/v1/constitution` | Contract, errors, norms |
| `GET /v1/identity` | ERC-8004-style identity |
| `GET /v1/peer` | This node’s A2A card (not an address book) |
| `GET /v1/hooks` | Every surface (HTTP, MCP, CLI exits, headers, stores); no push |
| `GET /v1/operator` | Payment config + local account |
| `POST /v1/operator/enroll` | Loopback-only enroll (`veritas-agent enroll`) |
| `GET /ui` | Human viewer of the same snapshot; enroll form is loopback-only |
| `GET /.well-known/x402` | Discovery + payment requirements |

Local MCP: register `veritas-mcp` as an stdio server (free-mode catalog; paid
access is HTTP).

## Testing

```bash
pip install -e ".[signing,dev]"
python -m pytest tests/ -q
python -m veritas.evaluations.catalog
ruff check veritas tests
```

## Known limitations

- **This is a book store, not a trading desk and not an oracle.** Snapshots
  attest advertised prices. They do not settle markets or say who won.
- **There is no public seller URL.** `docs/deploy/PUBLIC_HOST.md` is the
  operator runbook. This repository does not claim a live host.
- **Settlement is operator-run testnet only.** Count and evidence:
  `docs/program/fable/settlement/` and `docs/program/STATE.md`. Mainnet: none.
  Unsolicited buyers: none.
- **Shared state is opt-in.** Unset `VERITAS_DATABASE_URL` keeps per-instance
  SQLite under `$VERITAS_RUNTIME_DIR` (default
  `~/.local/share/veritas/runtime`; `veritas-agent` uses `{base-dir}/runtime`).
  Multi-host HA is the operator's Postgres.
- **Solana is not payable.** Recognised for aliasing, excluded from advertised networks.
- **Wallet commitments hide; they are not zero-knowledge.** Public verify needs the reveal.
- **Self-provisioned wallets are owner-only on POSIX only.** On Windows / no-mode filesystems
  a `WalletPermissionWarning` names the unprotected file — treat as development-only.

## What we removed, and why

An audit found claims the served path did not support. The claims and the
code went together:

- **Research Q&A engine.** Snippet retrieval, lexical synthesis, and a
  Bayesian posterior that could not refuse. Markets already price claims;
  the catalog is the product. `POST /v1/research` is 410 `product_removed`.
- **Metasearch tier.** Scraped Google/Bing/Yandex through a shuffling
  aggregator while labelling every result `duckduckgo`.
- **Offline corpus on the live path.** Fixture text carried real third-party
  URLs and a hash. It never appeared at those URLs.

See `AGENTS.md` (how to work here, including live-settlement field notes) and
`docs/design/` (prototype notes).

## Layout

```
veritas/               # installable package (the wheel)
  signals.py           # catalog pull, store, analyze
  notary/              # URL observe
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
