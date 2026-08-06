# Veritas — State of the System and Delivery Roadmap

Self-contained handoff. Everything needed to pick this up cold is here: what the
system does, what is verified, what is broken, and what to build in what order.

Last full evaluation: 2026-07-27, against `main` @ `b498652` plus the fixes in
`95a75ef`. Amended the same day by the packaging pass (single installable
`veritas` package, wheel/sdist build gated in CI — see Phase P below); paths in
this document reflect the post-restructure tree. Amended again the same day by
the constitution pass (machine-readable venue constitution with enforcement
pointers — see Phase C below, `CONSTITUTION.md`, and `ECOSYSTEM.md`) and by
the agent-autonomy pass (error contract, self-traversing discovery,
self-provisioning, MCP tools — see Phase D below).

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

Everything lives in one installable package, `veritas` (see Phase P):

```
veritas/server.py ────────────────┐
                                  ├──> veritas/pipeline.py   (single engine)
veritas/autonomous/control_plane ─┘         │
                                            ├──> veritas/retrieval.py ──> veritas/autonomous/zero_key_retrieval.py
                                            │                                  ├── Wikipedia REST
                                            │                                  └── ddgs / DDG Instant Answer
                                            ├──> veritas/hashing.py
                                            ├──> veritas/custody.py ──> CustodyStore (disk receipts)
                                            └──> veritas/bayesian.py

veritas/server.py ──> veritas/x402.py         (402 challenges, atomic amounts)
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

## Formal gate

Per `skills/adversarial-code-truth.md`, which is a locked gate on all code work
in this repository.

```
PROPERTY: The service never reports absent evidence when retrieval failed, never
          bills for its own failure, and never serves paid research without a
          facilitator-verified payment.
EVIDENCE LEVEL: L1 (tests and adversarial examples)
CHECKED ARTIFACT: veritas/pipeline.py, veritas/retrieval.py, veritas/facilitator.py,
          veritas/server.py, veritas/autonomous/control_plane.py; 240 tests; CI harness gates
ASSUMPTIONS: - Retrievers may raise and may ignore max_results (both now defended)
             - The facilitator honours the documented x402 /verify and /settle contract
             - Receipts are written to a filesystem that persists for the retention window
             - Single-instance deployment (receipts and outcome log are local disk)
NOT PROVEN:  - No payment has ever settled. Fail-closed is exercised; success is not.
             - No conforming third-party x402 client has completed the path end to end.
             - Retrieval quality is untested against any real benchmark; the harness
               runs on a 3-document corpus and its perfect scores are structural.
             - The ledger guards ONE instance (local disk). Two instances behind
               a balancer do not share authorization state, so a replay routed
               to the other one still fails.
             - Recorded settlements are never re-checked against the chain
               (constitution gap G9): the ledger states what the facilitator
               told us, not what we hold.
             - Behaviour under concurrency, load, or a hostile caller is unmeasured.
```

**Structural vs application success.** Everything green below is structural: it
proves the code does what its design says on the cases exercised. It does not
prove the product works. A skeptical external agent cannot today discover this
service, pay it, and receive research competitive with a direct search API —
because nothing is deployed, nothing has settled, and retrieval is snippet-grade.
Those are the product-killing gaps, and they are Phases 0, 1 and 4 below.

## Verified working (structural, L1)

Each row is covered by a test or a CI gate. "Holds on these cases" is the
strongest claim these support.

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
| Venue constitution | Every L1 article's enforcement pointer resolves to a real test/CI-gate/schema artifact; L0 articles carry none and are rendered as aspirational; `CONSTITUTION.md` sync-tested against `veritas/constitution.py` |
| Error contract | Registered codes (`veritas/errors.py`), one envelope on every non-402 error, 422 included; served at `/v1/errors` |
| Discovery surfaces | Self-traversing `/.well-known/x402` with live links; identity honest about unset base URL; `/llms.txt` sync-tested and lists only real endpoints; `/v1/schema` matches real pipeline output |
| Agent self-provisioning | `veritas-agent up` bootstraps config + encrypted wallet keystore (owner-only files) and applies it to the env the server reads; wallet plugs into the buyer Signer seam |
| MCP tools | research/verify/trust/constitution register with the SDK; module imports without the SDK installed |
| Packaging floors | requirements.txt pins never fall below pyproject install floors (tested) |

**Test suite: 240 passing.** CI runs compileall, an import check of all
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
| 4 | ~~No replay protection~~ | — | Fixed (0.4): nonces are claimed before work; a resubmission returns the stored deliverable rather than a 409. Single-instance scope. |
| 5 | No rate limiting | Medium | No per-IP or per-payer caps, no request-size limit on the `X-PAYMENT` header. |
| 6 | Receipts and outcome log are local disk | Medium | `/v1/receipts` is unreliable behind a load balancer. `OutcomeLog.stats()` re-reads the whole file per call. Both grow unbounded. |
| 7 | Evidence content is not stored | Medium | Only hashes. A buyer can confirm what we published but cannot re-obtain the passage after a source URL rots. |
| 8 | Calibrator is untrained | Medium | Machinery works and persists; reports `passthrough_untrained`. Needs labelled outcomes. |
| 9 | ~~Layering inversion~~ | — | Fixed by the packaging pass: the agent layer is now `veritas.autonomous`, a subpackage, and the lazy import no longer crosses top-level packages. |
| 10 | Benchmark is a 3-document corpus | Low | Harness proves invariants hold. Its perfect scores are not a quality claim. |
| 11 | Solana advertised nowhere but aliased | Low | Deliberately excluded from payable networks; SPL settlement unimplemented. |

## Repository health

`main` is green. Both workflows pass at HEAD:

| Workflow | Result at `b498652` |
|----------|---------------------|
| CI | success |
| CodeQL | success |

**Resolved: the permanently-red `Dependency review` job is gone.** It failed on
every pull request — including Dependabot PRs containing no application code —
with:

```
Dependency review is not supported on this repository.
Please ensure that Dependency graph is enabled
```

It errored *before* analysing anything, so across the repository's history it
never once produced a dependency signal; what it did produce was a red check on
every PR, which is how teams learn to ignore CI. Enabling **Settings → Code
security → Dependency graph** would have fixed it, but that needs an admin and
cannot be done from a pull request.

It was removed rather than left red or soft-failed (`continue-on-error` is
banned here). Coverage went up, not down: `pip-audit` now audits the dev and
optional dependency tree in addition to the runtime one, on every push and
pull request, and Dependabot still opens update PRs. If Dependency graph is
enabled later, the action can be restored as an additional PR-diff-level
check — it was never the only dependency control, just the only broken one.

Two other things that look like failures but are not: three CI runs on `main`
show `cancelled`, which is the `cancel-in-progress` concurrency group
superseding queued runs when four PRs merged in quick succession; and the
historical failures on `2cc5eaa` and `5e548ef` are the pre-fix commits where
the package could not import.

---

# Part III — Roadmap

Sequenced by dependency. Sizing is engineer-weeks for one experienced engineer.

## Phase P — Packaging & distribution (mostly done; remainder ~0.5 week)

Prerequisite for every phase that expects a third party — human or agent — to
install and run this. Split into what is done (verified in CI) and what
remains.

**Done in this pass (evidence: CI `package` job builds sdist+wheel, passes
`twine check`, installs the wheel in a clean venv, imports it, runs offline
research, and asserts no stray top-level packages):**

- **P.1 Single-package restructure.** `autonomous/`, `app/`, `evaluations/`
  merged into the `veritas` package (`veritas.autonomous`, `veritas.server`,
  `veritas.evaluations`). The wheel ships exactly one top-level name; the
  core→agent-layer import no longer crosses packages (closes issue #9).
- **P.2 Complete metadata.** SPDX license expression + LICENSE file
  (Apache-2.0 text was previously claimed but absent from the repo),
  classifiers, keywords, project URLs, `py.typed`, version single-sourced
  from `veritas.__version__` (server, identity document, and retrieval
  user-agent all derive from it).
- **P.3 Entry point.** `veritas-server` console script; `VERITAS_HOST` /
  `VERITAS_PORT` control binding.
- **P.4 Install paths.** `pip install .`, `.[signing]`, `.[dev]`
  (test/lint/build tooling). Lint (ruff) added to CI with zero findings.

**Remaining:**

- **P.5 PyPI publication.** The tag-triggered Trusted Publishing workflow
  exists (`.github/workflows/release.yml`, with a tag↔version gate covering
  the CI half of P.6) but is inert until a maintainer creates the
  `veritas-research` project on PyPI and configures the trusted publisher —
  the name is still unreserved. *Acceptance:* `pip install veritas-research`
  from a clean machine serves `/health`. Until then, install works directly
  from the repository: `pip install "veritas-research @
  git+https://github.com/eternal-roman/veritas"`.
- **P.6 Release discipline.** The tag↔version check ships in release.yml;
  remaining: a CHANGELOG.
- **P.7 Container image** (folds into 6.1). A `Dockerfile` exists (non-root,
  healthcheck, binds 0.0.0.0) and CI builds it; publishing to GHCR needs a
  registry-permissions decision a maintainer must make.

*Risk:* none technical; P.5 and the GHCR push need account/permissions
decisions, which is why they are not done from this branch.

## Phase C — Venue constitution (done; now at version 1.1)

The norms the service holds toward the venue — buyer agents, facilitators,
registries, attesters — made machine-readable and enforcement-linked.
`veritas/constitution.py` is the normative source: 18 L1 articles each
pointing at the test, CI gate, or schema invariant that enforces it (1.1
added A19 replay refusal, A20 bounded buyer spending, A21 agent
self-provisioning), 3 L0 articles marked aspirational with their promotion
phase named, and a known-gaps register whose open entries are pinned by
witness tests — G1 (simulator accepted any payment header) was closed under
that discipline and its residual weakness registered as G2 (the simulator
does not verify signatures). Served unpaid at `GET /v1/constitution`,
referenced from `/v1/identity`, rendered in `CONSTITUTION.md` (sync-tested),
with the surrounding venue architecture in `ECOSYSTEM.md`. *Evidence:*
`tests/test_constitution.py`; CI green. What this does not prove: that the
articles are sufficient against a hostile venue, or anything about the L0
articles beyond their being named.

## Phase D — Agent-autonomy surfaces (done in this pass)

Four gaps between "an agent can call this" and "an agent can adopt this
without a human", each closed with tests:

- **Unified error contract.** `veritas/errors.py` registry + one envelope on
  every non-402 error; the 503 retrieval-unavailable body previously had no
  `error` key at all; 422s were raw FastAPI shape; served at `GET /v1/errors`.
- **Self-traversing discovery.** `/.well-known/x402` links every
  machine-readable surface; free mode publishes an honest empty `accepts`
  plus `configured_price`; the identity document dropped its fake
  `api.veritas.example` default for relative paths and an explicit
  `base_url_configured` flag; `GET /llms.txt` (+ sync-tested repo copy);
  `GET /v1/schema` renders the wire contract as JSON Schema.
- **Self-provisioning.** `veritas-agent up` = bootstrap config + locally
  minted encrypted wallet keystore (`veritas/autonomous/wallet.py`) + config
  applied to the environment the server actually reads
  (`bootstrap.apply_to_env`) + serve. Funding the wallet, TLS, and public
  deployment remain external and are stated (constitution A21).
- **MCP surface (the local half of 4.2).** `veritas-mcp` serves
  research/verify/trust/constitution as stdio MCP tools over the one engine;
  no payment path over MCP — mapping the 402 challenge into an MCP error for
  remote paid use remains open in 4.2.

*Evidence:* `tests/test_errors.py`, `test_discovery.py`, `test_wallet.py`,
`test_agent_cli.py`, `test_mcp_server.py`, `test_autonomous_payment.py`,
`test_packaging.py`; CI green.

## Phase 0 — Prove settlement (2 weeks)

No payment has ever completed. Every commercial claim downstream rests on this,
and it is cheap, so it goes first.

- **0.1 Testnet settlement run.** Fund a Base Sepolia wallet with test USDC. Run
  with `VERITAS_NETWORK=eip155:84532`, `VERITAS_REQUIRE_PAYMENT=true`. Drive a
  real 402 → sign → verify → settle cycle. Record the transaction hash.
  *Acceptance:* a Base Sepolia transaction in which USDC moves from a buyer
  wallet to `VERITAS_PAY_TO`, initiated by an unattended request. While there:
  record each network's actual on-chain USDC EIP-712 domain (`name()` /
  `version()` — e.g. "USD Coin" vs "USDC" varies by deployment) and pin them
  in `USDC_ASSETS`; today the buyer trusts the challenge's `extra` block for
  the domain, and a wrong value means signatures that cannot settle.
- **0.2 Facilitator contract tests.** Record real `/verify` and `/settle`
  request/response bodies as fixtures. *Acceptance:* fixtures replay green;
  renaming a field fails a test.
- **0.3 Reconciliation.** *Partly done* (`veritas/ledger.py`). Every
  authorization, delivery and settlement attempt is now durable, joined by
  `request_id`, with `transaction`, `payer`, `amount` and `asset` recorded and
  `Ledger.summary()` answering revenue from the ledger alone. **Not done:**
  nothing compares those records to on-chain transfers — that needs an RPC
  endpoint and is registered as constitution gap G9. *Remaining acceptance:*
  zero unmatched settlements across a 50-request testnet run.
- **0.4 Replay safety.** *Done* (`veritas/ledger.py`). The authorization
  nonce is claimed after facilitator verification and **before** any retrieval
  pass, durably and under a SQLite write lock; the claim is never released,
  since the authorization it names stays live on chain. Acceptance — the same
  `X-PAYMENT` header submitted twice does the work once — is a test
  (`tests/test_replay.py::test_resubmitted_header_does_the_work_once`, which
  counts pipeline invocations). The refusal that used to accompany it was
  itself a defect (gap G6): a buyer whose connection dropped after settlement
  was charged and could not re-sign a single-use authorization. A resubmission
  now returns the stored deliverable. *Limit:* the store is local disk, so it
  guards one instance; behind a load balancer this needs the shared state
  in 6.2.
- **0.5 Signature-scheme compatibility probe.** The Phase 3 custody endgame
  (smart account + session keys) requires the facilitator to verify ERC-1271
  contract-wallet signatures for the `exact` scheme, and the deployed USDC on
  each target network to accept them in `transferWithAuthorization` (v2.2+).
  Neither is proven. *Acceptance:* a recorded testnet result per facilitator
  and network; the 3.2 session-key decision must cite it.

*Risk:* a public facilitator may not support the chosen network or scheme.
Self-hosting adds ~1 week and an RPC dependency.

## Phase 1 — Retrieval quality (4–6 weeks)

This is the product. Everything else is plumbing around it.

- **1.1 Full-text extraction.** Fetch the source URL and extract main content
  (`trafilatura` or `readability-lxml`); hash the extracted passage, not the
  snippet. *Acceptance:* median evidence length > 1,500 chars on the eval set,
  extraction failures reported as provider errors.
- **1.2 Paid retrieval backends.** *Serper done* (`veritas/providers.py`):
  registered ahead of the zero-key tier when `VERITAS_SERPER_API_KEY` /
  `SERPER_API_KEY` is set; the acceptance criterion — a provider outage
  degrades to the next tier and is reported, with no pipeline change — is a
  test (`test_serper_outage_degrades_to_next_tier`), as is key non-leakage
  into any serialised output. *Note:* exercised against a recorded fixture of
  the Serper response shape, not yet against the live API with a real key —
  that first live call is the remaining acceptance step. Exa and Brave remain,
  following the same shape.
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
  *Status:* the offline half is implemented and TDD'd (`veritas/payer.py`:
  challenge validation → EIP-712 payload → policy gate → abstract signer →
  `X-PAYMENT` header; no key material in-process). Evidence: L1 unit tests
  plus an L2 bounded model check (`veritas/evaluations/payment_model.py`,
  CI-gated) — invariants I1–I7 hold across an exhaustive 8,720-trace bounded
  space including signer-fault and restart variants. Remaining for
  acceptance: the unattended testnet run against a funded wallet. A real
  signer now exists — `veritas.buyer_payment.LocalAccountSigner` puts an
  in-process `eth_account` key behind the `Signer` seam (testnet-only; the
  production model keeps keys out of the process), and a test signs a
  `payer.py` payload and recovers the signer's address from the signature, so
  the EIP-712 encoding is verified rather than assumed. Still unproven: no
  payment has settled on chain, and the signature has never been submitted to
  a real facilitator.
- **3.2 Key custody — committed design (encoded 2026-07-27).**

  1. **The key never enters the agent process.** Key bytes live only in the
     signer (managed signer service, or KMS/HSM behind a policy shim). The
     agent holds a short-lived credential to *request* signatures: it sends
     the EIP-712 payload, it receives a signature. `veritas.payer.Signer` is
     the abstract seam; there is no code path that loads key material.
  2. **Two independent policy layers.** The agent-side `SpendPolicy` (3.3) and
     the signer's own policy both gate every authorization. The agent's
     judgment is assumed compromisable (prompt injection is the primary
     threat), so signer-side caps are the backstop, not a duplicate.
     An exhausted policy fails the signature; there is no fallback key.
  3. **Payment parameters derive only from the validated 402 challenge.** The
     signing path accepts only a `ValidatedAccepts` produced and registered by
     `validate_accepts`; pipeline evidence text has no route into amount,
     payTo, asset, or network. Scope, precisely: the challenge itself is
     content from an untrusted counterparty and is the sole source of `payTo`
     and `amount` — this guarantee pins parameters to the challenge the buyer
     validated, it does not authenticate the seller (that is 5.2); only spend
     caps bound loss to a hostile seller. (Python cannot make the structural
     guard absolute against deliberate in-process bypass; it is enforced
     structurally — including against `dataclasses.replace` copies — and
     checked by the payment model.)
  4. **Treasury tiering, not ephemeral keys.** A fresh key per payment fails
     for EOAs: each new address holds nothing, funding it costs an on-chain
     transfer signed by a funded key, and that funding key becomes the real
     hot key. Instead: cold treasury (hardware/multisig) tops up a
     capped-float spending account; compromise loses at most the float. The
     seller side needs no key at all — `VERITAS_PAY_TO` should simply be a
     cold address; settlement executes the buyer's authorization.
  5. **Ephemerality at the layers where it works.** Per payment: the EIP-3009
     nonce is random and single-use, the amount exact, the validity window
     short (~60 s). Per session, once 0.5 proves ERC-1271 support end to end:
     ERC-4337 smart account with a cold root owner granting short-lived,
     scope-capped, revocable session keys.

  | Option | Blast radius | Effort | Status |
  |--------|--------------|--------|--------|
  | Hot key in env, capped balance | Full float | 0.5 wk | Implemented for the testnet run only (`LocalAccountSigner`), routed through the policy gate; rejected as end-state |
  | Managed signer (Turnkey / Privy / CDP) | Policy-bounded | 2 wk | **Committed first step** |
  | Smart account + session key (ERC-4337) | Per-key scope | 4 wk | Gated on the 0.5 probe |

  *Acceptance:* an exhausted policy fails signing rather than falling back to
  an unscoped key. *Risk:* unchanged — an agent holding a funded signing
  credential with no policy backstop is one prompt-injection away from
  draining the float; that is why layer 2 is signer-side.
- **3.3 Budget enforcement.** Per-request, per-hour, per-day, per-counterparty
  caps; network and asset allowlists. Enforce before signing; persist counters.
  *Acceptance:* a $1/day cap refuses the exceeding request, and counters survive
  restart.
  *Status:* agent-side layer implemented (`veritas.payer.SpendPolicy`):
  per-request / per-day / per-counterparty caps, network allowlist, persisted
  counters that survive restart (tested, and exercised by the model's
  restart variants). Remaining: per-hour granularity, asset allowlists, and —
  per the 3.2 design — the independent signer-side policy layer, which no
  local code can substitute for.

## Phase 4 — Discovery (2–3 weeks)

`/.well-known/x402` exists but nothing announces it.

- **4.1 Registry publication.** Post identity and payment requirements to the
  CDP x402 Bazaar and other live registries; re-register on boot and config
  change, deregister on shutdown. *Acceptance:* appears in a capability query
  within 5 minutes of boot, disappears within 5 of shutdown. Registry payloads
  should carry the constitution reference (version + endpoint) already exposed
  by `/v1/identity`; completing this promotes article A18.
- **4.2 MCP surface.** *Local half done* (Phase D: `veritas-mcp` serves the
  engine as stdio tools). Remaining: map the 402 challenge into an MCP error
  carrying payment requirements, so a remote MCP client can pay.
- **4.3 ERC-8004 registration.** On-chain identity so reputation is portable
  (with 5.1, the promotion path for article A16).

*Blocked by:* 0.1. Registry presence creates inbound traffic; inbound traffic
against an unproven payment path produces failed settlements.

## Phase 5 — Reputation (3 weeks)

- **5.1 Signed attestations.** Sign served results; let buyers publish outcome
  attestations against `request_id`; aggregate into the trust basis, weighted
  below local telemetry. Attestations should cite constitution article ids
  (`CONSTITUTION.md`) so a dispute names the norm at issue; with 4.3 this is
  the promotion path for articles A16 and A17.
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
| P — Packaging (remainder: PyPI publish + release discipline) | 0.5 |
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
pip install -e ".[signing,dev]"
python -m pytest tests/ -q               # 240 tests
python -m veritas.evaluations.harness    # quality report
veritas-server                           # free mode (or: python -m uvicorn veritas.server:app)
ruff check veritas tests
bandit -r veritas -lll -q
python -m build && twine check dist/*    # packaging, same gate CI runs
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
- **`skills/adversarial-code-truth.md` is a locked gate.** Emit the PROPERTY /
  EVIDENCE LEVEL block before any success claim. Tests are L1 — "holds on these
  cases" — not proof the product works. Do not use "complete", "live-ready",
  "ZK", or "revenue-ready" in this repository without evidence that carries
  them; the payment path is spec-shaped but unsettled, and is therefore
  incomplete rather than "wired".
