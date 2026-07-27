# Veritas — State of the System and Delivery Roadmap

Self-contained handoff. Everything needed to pick this up cold is here: what the
system does, what is verified, what is broken, and what to build in what order.

Last full evaluation: 2026-07-27, against `main` @ `b498652` plus the fixes in
`95a75ef`.

---

# Part I — What this is

An evidence-grounded research service that other agents pay for over x402. A
buyer sends a question; it returns claims, each citing a content-hashed
passage, with a Bayesian posterior and a hash-chained custody ledger the buyer
can independently verify.

The distinguishing behaviour is the outcome taxonomy:

| Status | Meaning | Billable |
|--------|---------|----------|
| `completed` | Evidence found; every claim cites a hash present in the response | Yes |
| `refused` | Providers reachable, nothing relevant found | Yes |
| `unavailable` | Retrieval itself failed | **No** |

The third row is the product. Any service can return confident text. A service
that separates "no evidence exists" from "I could not look", and declines to
bill for the second, is selling something a language model cannot fake.

## Architecture

```
app/main.py ─────────────┐
                         ├──> veritas/pipeline.py   (single engine)
autonomous/control_plane ─┘         │
                                    ├──> veritas/retrieval.py ──> autonomous/zero_key_retrieval.py
                                    │                                  ├── Wikipedia REST
                                    │                                  └── ddgs / DDG Instant Answer
                                    ├──> veritas/hashing.py
                                    ├──> veritas/custody.py ──> CustodyStore (disk receipts)
                                    └──> veritas/bayesian.py

app/main.py ──> veritas/x402.py         (402 challenges, atomic amounts)
           ├──> veritas/facilitator.py  (POST /verify, POST /settle)
           └──> veritas/payment_config.py ──> veritas/networks.py ──> veritas/x402.USDC_ASSETS
```

Two invariants hold structurally, and both were violated before this work:

1. **One engine.** `control_plane` previously contained a second, independent
   pipeline while the HTTP surface served a static three-document corpus. The
   live retrieval was unreachable and the reachable code was fabricated.
2. **One source of truth for payability.** `supported_networks()` derives from
   `USDC_ASSETS`, so the service cannot advertise a network on which it cannot
   construct a payment.

## Request flow, live mode

```
402 challenge  ──>  buyer signs  ──>  X-PAYMENT header
                                          │
                              facilitator /verify   (fail closed)
                                          │
                                   run_research
                                          │
                        billable? ──no──> 503, no settlement
                                          │yes
                              facilitator /settle
                                          │
                         200 + X-PAYMENT-RESPONSE + custody receipt
```

Verify-before-work and settle-after-work is deliberate: a buyer is never
charged for a request that produced nothing deliverable.

---

# Part II — Evaluation

## Verified working

Each row is covered by a test or a CI gate.

| Component | Evidence |
|-----------|----------|
| Content hashing + normalization | Round-trip and tamper tests |
| Custody hash-chain | Tamper detection test; `verify_chain_records` for post-hoc audit |
| Durable receipts (`/v1/receipts`) | Written to disk, 404 on unknown id |
| Bayesian updating | Correct Bayes; correlated-source damping keeps 3 same-provider sources under 0.9 |
| Refusal taxonomy | Discrimination measured both ways: refuse unsupported, answer supported |
| Outage honesty | Failing retriever yields `unavailable`, never `no_evidence`, never billable |
| Retriever robustness | Raising retriever converts to `unavailable`; `max_results` enforced against the retriever |
| x402 challenges | Atomic amounts (`$0.25` → `250000`), real USDC assets, spec-shaped `accepts` |
| Facilitator client | Fails closed on unconfigured, unreachable, HTTP error, malformed response |
| Payment ordering | Unpaid caller cannot consume a retrieval pass (both surfaces) |
| Config validation | Invalid address/network/facilitator → `misconfigured` + 503, never silent free service |
| Wallet commitments | Salt never published; forged and challenge-replayed proofs rejected |
| JIT packets | Stable identity across chain, MAC signatures, enforced expiry, verified linkage |
| Trust scoring | Derived from recorded outcomes; `UNPROVEN` below 10 samples |
| Wire contract | `validate_response` run against live pipeline output across three retriever types |

**Test suite: 65 passing.** CI runs compileall, an import check of all
top-level modules, the tests, and harness quality gates (citation fidelity,
custody validity, refusal discrimination, unavailability handling), plus Bandit
and pip-audit.

## Defects found in this evaluation and fixed (`95a75ef`)

All three were in the hardening work itself, found by adversarial probing
rather than by the test suite — worth noting, because it shows the suite was
testing the happy path of its own design.

1. **`max_results` was not enforced.** It was passed to the retriever and
   trusted. Asking for 5 and receiving 50 produced 50 evidence items and a
   0.896 posterior off correlated sources. Unbounded work and response size per
   request.
2. **A raising retriever escaped as a 500**, bypassing the `unavailable` /
   non-billable path that exists precisely so provider failure is never charged.
3. **`control_plane` ran the research before checking payment**, discarding the
   result if unpaid. An unpaid caller could consume the full cost of a request,
   contradicting the documented verify-before-work ordering.

## Known-unfixed issues

Ordered by severity. None is a correctness bug in the happy path; all are real
gaps a production deployment would hit.

| # | Issue | Severity | Notes |
|---|-------|----------|-------|
| 1 | Live settlement never exercised | High | Client matches the documented API and is tested against unreachable hosts. That verifies fail-closed, not that a payment completes. |
| 2 | Retrieval is snippet-grade | High | Wikipedia + DuckDuckGo. Will not sustain a paid price against a buyer who can call a search API directly. |
| 3 | Claims are extractive | High | A claim is a grounded excerpt, not an answer synthesised across sources. |
| 4 | No replay protection | Medium | The same `X-PAYMENT` header resubmitted causes the work to run again. Facilitator nonce handling should prevent double-spend, but our cost is incurred twice. |
| 5 | No rate limiting | Medium | No per-IP or per-payer caps, no request-size limit on the `X-PAYMENT` header. |
| 6 | Receipts and outcome log are local disk | Medium | `/v1/receipts` is unreliable behind a load balancer. `OutcomeLog.stats()` re-reads the whole file per call. Both grow unbounded. |
| 7 | Evidence content is not stored | Medium | Only hashes. A buyer can confirm what we published but cannot re-obtain the passage after a source URL rots. |
| 8 | Calibrator is untrained | Medium | Machinery works and persists; reports `passthrough_untrained`. Needs labelled outcomes. |
| 9 | Layering inversion | Low | `veritas/retrieval.py` lazily imports `autonomous.zero_key_retrieval`; the core package depends on the agent layer. |
| 10 | Benchmark is a 3-document corpus | Low | Harness proves invariants hold. Its perfect scores are not a quality claim. |
| 11 | Solana advertised nowhere but aliased | Low | Deliberately excluded from payable networks; SPL settlement unimplemented. |

## Repository health

`main` is green. Both workflows pass at HEAD:

| Workflow | Result at `b498652` |
|----------|---------------------|
| CI | success |
| CodeQL | success |

**One repository setting needs an admin.** The `Dependency review` job fails on
every pull request, including Dependabot PRs containing no application code:

```
Dependency review is not supported on this repository.
Please ensure that Dependency graph is enabled
```

Fix at **Settings → Code security → Dependency graph**. It cannot be fixed from
a pull request. It does not affect pushes to `main`, where the job is skipped —
which is why `main` is green while PRs show red. Bumping the action to v5 did
not help; the step errors before doing any analysis.

Two other things that look like failures but are not: three CI runs on `main`
show `cancelled`, which is the `cancel-in-progress` concurrency group
superseding queued runs when four PRs merged in quick succession; and the
historical failures on `2cc5eaa` and `5e548ef` are the pre-fix commits where
the package could not import.

---

# Part III — Roadmap

Sequenced by dependency. Sizing is engineer-weeks for one experienced engineer.

## Phase 0 — Prove settlement (2 weeks)

No payment has ever completed. Every commercial claim downstream rests on this,
and it is cheap, so it goes first.

- **0.1 Testnet settlement run.** Fund a Base Sepolia wallet with test USDC. Run
  with `VERITAS_NETWORK=eip155:84532`, `VERITAS_REQUIRE_PAYMENT=true`. Drive a
  real 402 → sign → verify → settle cycle. Record the transaction hash.
  *Acceptance:* a Base Sepolia transaction in which USDC moves from a buyer
  wallet to `VERITAS_PAY_TO`, initiated by an unattended request.
- **0.2 Facilitator contract tests.** Record real `/verify` and `/settle`
  request/response bodies as fixtures. *Acceptance:* fixtures replay green;
  renaming a field fails a test.
- **0.3 Reconciliation.** Extend receipts with `transaction`, `payer`,
  `settled_at`; add a script comparing receipts to on-chain transfers.
  *Acceptance:* zero unmatched settlements across a 50-request testnet run.
- **0.4 Replay protection.** Track spent payment nonces; reject resubmission.
  *Acceptance:* the same `X-PAYMENT` header submitted twice does the work once.

*Risk:* a public facilitator may not support the chosen network or scheme.
Self-hosting adds ~1 week and an RPC dependency.

## Phase 1 — Retrieval quality (4–6 weeks)

This is the product. Everything else is plumbing around it.

- **1.1 Full-text extraction.** Fetch the source URL and extract main content
  (`trafilatura` or `readability-lxml`); hash the extracted passage, not the
  snippet. *Acceptance:* median evidence length > 1,500 chars on the eval set,
  extraction failures reported as provider errors.
- **1.2 Paid retrieval backends.** Implement `Retriever` for Exa, Brave, Serper
  behind env config. The protocol and `CompositeRetriever` already support this;
  register paid providers ahead of keyless ones and keep zero-key as the free
  tier. *Acceptance:* a provider outage degrades to the next tier and is
  reported, with no pipeline change.
- **1.3 Claim synthesis.** Replace grounded excerpts with assertions supported
  by one or more sources, each carrying the `content_hash` of its support. Gate
  with entailment scoring (NLI model or LLM judge); drop claims below threshold.
  *Acceptance:* ≥95% of synthesised claims entailed by a cited passage under
  blind grading on a 100-question benchmark. *Risk:* synthesis reintroduces
  hallucination, the exact failure mode the architecture exists to prevent. If
  the gate cannot reach 95%, ship extractive claims and compete on
  verifiability.
- **1.4 Source-independence modelling.** Replace fixed per-provider damping with
  domain and content-similarity clustering. *Acceptance:* posterior on three
  syndicated copies of one wire story within 0.05 of the posterior on one copy.

*Blocked by:* nothing. 1.3 blocked by 1.1.

## Phase 2 — Benchmarking (2 weeks, parallel with Phase 1)

Without this there is no evidence the service beats a raw search call, and no
regression detection for Phase 1.

- **2.1 Dataset.** 100–200 questions with known answers across answerable,
  unanswerable, and stale-premise categories, stored with label provenance.
- **2.2 Baselines.** Raw search snippets; bare LLM; naive RAG. Metrics: answer
  accuracy, citation precision/recall, ECE, correct-refusal rate.
  *Acceptance:* published table with confidence intervals; CI gates on
  regression against the last recorded run.
- **2.3 Calibrator training.** Feed graded outcomes through `record_feedback`.
  *Acceptance:* `is_trained: true`; post-calibration ECE below raw ECE on a
  held-out split.

*Blocked by:* 2.1. This is the one asset that compounds with usage.

## Phase 3 — Buyer-side autonomy (5–7 weeks)

The service takes payment unattended. Nothing here lets an agent *make* one.
This is the larger half of agent-to-agent commerce.

- **3.1 Payment payload construction.** Build an EIP-3009
  `transferWithAuthorization` (`from`, `to`, `value`, `validAfter`,
  `validBefore`, `nonce`), sign as EIP-712, wrap in the x402 payload,
  base64 into `X-PAYMENT`. Validate the received `accepts` entry — asset,
  network, amount — before signing. *Acceptance:* a buyer completes
  402 → pay → 200 against our own service on testnet with no human step.
- **3.2 Key custody.**

  | Option | Blast radius | Effort |
  |--------|--------------|--------|
  | Hot key in env, capped balance | Full balance | 0.5 wk |
  | Managed signer (Turnkey / Privy / CDP) | Policy-bounded | 2 wk |
  | Smart account + session key (ERC-4337) | Per-key scope | 4 wk |

  Recommend managed signer first, session keys once volume justifies it. Keep
  the `Signer` interface abstract. *Acceptance:* an exhausted policy fails
  signing rather than falling back to an unscoped key. *Risk:* an agent holding
  a funded key with no approval loop is one prompt-injection away from draining
  it. Treat retrieved web content as untrusted input to the buying agent; never
  let retrieved text influence payment parameters.
- **3.3 Budget enforcement.** Per-request, per-hour, per-day, per-counterparty
  caps; network and asset allowlists. Enforce before signing; persist counters.
  *Acceptance:* a $1/day cap refuses the exceeding request, and counters survive
  restart.

## Phase 4 — Discovery (2–3 weeks)

`/.well-known/x402` exists but nothing announces it.

- **4.1 Registry publication.** Post identity and payment requirements to the
  CDP x402 Bazaar and other live registries; re-register on boot and config
  change, deregister on shutdown. *Acceptance:* appears in a capability query
  within 5 minutes of boot, disappears within 5 of shutdown.
- **4.2 MCP surface.** Expose research as an MCP tool; map the 402 challenge
  into an MCP error carrying payment requirements.
- **4.3 ERC-8004 registration.** On-chain identity so reputation is portable.

*Blocked by:* 0.1. Registry presence creates inbound traffic; inbound traffic
against an unproven payment path produces failed settlements.

## Phase 5 — Reputation (3 weeks)

- **5.1 Signed attestations.** Sign served results; let buyers publish outcome
  attestations against `request_id`; aggregate into the trust basis, weighted
  below local telemetry.
- **5.2 Counterparty checks.** Before paying, fetch the seller's identity and
  trust document; require a minimum score and a settled history; cap first-time
  exposure. *Acceptance:* a buyer refuses an unknown counterparty above the
  first-time cap, naming the failed check.

*Risk:* self-reported reputation is gameable by construction. It is an input to
a spend policy, not authorization.

## Phase 6 — Operations (3 weeks, parallel from Phase 1)

- **6.1 Deployment.** Container image, health/readiness probes, structured JSON
  logs, one hosted instance behind TLS.
- **6.2 Shared state.** Move receipts and outcome log to Postgres or object
  storage. *Acceptance:* receipts resolve correctly with two instances behind a
  balancer.
- **6.3 Abuse controls.** Per-IP and per-payer rate limits, request and header
  size caps, retrieval timeouts and concurrency ceilings, free tier limited
  independently. *Acceptance:* 10× expected load degrades to 429 without falling
  over or serving unbilled paid work.
- **6.4 Evidence durability.** Content-addressed storage for extracted passages
  with a stated retention window. *Acceptance:* a passage is retrievable by
  `content_hash` for the full window after its source URL returns 404.

## Critical path

```
0.1 settlement proof
      │
      ├─> 1.1 extraction ─> 1.3 synthesis ─> 2.2 benchmark ─> 2.3 calibration
      │
      ├─> 3.1 payer ─> 3.2 custody ─> 3.3 budgets
      │
      └─> 4.1 registry ─> 4.3 ERC-8004 ─> 5.1 attestations
```

Phases 1 and 3 are independent and run concurrently with two engineers. Phase 6
runs alongside from the start.

## Sequencing rationale

- **Phase 0 first** — two weeks, and it determines whether the commercial
  premise holds at all.
- **Phase 1 before Phase 3** — a buyer client pointed at snippet-grade output
  demonstrates the protocol, not the product.
- **Phase 2 alongside Phase 1** — synthesis cannot be evaluated without a
  benchmark, and the calibrator has no input without graded outcomes.
- **Phase 4 after Phase 0** — see above.
- **Phase 5 last** — reputation requires volume to mean anything.

## Estimate

| Phase | Weeks (1 eng) |
|-------|---------------|
| 0 — Settlement proof | 2 |
| 1 — Retrieval quality | 4–6 |
| 2 — Benchmarking | 2 |
| 3 — Buyer autonomy | 5–7 |
| 4 — Discovery | 2–3 |
| 5 — Reputation | 3 |
| 6 — Operations | 3 |
| **Serial total** | **21–26** |
| **Two engineers, parallel tracks** | **13–16** |

## Assumptions

- x402 remains the settlement protocol. A shift invalidates Phases 0, 3, 4.
- USDC on an EVM L2 remains the asset. Solana needs an SPL scheme not covered.
- Prices stay sub-dollar, which rules out per-request human approval and makes
  Phase 3.3 budget enforcement the only viable control.

---

# Part IV — Working on this

## Commands

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q          # 65 tests
python -m evaluations.harness       # quality report
python -m uvicorn app.main:app      # free mode
ruff check veritas autonomous app evaluations tests
bandit -r veritas autonomous app -lll -q
```

Offline (no network): `run_research(query, allow_network=False)` uses the
labelled corpus. Note the corpus is **not** a fallback for provider outages —
substituting fixture text for a failed live fetch would hide the outage, so an
outage propagates as `unavailable` instead.

## Conventions worth preserving

- **CI has no soft-fail.** `5e548ef` removed the `|| true` workarounds that let
  five import errors sit on a green `main`. Do not add them back.
- **`compileall` is not an import check.** It passes on unresolvable imports;
  the explicit import step exists because of that.
- **Retrievers are untrusted.** They may raise and may ignore `max_results`.
  The pipeline defends against both.
- **The wire contract is enforced.** `validate_response` runs against real
  pipeline output in tests. Extending the response means extending the contract.
- **Never bill for our own failure.** `billable: false` on `unavailable` is
  load-bearing; the settle call is gated on it.
