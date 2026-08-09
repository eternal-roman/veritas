# Working in this repository

Guide for agents (and humans) contributing to or consuming Veritas. The README
covers what the product is; this file covers how to work on it and what rules
are load-bearing.

## Setup and commands

```bash
pip install -e ".[signing,dev]"  # everything needed to develop
python -m pytest tests/ -q               # test suite — must stay green
python -m veritas.evaluations.harness    # quality report (JSON to stdout)
python -m veritas.evaluations.payment_model  # bounded payment-invariant check — CI gates on this
ruff check veritas tests                 # lint — CI gates on this
bandit -r veritas scripts -ll -q         # security scan — CI gates on medium and high
python -m build && twine check dist/*    # packaging — CI builds and installs the wheel
veritas-server                           # run the service (free mode by default)
veritas-agent up                         # zero-touch: bootstrap config + wallet, then serve
veritas-mcp                              # serve the engine as local MCP tools (stdio)
VERITAS_METRICS_TOKEN=... veritas-server # /metrics exists only when a token is set
veritas-ops revenue                      # operator reports from the ledger (JSON)
veritas-ops reconcile                    # what needs attention; states it has NOT checked the chain
veritas-diligence https://seller.example # vet a counterparty; exit 0 pass / 1 fail / 2 unverifiable
veritas-audit run pack.json              # audit an attested pack against its origin; 0 confirmed / 1 diverged / 2 unobserved
veritas-audit report r1.json r2.json     # survival report (counts) over audit records you hold
veritas-verify receipt.json              # audit a receipt; one vendorable file, zero dependencies
python scripts/lock_requirements.py --check  # hashed locks current — Linux/CPython 3.12 only
```

Retrieval tiers: setting `VERITAS_SERPER_API_KEY` (or `SERPER_API_KEY`) ranks
the keyed Serper provider ahead of the zero-key tier. Keys are configuration,
never payload — read from env, sent only as a provider request header, never
serialised into results, errors, custody events, or receipts (tested).

Offline development: `run_research(query, allow_network=False)` uses the
labelled offline corpus. The corpus is **not** a fallback for provider outages
— an outage must propagate as `unavailable`, never be papered over with
fixture text.

## Layout

One installable package. `veritas/` is the engine plus, as subpackages, the
agent-native layer (`veritas/autonomous/`), the FastAPI surface
(`veritas/server.py`), and the evaluation harness (`veritas/evaluations/`).
`tests/` stays outside the wheel. The wheel must ship exactly one top-level
package — CI's package job asserts this.

## Invariants that must hold (each is CI-gated or tested)

1. **One engine.** All surfaces call `veritas.pipeline.run_research`. Never
   add a second retrieval/custody/Bayes path.
2. **Never report absent evidence when retrieval failed.** `unavailable` is
   not `no_evidence`. This distinction is the product.
3. **Never bill for our own failure.** `billable: false` on `unavailable` is
   load-bearing; settlement is gated on it. x402 satisfies this by ordering —
   it charges last, so any failure before settlement leaves the buyer
   uncharged. Credits invert that order (the debit precedes the work), so the
   research handler reverses the debit when a request dies on an unexpected
   exception. Refunds are idempotent, so the crash guard and the handled
   refusals cannot double-pay.
4. **Verify payment before work, settle after.** An unpaid caller must not
   consume a retrieval pass; a buyer must never be charged for undeliverable
   work. A payment nonce is claimed before the work too, so a resubmitted
   `X-PAYMENT` cannot make us pay for the same request twice.
5. **Retrievers are untrusted.** They may raise and may ignore `max_results`;
   the pipeline defends against both.
6. **The wire contract is enforced.** `veritas.schema.validate_response` runs
   against real pipeline output in tests. Extending the response means
   extending the contract.
7. **Misconfiguration never silently becomes free service.** Invalid payment
   config → `mode: misconfigured` → 503.
8. **One buyer payment path.** `veritas.payer` owns challenge validation,
   counterparty diligence, spend caps, the attempt journal, and the `Signer`
   seam. Signing backends adapt to that seam
   (`veritas.buyer_payment.LocalAccountSigner` is the testnet one); never add a
   second path that signs without the gate. Diligence verdicts come from
   `veritas.diligence` and are opt-in per client (`require_diligence=True`);
   with the gate off, a spend cap is the only bound on a hostile seller.
9. **Version is single-sourced.** `veritas.__version__` feeds pyproject
   (dynamic), the server, the identity document, and the retrieval user-agent.
   Bump it in exactly one place: `veritas/__init__.py`.
10. **The money path records itself before it acts.** `veritas.ledger` claims
   the authorization before work, writes the delivery (fsynced) before
   settlement is attempted, and appends every settlement attempt. A settlement
   we never heard back about is `indeterminate`, never `failed`.
11. **Costs are counted, never invented.** `veritas.metering` records provider
   calls, bytes and wall time on every request; money is computed only for
   providers an operator has priced, and an unpriced provider makes the report
   say so instead of assuming zero.
12. **What CI runs is pinned, not resolved at run time.** Every Action is a
   commit SHA; every dependency CI installs comes from `requirements.lock` /
   `requirements-dev.lock` under `--require-hashes`. The locks are generated
   only on Linux/CPython 3.12 — `scripts/lock_requirements.py` refuses
   elsewhere, because pip evaluates environment markers against the running
   interpreter and an off-target lock fails only at install time. See
   SECURITY.md for what this does and does not establish.

## Conventions

- **CI has no soft-fail.** Do not add `|| true` or `continue-on-error`.
- **`compileall` is not an import check.** The explicit import step in CI
  exists because compileall passes on unresolvable imports.
- **`skills/adversarial-code-truth.md` is a locked gate** on all code work
  here. Emit its PROPERTY / EVIDENCE LEVEL block before any success claim.
  Tests are L1 ("holds on these cases"), not proof the product works. Banned
  without carrying evidence: "complete", "live-ready", "ZK", "revenue-ready".
- Docs state limitations plainly (see README "Known limitations", STATUS.md).
  Keep that register: narrow claims, evidence cited.
- **The venue constitution is enforcement-linked.** `veritas/constitution.py`
  is the normative source; `CONSTITUTION.md` is a sync-tested rendering.
  Changing an article means changing both and bumping `CONSTITUTION_VERSION`;
  a new norm is either L1 with a resolving enforcement pointer or L0 marked
  aspirational — `tests/test_constitution.py` rejects anything else.

## Consuming the service as an agent

- Discovery: `GET /.well-known/x402` — self-traversing (its `links` object
  reaches every surface below), plus `GET /v1/identity` and `GET /llms.txt`.
- Contract: `GET /v1/schema` (wire contract as JSON Schema), `GET /v1/errors`
  (registered error codes with status and retriability), `GET /openapi.json`.
- Norms: `GET /v1/constitution` — the venue constitution, each article either
  pointing at its enforcement artifact or marked aspirational (see
  `CONSTITUTION.md` and `ECOSYSTEM.md`).
- Research: `POST /v1/research` — returns 402 with an `accepts` array in live
  mode; retry with an `X-PAYMENT` header (base64 x402 payload).
- Verification: `POST /v1/verify` re-checks any published `content_hash`;
  `GET /v1/receipts/{request_id}` returns the durable custody receipt;
  `veritas.custody.verify_chain_records` re-runs chain validation client-side.
- Trust: `GET /v1/trust` is behaviour-derived and reports `UNPROVEN` below 10
  recorded outcomes. Treat it as an input, not authorization.
- Local tools: `veritas-mcp` exposes research/verify/trust/constitution as MCP
  tools over stdio (free-mode local engine; no payment path over MCP).
- Vetting a seller: `veritas-diligence <url>` fetches a counterparty's
  published surfaces and prints a JSON verdict with a reason per check. Exit
  codes separate the two refusals — `1` fail (a contradiction was observed),
  `2` unverifiable (the checks could not be run) — so an agent shelling out
  cannot treat its own network trouble as the seller's misconduct. Fetching
  follows discovery's `links` and SSRF-guards every one of them, because a
  hostile discovery document is caller-controlled input into the buyer's
  fetcher. A pass is not proof a seller will deliver.
- Self-provisioning: `veritas-agent up` bootstraps config and a local wallet
  and serves; funding the wallet and public TLS deployment remain external.
- Observability: JSON access logs on stdout (`VERITAS_LOG_FORMAT=json|text`)
  carrying method, path, status and duration — **never** the query or the
  `X-PAYMENT` header. `/metrics` serves Prometheus counters and exists only
  when `VERITAS_METRICS_TOKEN` is set, because settlement counters are revenue.
- Operations: `veritas-ops` answers revenue, what is owed, what needs
  attention, and what serving consumed — all from `veritas/ledger.py`, all as
  JSON. `reconcile` compares this instance's records against each other only
  and says so: nothing is checked against the chain (constitution gap G9).

## Field notes from live contact (2026-08-09) — read before touching the money path

The first real settlement (`docs/program/fable/settlement/`, PR #112) found
defects that internal verification structurally could not. Do not re-learn
these:

1. **Every outbound HTTP client must send a versioned User-Agent.**
   Cloudflare fronts both x402.org and sepolia.base.org and rejects the
   default `Python-urllib` agent (error 1010 → HTTP 403) before reading the
   body. The facilitator client and the G9 RPC transport were both
   structurally unable to reach their production counterparties while every
   test stayed green. Pinned by `tests/test_payment.py` — keep the pattern
   for any new client.
2. **The reference facilitator speaks x402 v2 only** for exact/eip155:84532:
   it routes handlers by `x402Version`, renames `maxAmountRequired`→`amount`,
   moves resource/description/mimeType into a structured `resource` block,
   and expects the selected requirement echoed as `accepted`. Internal shapes
   stay v1; the one translation site is `FacilitatorClient`
   (`_wire_requirements` / `_wire_payment_payload`). Do not add a second
   translation site, and do not "fix" internal shapes to v2 piecemeal —
   migrate end to end or not at all.
3. **Do not trust recorded environment constraints — probe them.** The
   long-standing "no egress, settlement unprovable from here" premise was one
   sandbox's, not this machine's. A 60-second probe (`curl` the facilitator
   `/supported` and the RPC `eth_chainId`) invalidated it. Any environment
   claim in `docs/program/` needs a last-verified date; treat stale ones as
   hypotheses.
4. **The settlement recipe is repeatable.** `scripts/testnet_settlement.py`
   against a live-mode server; Circle's faucet (faucet.circle.com) is
   permissionless — 20 testnet USDC per address per 2 hours, no account; the
   buyer needs no ETH (EIP-3009: the facilitator submits and pays gas). Full
   walkthrough: `docs/program/fable/STATE.md`.
5. **An hour of boundary contact beats a week of internal rigor.** Every
   defect above was invisible to a green 791-test suite and found in minutes
   of live contact. Prefer one real exchange with a production counterparty
   over another round of self-verification; record the transcript as
   evidence.
6. **Fan-out discipline for agent workflows.** A 28-agent audit workflow died
   mid-flight on the session usage limit: ~1M tokens spent, zero results
   returned, nothing recoverable. Keep fleets small (≤8 per wave), stage
   waves so each checkpoints its results to disk before the next starts, and
   fall back to inline synthesis when limits are near. Partial results that
   are persisted beat comprehensive results that never land.

## Current state, honestly

Structural invariants above are tested and green. One payment has settled
on-chain: a testnet (Base Sepolia) end-to-end run against the real x402.org
facilitator — tx recorded and chain-confirmed by `reconcile-chain`; evidence
in `docs/program/fable/settlement/`. Not yet proven: mainnet settlement, any
buyer we did not operate ourselves, sustained volume. Retrieval is
snippet-grade and the package is not yet published to PyPI. See ROADMAP.md
for the full evaluation and sequencing.
