# Program state — Veritas → Evidence Notary

**This file is the resume point.** The working container is ephemeral; only what is
committed and pushed survives. Update this file and push after every sub-step.

## NEXT ACTION

> **M1–M4 landed; G6 and G8 are closed.** `veritas/ledger.py` is a SQLite
> (WAL, `synchronous=FULL`) record of authorizations, deliveries and settlement
> attempts. The paid path now runs verify → deadline → claim(nonce,
> request_id) → work → **record delivery (fsynced)** → settle → record
> settlement → respond, and a resubmitted authorization returns the stored
> deliverable instead of a 409. `veritas/replay.py` is gone: its nonce parsing
> moved to `veritas/x402.py` beside the other payload parsing, and its store is
> superseded — two nonce stores would have been two sources of truth about
> whether a payment was used.
>
> **M5 and M6 also landed.** `veritas/metering.py` counts provider calls,
> evidence bytes and wall time on every request (free ones included — cost is
> incurred regardless of payment); `veritas/pricing.py` stamps
> `PRICE_TABLE_VERSION` on every authorization so revenue across a reprice
> stays explainable; `veritas/ops_cli.py` (`veritas-ops`) reports revenue,
> owed, reconcile, usage, pricing and one authorization end-to-end, as JSON.
>
> **The default cost table is empty and that is deliberate.** No provider's
> list price is verifiable from this sandbox, so `CostTable` ships with nothing
> in it, an unpriced provider is reported as unpriced, and margin is withheld
> rather than computed over a partial cost base. Operators supply real numbers
> via `VERITAS_PROVIDER_COST_MICROS`.
>
> Next: **M7** (credits via SIWx; refunds as credits) or straight to
> **Phase O**, which is the larger risk — sync handlers with 40 threadpool
> slots and no rate limiting mean one slow retrieval stalls `/health`. My
> recommendation is Phase O first: M7 adds a surface, O keeps the ones that
> exist standing up.
>
> New gap opened while closing G8: **G9** — recorded settlements are never
> re-checked against the chain. `settled` currently means "the facilitator told
> us so". Closing it needs RPC access this sandbox does not have.
>
> Deferred within X, deliberately: X3 (`/supported` preflight) and X1 (SDK
> adoption) need facilitator egress this sandbox blocks; X6 (Bazaar) follows X1.
>
> Note the execution order was deliberately inverted from the original plan:
> substrate (X → M → O) before new product surface (N0/N1). Rationale in the
> approved plan — building a paid notary on a payment path that charges
> disconnected buyers (G6/R11) and keeps no ledger (G8/R5) multiplies the defect.

## Resume protocol

1. `git log --oneline -15` — see what actually landed.
2. Read **NEXT ACTION** above.
3. Run the battery to confirm the tree is green before continuing:
   ```bash
   python -m pytest tests/ -q
   ruff check veritas tests scripts
   python -m veritas.evaluations.harness > /dev/null
   python -m veritas.evaluations.payment_model > /dev/null
   ```
4. Continue from the first unchecked sub-step below.

## Program

Repositioning the service from "search snippets with a confidence number" to an
**evidence notary**: `notarize(url) → signed, timestamped, anchored record of what
that URL served at time T`, machine-payable over x402. Full plan and rationale in
`ROADMAP.md` (Part III) once Phase T lands; the audit that motivated it is summarised
in the defect register below.

Decisions taken: evidence notary + trust layer · x402 first, Stripe-ready · build to
one-credential-away with runbooks · licensed/permitted sources with truthful labels.

## Environment constraint (affects what is provable)

The development sandbox blocks outbound egress to `x402.org`, Base Sepolia RPC, and
Wikipedia (only PyPI is reachable). **No on-chain settlement or live-URL fetch is
executable in-session.** Everything is proven against the official x402 SDK's models
offline, a local TLS origin fixture, and a local facilitator harness. Real testnet and
mainnet settlement ship as runbooks under `docs/runbooks/` for an operator with egress.
No claim of on-chain success may be made until an operator produces a transaction hash.

## Phase checklist

Legend: `[ ]` not started · `[~]` in progress · `[x]` done (commit SHA)

### Phase T — Truth restoration (blocking; stops shipping false claims)
- [x] T1 Enforce `MIN_RELEVANCE` in `pipeline.py` evidence loop (P1)
- [x] T2 Deliver `custody_chain` in the response envelope (P2)
- [x] T3 Removed the unreachable `low_confidence` branch with the posterior (P3)
- [x] T4 Removed `ddgs`/metasearch; DDG Instant Answer named truthfully (L1, L2)
- [x] T5 Corpus off the live path; `veritas://fixture/*` URLs (L4)
- [x] T6 Deleted `posterior` and per-claim `confidence`; `support` report replaces them (P4, P5)
- [x] T7 Price default `$0.25` → `$0.01`; price validated by the misconfig guard (R9)
- [x] T8 `payer.py` assert → explicit raise; SSRF/scheme guards + bandit gate at `-ll`
- [x] T9 Constitution 2.0: A12 **promoted** (chain now delivered), A22/A23 added, G3–G8 registered, re-rendered
- [x] T10 Pointer resolution via real pytest collection, not string grep
- [x] T11 Retracted false claims in README / STATUS.md / ANALYSIS.md

### Phase X — x402 correctness (NEXT)
See the checklist further down; execution order is X → M → O → N0 → N1 → L → G.

### Phase N0 — Notary core
- [ ] N0.1 `veritas/notary/fetch.py` with SSRF defence + local TLS origin fixture
- [ ] N0.2 `extract.py` (versioned, deterministic), `record.py` (EvidenceRecord)
- [ ] N0.3 `license.py` + `robots.py`
- [ ] N0.4 `observe.py`; `pipeline.run_research` routes through it (preserves A1)
- [ ] N0.5 `POST /v1/notarize`; stored evidence text + retention class
- [ ] N0.6 `veritas/support.py` — countable support report replacing the posterior

### Phase N1 — Signing, log, anchoring, non-circular verify
- [ ] N1.1 EIP-191 signing with the payment secp256k1 key
- [ ] N1.2 Append-only log + RFC-6962 Merkle batches + inclusion proofs
- [ ] N1.3 Anchors (file backend default; on-chain behind config)
- [ ] N1.4 Re-fetching `/v1/verify/{record_id}`; deprecate the circular verify (P7)
- [ ] N1.5 `veritas/verifier.py` — zero-dependency standalone verification

### Phase X — x402 correctness + SDK adoption
- [ ] X1 Adopt official `x402` SDK behind existing seams
- [x] X2 Pinned per-network EIP-712 domain table with provenance; unverified networks refused (R1)
- [ ] X3 `/supported` preflight, fail-closed
- [x] X4 Absolute `resource` URL; `VERITAS_PUBLIC_URL` required in live mode (R2)
- [x] X5 Base Sepolia default + `--network` and `--i-understand-this-is-real-money` opt-in (O11)
- [ ] X6 Bazaar discovery extension, `discoverable: true`
- [x] X7 `veritas/deadline.py` — budget checked before the nonce claim and again before settle (R4)

### Phase M — Money infrastructure
- [x] M1 SQLite ledger: authorization/delivery/settlement entries, delivery fsynced before settle (R5)
- [x] M2 Nonce state machine; idempotent replay of a completed paid request (R11)
- [x] M3 `request_id` allocated in the handler and recorded against the claim (R6)
- [x] M4 Indeterminate settlement distinguished from failure (R7)
- [x] M5 Reconciliation + revenue/COGS/margin reports; `veritas-ops` CLI
- [x] M6 Metering (COGS per request, free traffic included); versioned pricing stamped per entry
- [ ] M7 Credits via SIWx; refunds as credits, documented

### Phase O — Operations
- [ ] O.1 Async handlers + request deadline + concurrency limit (O1)
- [ ] O.2 Body-size cap, verify `max_length`, per-IP rate limit (O2)
- [ ] O.3 `veritas/store/` protocol with SQLite default (O3, O4, O7, O10)
- [ ] O.4 Lifespan state, readiness ≠ liveness, graceful drain (O5, O14)
- [ ] O.5 JSON logging + metrics endpoint (O9)
- [ ] O.6 Retention/pruning; 410 Gone ≠ 404
- [ ] O.7 `.dockerignore`, VOLUME, compose, deploy configs (O12, O13)
- [ ] O.8 Supply chain: lockfile with hashes, SHA-pinned actions, SBOM, bandit `-ll` (O15)

### Phase L — Legal
- [ ] L.1 TERMS.md, PRIVACY.md, provider compliance matrix, retention policy
- [ ] L.2 Authorization on `/v1/receipts` (L6)
- [ ] L.3 Erasure with hash-preserving tombstones

### Phase G — Ecosystem
- [ ] G.1 Paid MCP surface
- [ ] G.2 Standalone `veritas-verify` distribution
- [ ] G.3 ERC-8004 identity registration (L0 until registered)

### Dogfooding cycles
- [ ] Cycle 1 — cold autonomous install (after N0)
- [ ] Cycle 2 — paying buyer, official SDK, local facilitator (after X)
- [ ] Cycle 3 — hostile caller incl. SSRF (after O)
- [ ] Cycle 4 — operator economics from the ledger alone (after M)
- [ ] Cycle 5 — ecosystem participant, independent verification (after G)

## Defect register

Ids from the three audits. `open` until a test pins the fix.

| Id | Severity | Summary | Status |
|----|----------|---------|--------|
| P1 | critical | Relevance gate absent from production path; irrelevant evidence billed as `completed` | **closed** — `tests/test_truth_restoration.py::test_irrelevant_evidence_is_refused_on_the_production_path` |
| P2 | critical | Custody chain never delivered; `to_list`/`verify_chain_records` unused; A12 false | **closed** — `::test_response_delivers_the_custody_chain` |
| P3 | critical | `low_confidence` refusal unreachable (posterior strictly increases) | **closed** — branch removed with the posterior |
| P4/P5 | high | Posterior cosmetic; claim confidence positional | **closed** — `::test_no_posterior_or_confidence_appears_on_the_wire` |
| P7 | high | `/v1/verify` circular — re-hashes caller input, no source binding | open |
| P13 | med | Evidence text never stored; hashes only | open |
| L1/L2 | critical | `ddgs` metasearch resells scraped SERPs; provenance falsified as `duckduckgo` | **closed** — `tests/test_retrieval_honesty.py::test_no_metasearch_backend_is_used` |
| L3 | high | Wikipedia CC BY-SA reused without licence notice | **closed** — `::test_wikipedia_sources_carry_their_licence_and_attribution` |
| L4 | high | Repo-authored corpus text published under third-party URLs | **closed** — `::test_corpus_urls_are_not_third_party_attributions` |
| L6 | high | Buyer queries persisted forever, served unauthenticated | open |
| R1 | critical | EIP-712 domain guessed from symbol; would void every signature | **closed** — pinned table with provenance; unverified networks refused (`tests/test_x402_protocol.py`). Only Base/Base Sepolia are advertisable, from the reference implementation; **none is yet confirmed on-chain** — run `scripts/verify_eip712_domains.py` |
| R4 | critical | No deadline; authorization can expire during paid work | **closed** — `veritas/deadline.py`; too-short windows refused before work, expiry before settle returns non-billable `deadline_exceeded` (`tests/test_x402_protocol.py`) |
| R5 | critical | No financial ledger; settlement tx hash discarded | **closed** — `veritas/ledger.py`; `tests/test_money_path.py::test_settlement_is_recorded_durably` and `::test_revenue_is_answerable_from_the_ledger_alone`. Gap G8 closed, G9 opened (nothing is reconciled against the chain) |
| R6 | high | `request_id` never recorded against the nonce claim | **closed** — allocated in the handler, threaded through `run_research`, claim and receipt (`::test_the_nonce_is_joined_to_the_request_it_burned_for`) |
| R7 | high | Indeterminate settlement coded as definite failure | **closed** — `SettlementResult.outcome`; a facilitator that never answered records `indeterminate` and the buyer still receives the work (`::test_indeterminate_settlement_delivers_and_says_so`) |
| R9 | high | `price` unvalidated → live mode with 500s and a green `/health` | **closed** — `::test_price_is_validated_by_the_misconfiguration_guard` |
| R10 | high | Paid Serper provider called in free mode | open |
| R11 | critical | Dropped connection after settle = charged, undelivered, retry 409 | **closed** — `::test_replayed_authorization_returns_the_deliverable_it_paid_for`; the work still runs once (`::test_a_replay_does_not_run_the_work_again`). Bounded: single-instance ledger |
| O1 | critical | Sync handlers, 40 slots, no deadline — service stalls incl. `/health` | open |
| O2 | critical | Unbounded `/v1/verify` body; no rate limiting anywhere | open |
| O3 | high | `/v1/trust` rescans the whole outcome log, free and unauthenticated | open |
| O4 | high | Nonce store rescanned under global lock per paid request | **closed** — the JSONL rescan-under-flock is gone; SQLite indexes the nonce and takes a write lock only for the claim transaction |
| O5 | high | Relative runtime dir + cwd dependence → silent 503s | open |
| O6 | high | Two instances: replay, receipt 404s, divergent trust | open |
| O7 | high | Receipt writes neither atomic nor fsynced | partial — the *financial* record is now transactional and fsynced (`synchronous=FULL`); `veritas/custody.py` receipt writes are still plain `write_text` (Phase O.3) |
| O9 | high | No logging, metrics, tracing or alerting | open |
| O11 | high | `veritas-agent up --paid` targets Base mainnet by default | **closed** — testnet default + explicit acknowledgement flag |
| O12 | high | No `.dockerignore` beside a plaintext wallet passphrase; no VOLUME | open |
| O14 | med | Unhandled exceptions escape the error envelope as text/plain | open |
| O15 | med | No lockfile/hashes, mutable action refs, vacuous bandit gate | partial — bandit gate raised to `-ll` with real fixes; lockfile/action pinning open |
| T1 | high | Trust score manipulable by free traffic; refusal_health perverse | open — now **witnessed** by `tests/test_known_gaps.py::test_known_gap_free_traffic_moves_the_trust_score` (constitution gap G7) |

## Measured numbers

Updated as they are measured, never estimated in this table.

| Metric | Value | Measured at |
|--------|-------|-------------|
| Tests passing | 309 | Phase X (X2, X4, X5, X7 done) |
| Payment model traces | 8,720 | 4f2321c |
| COGS per notarization | not measured | — (Cycle 4) |
| Break-even requests/month | not measured | — (Cycle 4) |
| On-chain settlements | **0** | never executed |

## Session log

| Date | Landed | Commits |
|------|--------|---------|
| 2026-08-05 | Program bootstrapped; state file established | ece7e2a |
| 2026-08-05 | T1–T3, T6: relevance gate on the served path, custody chain delivered, posterior removed | e5385bf |
| 2026-08-05 | T4–T5: metasearch scraper removed, licences carried, corpus de-attributed | ba1ae33 |
| 2026-08-05 | T7–T8: repricing to $0.01, price validation, SSRF/scheme guards, bandit `-ll` | c8b87ee |
| 2026-08-05 | T11: README/STATUS/ANALYSIS retractions; honest verdict corrected | 3e48378, 96ac66b |
| 2026-08-05 | T9–T10: constitution 2.0, three open gaps witnessed, pointers resolved by pytest collection | 86ad917 |
| 2026-08-06 | X2 + X5(part): EIP-712 domains pinned with provenance, unverified networks refused, default network → Base Sepolia | 6413382 |
| 2026-08-06 | Bandit gate extended to scripts/; unguarded fetch in the settlement script fixed | 74dfb1b |
