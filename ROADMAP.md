# Veritas Roadmap

Sequenced by dependency, not by appeal. Each phase lists deliverables,
acceptance criteria that can be checked mechanically, and the risks that would
invalidate the phase.

Sizing is in engineer-weeks for one experienced engineer. "Blocked by" means the
prior item must land first; anything else can run in parallel.

---

## Phase 0 — Prove settlement (2 weeks)

The facilitator client is written and tested against unreachable hosts, which
exercises the failure path only. No payment has ever completed. Every revenue
claim downstream depends on this working, so it goes first and it is cheap.

### 0.1 Testnet settlement run
- Fund a Base Sepolia wallet with test USDC.
- Run the service with `VERITAS_NETWORK=eip155:84532`, `VERITAS_REQUIRE_PAYMENT=true`.
- Drive a real 402 → sign → verify → settle cycle against a public facilitator.
- Record the transaction hash in `docs/settlement-proof.md`.

**Acceptance:** a Base Sepolia transaction hash exists in which USDC moves from
a buyer wallet to `VERITAS_PAY_TO`, initiated by an unattended request.

### 0.2 Facilitator contract tests
- Add `tests/test_facilitator_contract.py` with recorded fixtures of real
  `/verify` and `/settle` request/response bodies.
- Pin the payload shape so a facilitator API change fails CI rather than
  production.

**Acceptance:** fixtures replay green; mutating a field name fails a test.

### 0.3 Settlement reconciliation
- Extend `CustodyStore` receipts with `transaction`, `payer`, `settled_at`.
- Add `scripts/reconcile.py` comparing receipts against on-chain transfers to
  `pay_to` over a block range.

**Acceptance:** reconciliation reports zero unmatched settlements across a
50-request testnet run.

**Risk:** public facilitators may not support the chosen network or scheme. If
so, self-host `x402-facilitator` — adds ~1 week and an RPC dependency.

---

## Phase 1 — Retrieval quality (4–6 weeks)

This is the product. Everything else is plumbing around it. Currently the
engine returns Wikipedia and DuckDuckGo snippets, which will not sustain a
$0.25 price against a buyer that can call a search API directly.

### 1.1 Full-text extraction
- Add `veritas/extractors.py`: fetch the source URL, extract main content
  (`trafilatura` or `readability-lxml`), fall back to the snippet on failure.
- Hash the extracted text, not the snippet, so evidence is the full passage.

**Acceptance:** median evidence length > 1,500 chars on the eval set, with
extraction failures reported as provider errors rather than silently truncated.

**Blocked by:** nothing.

### 1.2 Paid retrieval backends
- Implement `Retriever` for Exa, Brave, and Serper behind env-var config.
- `CompositeRetriever` already merges and dedupes; register paid providers
  ahead of the keyless ones.
- Keep zero-key providers as the free tier.

**Acceptance:** the same `Retriever` protocol serves both tiers with no pipeline
change; a provider outage degrades to the next tier and is reported.

### 1.3 Claim synthesis
- Replace the current extractive claim (a grounded excerpt) with a synthesis
  step producing an assertion supported by one or more sources.
- Every synthesised claim must carry the `content_hash` of each supporting
  passage; a claim citing no present hash fails `validate_response`.
- Add entailment scoring (NLI model or LLM judge) between claim and cited
  passage; drop claims below threshold.

**Acceptance:** on a 100-question benchmark, ≥95% of synthesised claims are
entailed by at least one cited passage under blind grading.

**Blocked by:** 1.1.

**Risk:** synthesis reintroduces hallucination, which is the failure mode the
architecture exists to prevent. The entailment gate is the control; if it
cannot reach 95%, ship extractive claims and compete on verifiability instead.

### 1.4 Source-independence modelling
- Current damping applies a fixed factor per repeat from the same provider.
- Replace with domain-level and content-similarity clustering: two articles
  syndicated from one wire story are one observation, not two.

**Acceptance:** posterior on three syndicated copies of one story is within
0.05 of the posterior on one copy.

---

## Phase 2 — Benchmarking (2 weeks, parallel with Phase 1)

Without this there is no evidence the service is better than a raw search call,
and no way to detect regressions from Phase 1 changes.

### 2.1 Real benchmark set
- 100–200 questions with known answers, spanning answerable, unanswerable, and
  stale-premise categories.
- Store as `evaluations/datasets/*.jsonl` with provenance for each label.

### 2.2 Baseline comparison
- Baselines: raw search snippets; a general LLM with no retrieval; an LLM with
  naive RAG.
- Metrics: answer accuracy, citation precision/recall, calibration error (ECE),
  correct-refusal rate on unanswerable items.

**Acceptance:** a published table with confidence intervals; CI gates on
regression against the last recorded run.

### 2.3 Calibration training
- Feed graded outcomes into `record_feedback`, populating the calibrator.
- Report ECE before and after.

**Acceptance:** calibrator reports `is_trained: true`; post-calibration ECE
lower than raw posterior ECE on a held-out split.

**Blocked by:** 2.1. This is what turns the calibrator from a passthrough into
a functioning component, and it is the one asset that compounds with usage.

---

## Phase 3 — Buyer-side autonomy (5–7 weeks)

The service can take payment unattended. Nothing in the repository lets an
agent *make* one. This is the larger half of agent-to-agent commerce and the
part with real security exposure.

### 3.1 Payment payload construction
- Add `veritas/client/payer.py`: build an EIP-3009 `transferWithAuthorization`
  authorization (`from`, `to`, `value`, `validAfter`, `validBefore`, `nonce`),
  sign as EIP-712 typed data, wrap in the x402 payload shape, base64-encode
  into `X-PAYMENT`.
- Validate the received `accepts` entry before signing: asset address, network,
  and amount must match expectation, or refuse to sign.

**Acceptance:** a `VeritasBuyer` completes a 402 → pay → 200 cycle against our
own service on testnet with no human step.

### 3.2 Key custody
Three options, in increasing order of safety and cost:

| Option | Model | Blast radius | Effort |
|--------|-------|--------------|--------|
| Hot key in env | Raw private key, hard-capped balance | Full balance | 0.5 wk |
| Managed signer | Turnkey / Privy / CDP; policy enforced server-side | Policy-bounded | 2 wk |
| Smart account + session key | ERC-4337 with scoped session key module | Per-key scope | 4 wk |

Recommendation: managed signer for the first production buyer, session keys
once transaction volume justifies the integration.

**Acceptance:** the signer interface is abstract (`Signer` protocol) so custody
can be swapped without touching payload construction. A key with an exhausted
policy fails signing rather than falling back to an unscoped key.

**Blocked by:** 3.1.

**Risk:** this is the hardest unsolved problem in the space. An agent holding a
funded key with no approval loop is one prompt-injection away from draining it.
Treat retrieved web content as untrusted input to the buying agent; never let
retrieved text influence payment parameters.

### 3.3 Budget enforcement
- `SpendPolicy`: per-request cap, per-hour and per-day totals, per-counterparty
  cap, network allowlist, asset allowlist.
- Enforce before signing, not after; persist counters so a restart does not
  reset the budget.

**Acceptance:** a buyer configured with a $1/day cap refuses the request that
would exceed it, with the refusal recorded; counters survive process restart.

---

## Phase 4 — Discovery (2–3 weeks)

`/.well-known/x402` exists but nothing announces it. An agent cannot find the
service without being handed the URL.

### 4.1 Registry publication
- `scripts/register.py` posting the identity document and payment requirements
  to the CDP x402 Bazaar and any other live registry.
- Re-register on boot and on config change; deregister on shutdown.

**Acceptance:** the service appears in a registry query for its capability
within 5 minutes of boot, and disappears within 5 minutes of shutdown.

### 4.2 MCP server surface
- Expose research as an MCP tool so MCP-native agents can call it without
  bespoke HTTP code.
- Map the 402 challenge into an MCP error carrying payment requirements.

**Acceptance:** an MCP client discovers the tool, receives the payment
requirement, pays, and receives a result.

### 4.3 ERC-8004 registration
- Register the identity document on-chain so reputation is portable across
  registries rather than locked to one index.

**Blocked by:** 0.1 (a registered identity pointing at an unproven payment path
is a support burden).

---

## Phase 5 — Reputation and counterparty risk (3 weeks)

Trust scoring is now derived from recorded outcomes, but it is self-reported
and single-instance. A buyer deciding whether to pay a stranger needs something
better than the seller's own claim.

### 5.1 Signed outcome attestations
- Sign each served result with the service key; buyers can publish
  attestations of outcomes against `request_id`.
- Aggregate published attestations into the trust basis alongside local
  telemetry, weighted lower for unverified reporters.

### 5.2 Buyer-side counterparty checks
- Before paying, fetch the seller's identity and trust document; apply a
  minimum score, require a settled-transaction history, and cap first-time
  exposure.

**Acceptance:** a buyer refuses an unknown counterparty above the first-time
cap, and the refusal names the failed check.

**Risk:** self-reported reputation is gameable by construction. Treat scores as
one input to a spend policy, not as authorization.

---

## Phase 6 — Operations (3 weeks, parallel from Phase 1)

### 6.1 Deployment
- Container image, health/readiness probes, structured JSON logs, one hosted
  instance behind TLS.

### 6.2 Shared state
- Receipts and outcome logs currently write to local disk, so `/v1/receipts` is
  unreliable behind a load balancer. Move to Postgres or object storage.

**Acceptance:** receipts resolve correctly with two instances behind a balancer.

### 6.3 Abuse controls
- Per-IP and per-payer rate limits, request size caps, retrieval timeouts and
  concurrency ceilings.
- Free tier limited independently of the paid tier.

**Acceptance:** a load test at 10× expected traffic degrades to 429 without
falling over or serving unbilled paid work.

### 6.4 Evidence durability
- Receipts store hashes only; if a source URL rots, a buyer can confirm what we
  published but cannot re-obtain the passage.
- Add content-addressed storage for extracted passages with a stated retention
  window; optional IPFS pinning for long-lived evidence.

**Acceptance:** a passage is retrievable by `content_hash` for the full
retention window after the original URL returns 404.

---

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

Phases 1 and 3 are independent and can run concurrently with two engineers.
Phase 6 runs alongside from the start.

## Sequencing rationale

- **Phase 0 first** because it is two weeks and it determines whether the
  commercial premise holds at all. Every later phase assumes payment works.
- **Phase 1 before Phase 3** because a buyer client pointed at a service with
  snippet-grade output demonstrates the protocol, not the product.
- **Phase 2 alongside Phase 1** because synthesis changes cannot be evaluated
  without a benchmark, and the calibrator has no input without graded outcomes.
- **Phase 4 after Phase 0** because registry presence creates inbound traffic;
  inbound traffic against an unproven payment path produces failed settlements.
- **Phase 5 last** because reputation requires volume to be meaningful.

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

- x402 remains the settlement protocol; a shift to another standard invalidates
  Phases 0, 3, and 4.
- USDC on an EVM L2 remains the settlement asset. Solana support requires an
  SPL scheme implementation not covered here.
- Prices stay in the sub-dollar range, which rules out per-request human
  approval and makes Phase 3.3 budget enforcement the only viable control.
