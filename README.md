# Veritas Research

**A research API for AI agents that refuses to guess — and never charges you
when it fails.**

[![CI](https://github.com/eternal-roman/veritas/actions/workflows/ci.yml/badge.svg)](https://github.com/eternal-roman/veritas/actions/workflows/ci.yml)
[![CodeQL](https://github.com/eternal-roman/veritas/actions/workflows/codeql.yml/badge.svg)](https://github.com/eternal-roman/veritas/actions/workflows/codeql.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-420%20passing-brightgreen.svg)](tests/)
[![x402](https://img.shields.io/badge/payments-x402-8A2BE2.svg)](https://x402.org)

Every answer arrives with a hash-chained custody record the caller can verify
themselves, per-source licence and attribution, and a status that distinguishes
*"I looked and found nothing"* from *"I could not look."* Payment is
machine-native over [x402](https://x402.org), so an agent can buy a single
query without an account, an API key, or a human.

**Status: working software, unproven economics.** The invariants below are
tested and CI-gated. No payment has ever settled on-chain, and retrieval is
snippet-grade today. Both are stated plainly in
[Known limitations](#known-limitations) and sequenced in [ROADMAP.md](ROADMAP.md)
— we would rather you find that here than discover it later.

```bash
pip install "veritas-research @ git+https://github.com/eternal-roman/veritas"
veritas-agent up     # config + wallet + server, zero human input
```

## Core guarantee

Veritas distinguishes three outcomes, and the distinction is the product:

| Status | Meaning | Billable |
|--------|---------|----------|
| `completed` | Evidence was found; every claim cites a hash present in the response | Yes |
| `refused` | Sources were reachable and genuinely had nothing relevant | Yes |
| `unavailable` | Retrieval itself failed — we did not observe an absence of evidence, so we do not claim one | **No** |

A service that reports "no evidence exists" when it simply could not reach the
network is not a research service. Veritas never bills for its own outage.

## Why an agent would choose this

**You can check our work without trusting us.** Every response carries its own
hash-chained custody record. Run `veritas.custody.verify_chain_records` on what
you received: that check runs entirely on your side, on bytes already in your
hands, and does not route back through our goodwill.

`POST /v1/verify` with **`url` + `content_hash`** (or a **`request_id`** from a
custody receipt) re-fetches the origin through the same notary engine and
compares the extracted body hash — that is the independent product path (P7
closed for origin binding). The legacy **`content` + `content_hash`** body is
still accepted as offline arithmetic convenience and is labeled
`binding: caller_supplied`; it is not independent verification. Re-fetch at
time T2 may diverge from notarization at T1 when the page changes; that is
reported as mismatch, not fraud proof. Nothing here is an on-chain settlement.

**We wrote down the rules we can be held to.** The
[venue constitution](CONSTITUTION.md) states each norm this service commits to,
and every article either points at the test that enforces it or is explicitly
marked aspirational — a test rejects any article that tries to be neither. The
open gaps are enumerated in the document itself, including the uncomfortable
one: our trust score is still computed by us, from our own records.

**An agent can adopt it without a human in the loop.** Discovery at
`/.well-known/x402` reaches every other surface; the wire contract is served as
JSON Schema at `/v1/schema` and the error codes at `/v1/errors`; payment is
x402, so there is no signup, no key issuance, and no dashboard. `veritas-agent
up` provisions its own config and wallet and starts serving.

## Capabilities

- **Evidence-first research** with content hashing and an append-only custody
  ledger **delivered with the response**, so a buyer re-runs
  `veritas.custody.verify_chain_records` on what they received
- **A countable support report** — independent registrable domains, distinct
  providers, verdict — instead of a confidence score. See "What we removed"
- **First-class refusal** enforced in the pipeline: evidence below the relevance
  threshold is refused (`irrelevant_evidence`), not dressed up as an answer
- **Per-source licence and attribution** on every excerpt, so an agent knows what
  it may reuse; unknown licences are labelled unknown, never assumed permissive
- **Tiered retrieval**: keyed Serper (Google) when configured, plus keyless
  Wikipedia and the DuckDuckGo Instant Answer API, each labelled with the engine
  that actually served it, with provider errors surfaced — never silently
- **x402 payment** with real facilitator `verify` / `settle`, fail-closed gating,
  and an idempotent paid path: a resubmitted authorization never buys a second
  retrieval pass, and returns the deliverable it already paid for
- **A durable financial ledger** (`veritas/ledger.py`) recording every
  authorization, delivery and settlement attempt, with delivery written before
  settlement is attempted and "we never heard back" recorded as indeterminate
  rather than as failure
- **Buyer-side counterparty diligence** (`veritas/diligence.py`,
  `veritas-diligence <url>`) — a buyer agent decides whether a seller may be
  paid at all, from documents that seller publishes, and the verdict gates the
  signer rather than merely advising: the
  402 must agree with advertised discovery on payee, network and asset and must
  not exceed the advertised price; L1 articles must name enforcement; and a
  seller declaring no open gaps is refused for claiming perfection.
  `unverifiable` is reported apart from `fail`, because "I could not check this
  seller" and "this seller failed" call for different action — the CLI carries
  that into its exit code (`0` pass, `1` fail, `2` unverifiable), so an agent
  that shells out cannot collapse the two. Fetching is SSRF-guarded on the
  seller's own links, since a hostile discovery document would otherwise steer
  the buyer's fetcher at the buyer's private network. Every check is
  cross-document consistency — **none proves a seller will deliver**
- **A standalone verifier** (`veritas/verifier.py`, `veritas-verify receipt.json`)
  — one file, zero dependencies, importing nothing from `veritas`. Copy it out
  and run it: a buyer should not have to install our web server to audit our
  receipt, nor check our work with our own code. It re-implements the hash
  chain, and a differential test pins it against the engine on real output and
  on tampered variants. It reports what it does **not** attest: consistent
  records do not mean we ever contacted the URLs we name
- **Hiding wallet commitments** so a broadcast offer does not leak the payout address
- **Signed JIT Disposable Packets** with enforced expiry and verified chain linkage

## Install

```bash
# Directly from the repository — no clone needed, works for an agent today:
pip install "veritas-research @ git+https://github.com/eternal-roman/veritas"

# From a clone (not yet published to PyPI; the release workflow exists but
# needs a maintainer to configure the PyPI project first):
pip install -e ".[signing,dev]"   # development install

# Container (binds 0.0.0.0 inside; the bare console script binds 127.0.0.1):
docker build -t veritas-research . && docker run -p 8000:8000 veritas-research
```

Requires Python >= 3.10 and pip >= 24.1 (the package uses Metadata 2.4).
The wheel ships a single top-level package, `veritas` (engine, agent layer,
HTTP server, and evaluation harness), plus `veritas-server` and
`veritas-agent` console scripts. Verify an install in one line:

```bash
python -c "from veritas.pipeline import run_research; print(run_research('What is x402?', allow_network=False)['status'])"
```

## Quick start (free mode)

```bash
veritas-agent up                            # zero-touch: config + wallet + serve
veritas-ops revenue                         # what was earned, cost and margin (JSON)
veritas-ops reconcile                       # what needs attention (records only, not the chain)
veritas-server                              # server only; VERITAS_HOST / VERITAS_PORT to bind
# or equivalently
python -m uvicorn veritas.server:app --host 0.0.0.0 --port 8000

# or use the library directly
python -c "from veritas.pipeline import run_research; print(run_research('What is x402?'))"
```

Offline / no network:

```python
from veritas.pipeline import run_research
run_research("What is x402?", allow_network=False)   # uses the labelled offline corpus
```

## Retrieval configuration

Zero-key retrieval (Wikipedia + DuckDuckGo) works with no configuration. To
rank a keyed provider ahead of it:

```bash
export VERITAS_SERPER_API_KEY=...   # or the conventional SERPER_API_KEY
```

API keys are configuration, never payload: a key is read from the
environment, sent only as a request header to its provider, and never
serialised into responses, errors, custody events, or receipts (tested — see
`tests/test_providers.py`). Without a key the provider is simply not
registered; a configured provider's outage degrades to the next tier with the
error reported in `retrieval.errors`.

## Live payments

```bash
export VERITAS_PAY_TO=0xYourWallet          # validated as a real EVM address
export VERITAS_FACILITATOR=https://pay.openfacilitator.io   # unverified by us; see ROADMAP
export VERITAS_REQUIRE_PAYMENT=true
export VERITAS_NETWORK=eip155:8453
veritas-server
```

If any of these is invalid the service reports `mode: misconfigured` and returns
503 — it will not quietly serve paid research for free.

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /v1/research` | Run research (402-gated in live mode) |
| `POST /v1/verify` | Origin re-fetch (`url`+`content_hash` or `request_id`); legacy content+hash is non-independent arithmetic |
| `GET /v1/receipts/{id}` | Retrieve a stored custody receipt after the call |
| `GET /v1/trust` | Behaviour-derived trust score (`UNPROVEN` until enough data) |
| `GET /v1/identity` | ERC-8004 style identity document |
| `GET /.well-known/x402` | Discovery + payment requirements |

## Testing

```bash
pip install -e ".[signing,dev]"
python -m pytest tests/ -q
python -m veritas.evaluations.harness
ruff check veritas tests
```

## Known limitations

Stated plainly, because a truth-telling service should not overstate itself:

- **Retrieval quality is thin.** Wikipedia and Instant Answer snippets are not
  competitive with a paid search/extraction stack for general queries.
- **Nothing has ever settled on-chain.** Fail-closed payment paths are
  exercised; a successful settlement is not.
- **Claims are extractive, not synthesised.** A "claim" is a grounded excerpt,
  not an answer composed across sources.
- **The calibrator is untrained and unused.** It reports `passthrough_untrained`,
  needs labelled outcomes via `record_feedback`, and is applied to no response.
- **The harness runs on a 3-document offline corpus.** Its perfect scores
  demonstrate the invariants hold; they are not a quality benchmark.
- **Solana is not payable.** It is recognised for alias resolution but excluded
  from advertised networks because SPL settlement is not implemented.
- **Wallet commitments are hiding, not zero-knowledge.** Public verification of
  the opening requires the reveal at settlement.
- **Self-provisioned wallet files are owner-only on POSIX only.** `os.open(...,
  0o600)` is ignored on Windows and on filesystems without mode bits, leaving
  the keystore and its plaintext passphrase readable beyond their owner. The
  mode is read back after every write and a `WalletPermissionWarning` names any
  file that is unprotected, so this is reported rather than assumed — but on
  those platforms treat the wallet as development-only.

## What we removed, and why

An audit found the service was making claims its served code path did not
support. Rather than soften the wording, the claims and the code behind them
were removed:

- **The Bayesian posterior and per-claim confidence.** The posterior's
  hypothesis was the raw query string (a question has no truth value), its
  constants were typed rather than derived, it could only increase — so the
  `low_confidence` refusal it gated was unreachable — and two contradictory
  sources both pushed it up. Per-claim confidence was decided by list position.
  `veritas/support.py` publishes counts a buyer can recompute instead.
- **The metasearch retrieval tier.** It scraped Google, Bing, Yandex and others
  through a shuffling aggregator while labelling every result `duckduckgo`.
  That is a redistribution problem and, in a provenance product, a falsified
  provenance label.
- **The offline corpus from the live path.** Its fixture text carried real
  third-party URLs and a content hash, which reads as "this text appears at
  this URL". It did not. The corpus is now `veritas://fixture/*` and offline-only.

See `LIVE_PAYMENTS.md`, `JIT_PACKET.md`, `ZK_WALLET.md`, `WORKFLOW.md`,
`ANALYSIS.md`, and `AGENTS.md` (repo guide for agents and contributors).

## Layout

```
veritas/               # the installable package (everything below ships in the wheel)
  pipeline.py          #   single research engine: retrieval -> relevance -> hashing -> custody
  retrieval.py         #   retriever protocol, offline corpus, composite merging
  custody.py           #   hash-chained ledger + durable receipts
  hashing.py support.py schema.py trust.py identity.py safeurl.py
  x402.py facilitator.py payment_config.py networks.py
  server.py            #   FastAPI surface (`veritas-server` console script)
  autonomous/          #   agent-native layer: zero-key retrieval, control plane,
                       #   JIT packets, wallet commitments, bootstrap, calibrator
  evaluations/         #   harness + CI quality gates
tests/                 # not shipped in the wheel
```

## License
Apache-2.0
