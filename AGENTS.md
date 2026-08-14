# Working in this repository

README is the product. This file is how to work here and which rules are load-bearing.

## First engagement

One local account binds identity, wallets, and skills. No signup server.

```bash
pip install -e ".[signing,dev]"
veritas-agent enroll --id <your-name> --interests research,buy,verify
veritas-agent whoami
veritas-agent skills
```

Interests map to existing capabilities: `research`, `verify`, `diligence`, `audit`, `buy`, `sell`, `notarize`, `ops`, `warranty`, `standing`. Unknown interests stay unmapped.

| Goal | Command |
|------|---------|
| Sell | `veritas-agent up` (`--paid` charges the commerce wallet) |
| Buy | `veritas-buy <seller-url>` |
| Local tools | `veritas-mcp` (includes `whoami`) |
| Vet a seller | `veritas-diligence <url>` |
| Audit a pack | `veritas-audit run pack.json` |

`init` / `up` enroll `id=self` with interests `research,verify` if no account exists. Funding the commerce wallet and public TLS stay external.

Home is `--base-dir` (default `.veritas_agent/`, or `VERITAS_AGENT_HOME`): `account.json`, commerce keystore, plane visa/VAAT ledger. Commerce address is x402 `pay_to`. VAAT is local coordination, not settlement.

## Setup and commands

```bash
pip install -e ".[signing,dev]"
python -m pytest tests/ -q
python -m veritas.evaluations.harness
python -m veritas.evaluations.payment_model
ruff check veritas tests
bandit -r veritas scripts -ll -q
python -m build && twine check dist/*
veritas-server
veritas-agent up
veritas-mcp
VERITAS_METRICS_TOKEN=... veritas-server   # /metrics only when set
veritas-ops revenue
veritas-ops reconcile                      # records only, not the chain
veritas-ops reconcile-chain                # G9; env RPC wins, else testnet default
veritas-diligence https://seller.example   # 0 pass / 1 fail / 2 unverifiable
veritas-audit run pack.json                # 0 confirmed / 1 diverged / 2 unobserved
veritas-audit report r1.json r2.json
veritas-verify receipt.json                # one file, zero deps
python scripts/lock_requirements.py --check  # Linux/CPython 3.12 only
```

`VERITAS_SERPER_API_KEY` (or `SERPER_API_KEY`) ranks keyed Serper ahead of the zero-key tier. Keys are env config, never payload: request header only, never in results, errors, custody, or receipts (tested).

`run_research(query, allow_network=False)` uses the labelled offline corpus. That corpus is not an outage fallback — outages must surface as `unavailable`.

## Layout

One installable package. `veritas/` is the engine plus `autonomous/`, `server.py`, and `evaluations/`. `tests/` is outside the wheel. CI asserts exactly one top-level package.

## Invariants (CI-gated or tested)

1. **One engine.** All surfaces call `veritas.pipeline.run_research`. No second retrieval/custody/Bayes path.
2. **`unavailable` is not `no_evidence`.** Failed retrieval is not an observed absence.
3. **Never bill our own failure.** `billable: false` on `unavailable` gates settlement. x402 charges last, so pre-settle failure leaves the buyer uncharged. Credits debit first, so the research handler refunds on unexpected death. Refunds are idempotent.
4. **Verify payment before work, settle after.** Unpaid callers do not retrieve. Nonces are claimed before work so a resubmitted `X-PAYMENT` cannot buy twice.
5. **Retrievers are untrusted.** They may raise or ignore `max_results`; the pipeline defends both.
6. **Wire contract is enforced.** `veritas.schema.validate_response` runs on real pipeline output. Extend the response only with the contract.
7. **Misconfiguration is not free service.** Invalid payment config → `mode: misconfigured` → 503.
8. **One buyer payment path.** `veritas.payer` owns challenge validation, diligence, spend caps, the attempt journal, and the `Signer` seam. Backends adapt to that seam (`LocalAccountSigner` is the testnet one). Diligence is opt-in (`require_diligence=True`); with it off, only a spend cap bounds a hostile seller.
9. **Version is single-sourced.** Bump only `veritas/__init__.py`. It feeds pyproject (dynamic), the server, identity, and the retrieval User-Agent.
10. **Money records itself before it acts.** Ledger claims the authorization, fsyncs delivery, then settles. No reply → `indeterminate`, never `failed`.
11. **Costs are counted, never invented.** Metering records calls, bytes, wall time. Money is computed only for priced providers; unpriced is reported as unpriced.
12. **CI is pinned.** Actions are commit SHAs. CI installs from hashed `requirements.lock` / `requirements-dev.lock`. Locks are generated only on Linux/CPython 3.12 — `scripts/lock_requirements.py` refuses elsewhere. See SECURITY.md.

## Conventions

- **No CI soft-fail.** No `|| true` or `continue-on-error`.
- **`compileall` is not an import check.** CI's explicit import step exists because compileall accepts missing imports.
- **`skills/adversarial-code-truth.md` is locked.** Emit PROPERTY / EVIDENCE LEVEL before any success claim. Tests are L1. Banned without evidence: "complete", "live-ready", "ZK", "revenue-ready".
- **Program roles load `docs/program/MIND.md` before their charter.** North star is `VISION.md`; program docs point to it, never restate it. "Blocked" needs a dated failing probe; the human is the last rung, with the agent-executable 90% already done.
- **Limitations stay plain** (README "Known limitations", STATUS.md). Narrow claims, evidence cited.
- **Constitution is enforcement-linked.** `veritas/constitution.py` is normative; `CONSTITUTION.md` is a sync-tested rendering. Change both and bump `CONSTITUTION_VERSION`. New norms are L1 with a resolving pointer or L0 marked aspirational — `tests/test_constitution.py` rejects anything else.

## Consume as an agent

| Need | Where |
|------|--------|
| Discovery | `GET /.well-known/x402` (`links` reaches every surface), `/v1/identity`, `/llms.txt` |
| Contract | `/v1/schema`, `/v1/errors`, `/openapi.json` |
| Norms | `/v1/constitution` (enforced or aspirational; see CONSTITUTION.md, ECOSYSTEM.md) |
| Surfaces | `/v1/hooks` (HTTP, MCP, CLI exits, headers, stores; **no push**). Sync-tested both ways |
| Operator | `GET /ui` (HTML, excluded from hooks), `GET /v1/operator`, `POST /v1/operator/enroll` (loopback only) |
| Research | `POST /v1/research` — live mode 402 + `accepts`; retry with `X-PAYMENT` |
| Verify | `POST /v1/verify`; `GET /v1/receipts/{request_id}`; client-side `verify_chain_records` |
| Trust | `/v1/trust` — `UNPROVEN` below 10 outcomes. Input, not authorization |
| Local | `veritas-mcp` — free-mode engine over stdio; no payment path |
| Diligence | `veritas-diligence <url>` — 0 pass / 1 fail / 2 unverifiable. Fetches `links` under SSRF guard. Pass ≠ will deliver |
| Provision | `veritas-agent up` — config + wallet + serve. Funding and TLS stay external |
| Logs | JSON access logs (`VERITAS_LOG_FORMAT`) — method, path, status, duration. Never the query or `X-PAYMENT`. `/metrics` only if `VERITAS_METRICS_TOKEN` is set |
| Ops | `veritas-ops` JSON from `veritas/ledger.py`. `reconcile` is intra-instance only (G9) |

## Field notes (money path) — 2026-08-09

First live settlement (`docs/program/fable/settlement/`, PR #112) found defects a green suite could not. Do not re-learn them:

1. **Versioned User-Agent on every outbound money-path client.** Cloudflare rejects default `Python-urllib` (1010 → 403) on x402.org and sepolia.base.org. Pinned in `tests/test_payment.py`.
2. **Reference facilitator is x402 v2** for exact/eip155:84532 (`amount`, structured `resource`, echo `accepted`). Internals stay v1. One translation site: `FacilitatorClient` (`_wire_requirements` / `_wire_payment_payload`). No second site; no piecemeal v2.
3. **Probe environment claims.** "No egress" was one sandbox. A 60s probe of facilitator `/supported` and RPC `eth_chainId` killed it. `docs/program/` facts need a last-verified date; stale = hypothesis.
4. **Settlement recipe is repeatable.** `scripts/testnet_settlement.py` vs a live-mode server. Circle faucet: 20 testnet USDC / address / 2h, no account. Buyer needs no ETH (EIP-3009). Walkthrough: `docs/program/fable/STATE.md`.
5. **Boundary contact beats another internal round.** Prefer one real counterparty exchange; persist the transcript.
6. **Fan-out ≤8 per wave.** A 28-agent audit died at the usage limit (~1M tokens, zero results). Checkpoint each wave to disk. Persisted partials beat comprehensive results that never land.

## Current state

Invariants above are tested and green. Testnet settlements (Base Sepolia, real x402.org facilitator) are chain-confirmed by `reconcile-chain` — count and transcripts at `docs/program/STATE.md` and `docs/program/fable/settlement/`. Not proven: mainnet, unsolicited buyers, sustained volume. Retrieval is snippet-grade. Not on PyPI. See ROADMAP.md.
