# Program state — Veritas → Evidence Notary

**This file is the resume point.** The working container is ephemeral; only what is
committed and pushed survives. Update this file and push after every sub-step.

## NEXT ACTION

> Phase T, steps T9–T11: constitution 2.0 (re-level A12 to L0, add A22/A23, register
> G3–G8, re-render CONSTITUTION.md), pointer resolution via pytest collection (T10),
> and retract the now-false claims in README/ROADMAP/STATUS/ANALYSIS (T11).
> README still advertises "Bayesian belief updating" and DuckDuckGo search — both
> untrue after T4/T6. Fix before starting Phase N0.

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
- [ ] T9 Constitution 2.0: A12 → L0, add A22/A23, register G3–G8, re-render
- [ ] T10 Pointer resolution via real pytest collection, not string grep
- [ ] T11 Retract false claims in STATUS.md / ANALYSIS.md / ROADMAP.md

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
- [ ] X2 Pinned per-network EIP-712 domain table; refuse unverified networks (R1)
- [ ] X3 `/supported` preflight, fail-closed
- [ ] X4 Absolute `resource` URL; require `VERITAS_PUBLIC_URL` in live mode (R2)
- [ ] X5 Default network → Base Sepolia; mainnet explicit opt-in (O11)
- [ ] X6 Bazaar discovery extension, `discoverable: true`
- [ ] X7 `veritas/deadline.py` — deadline budget before settle (R4)

### Phase M — Money infrastructure
- [ ] M1 SQLite ledger: delivery + settlement entries, fsync before responding (R5)
- [ ] M2 Nonce state machine; idempotent replay of a completed paid request (R11)
- [ ] M3 `request_id` recorded against the nonce claim (R6)
- [ ] M4 Indeterminate settlement distinguished from failure (R7)
- [ ] M5 Reconciliation + revenue/COGS/margin reports; `veritas-ops` CLI
- [ ] M6 Metering (COGS per request); versioned pricing table
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
| R1 | critical | EIP-712 domain guessed from symbol; would void every signature | open |
| R4 | critical | No deadline; authorization can expire during paid work | open |
| R5 | critical | No financial ledger; settlement tx hash discarded | open |
| R6 | high | `request_id` never recorded against the nonce claim | open |
| R7 | high | Indeterminate settlement coded as definite failure | open |
| R9 | high | `price` unvalidated → live mode with 500s and a green `/health` | **closed** — `::test_price_is_validated_by_the_misconfiguration_guard` |
| R10 | high | Paid Serper provider called in free mode | open |
| R11 | critical | Dropped connection after settle = charged, undelivered, retry 409 | open |
| O1 | critical | Sync handlers, 40 slots, no deadline — service stalls incl. `/health` | open |
| O2 | critical | Unbounded `/v1/verify` body; no rate limiting anywhere | open |
| O3 | high | `/v1/trust` rescans the whole outcome log, free and unauthenticated | open |
| O4 | high | Nonce store rescanned under global lock per paid request | open |
| O5 | high | Relative runtime dir + cwd dependence → silent 503s | open |
| O6 | high | Two instances: replay, receipt 404s, divergent trust | open |
| O7 | high | Receipt writes neither atomic nor fsynced | open |
| O9 | high | No logging, metrics, tracing or alerting | open |
| O11 | high | `veritas-agent up --paid` targets Base mainnet by default | open |
| O12 | high | No `.dockerignore` beside a plaintext wallet passphrase; no VOLUME | open |
| O14 | med | Unhandled exceptions escape the error envelope as text/plain | open |
| O15 | med | No lockfile/hashes, mutable action refs, vacuous bandit gate | partial — bandit gate raised to `-ll` with real fixes; lockfile/action pinning open |
| T1 | high | Trust score manipulable by free traffic; refusal_health perverse | open |

## Measured numbers

Updated as they are measured, never estimated in this table.

| Metric | Value | Measured at |
|--------|-------|-------------|
| Tests passing | 287 | Phase T (T1–T8) |
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
| 2026-08-05 | T7–T8: repricing to $0.01, price validation, SSRF/scheme guards, bandit `-ll` | this commit |
