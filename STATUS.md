# Veritas Status

Written to be accurate rather than encouraging. The previous version of this
file described a system that did not import.

## What actually works (verified by tests + CI gates)

| Component | State |
|-----------|-------|
| Content hashing + normalization | Working, tested |
| Custody hash-chain, delivered with the response | Working, tested — the buyer re-runs `verify_chain_records` on delivered data |
| Durable custody receipts (`/v1/receipts`) | Working, tested |
| Relevance gate enforced on the served path | Working, tested — irrelevant evidence is refused, not billed as an answer |
| Refusal taxonomy (`no_evidence`, `irrelevant_evidence`, `unavailable`) | Working, tested |
| Retrieval error surfacing | Working, tested |
| x402 402-challenge construction (atomic amounts) | Working, tested |
| Facilitator verify/settle client, fail-closed | Working, tested against unreachable host |
| Payment misconfiguration guard | Working, tested |
| Hiding wallet commitments | Working, tested |
| Signed JIT packets, enforced expiry, chain verification | Working, tested |
| Behaviour-derived trust score | Working, reports `UNPROVEN` until 10 samples |
| Evaluation harness + CI quality gates | Working |
| Installable package (`pip install .`, single `veritas` namespace, `veritas-server` script) | Working; CI builds the wheel and installs it in a clean venv. Not yet on PyPI |
| Keyed Serper retrieval tier (env-configured, key never serialised, degrades to zero-key tier) | Working against fixture-shaped responses; not yet exercised against the live API with a real key |
| Buyer-side payment construction + spend policy (`veritas.payer`, key-free signer seam) | Working; L1 unit tests + L2 bounded model check (I1–I7, 8,720 traces, CI-gated). EIP-712 signature round-trip verified against `eth_account`. No on-chain settlement yet |
| Container / deploy (`Dockerfile`, `.dockerignore`, `docker-compose.yml`) | Working, tested by reading the shipped files: allowlist build context, no `COPY . .`, non-root user, declared VOLUME for the runtime directory, compose with no baked-in credentials. Not verified against a built image — no Docker daemon in CI |
| Observability (`veritas.observability`) | Working, tested: JSON access logs, Prometheus counters at `/metrics` behind a required token, label values escaped so a request path cannot forge metric lines. Buyer queries and payment headers are asserted absent from logs. In-process counters — each node counts only itself |
| Unit economics (`veritas.metering`, `veritas.pricing`, `veritas-ops`) | Working, tested: provider calls, evidence bytes and wall time metered on every request including free ones; the pricing version is stamped on every authorization; `veritas-ops` reports revenue, what is owed and what needs attention as JSON. **The default cost table is empty on purpose** — no provider list price can be verified from this environment, so an unpriced provider is reported as unpriced and margin is withheld rather than guessed |
| Replay safety + financial ledger (`veritas.ledger`) | Working, tested: a resubmitted `X-PAYMENT` does the work once and returns the stored deliverable; every authorization, delivery and settlement attempt is durable on SQLite and revenue is answerable from the ledger alone. Single-instance scope — local disk. Nothing is reconciled against the chain (gap G9) |
| Venue constitution (`/v1/constitution`, `veritas/constitution.py`) | Working, tested: every L1 article's enforcement pointer resolves; L0 articles carry none; `CONSTITUTION.md` sync-tested; the version lives in the module, never restated here |
| Unified error contract (`veritas/errors.py`, `/v1/errors`) | Working, tested: registered codes, one envelope on every non-402 error including 422 and the previously code-less 503 unavailable body |
| Self-traversing discovery (`/.well-known/x402` links, `/llms.txt`, `/v1/schema`) | Working, tested; identity document no longer fabricates a base URL when none is configured |
| Wallet self-provisioning (`veritas/autonomous/wallet.py`) | Working, tested: locally minted encrypted keystore, owner-only files, plugs into the buyer Signer seam. Funding is external |
| `veritas-agent` CLI (enroll/whoami/skills/init/serve/up/status) | Working, tested: one account binds identity, commerce/plane wallets, and interest-mapped skills; `init`/`up` enroll if missing |
| MCP tools (`veritas-mcp`; the full set is registered at `/v1/hooks`) | Working, tested against the SDK; local free-mode engine only, no payment path over MCP |
| Container + release workflow (`Dockerfile`, `release.yml`) | Dockerfile CI-built; release workflow inert until a maintainer configures PyPI Trusted Publishing |
| Prepaid credits via SIWx (`veritas/credits.py`, `veritas/siwx.py`, HTTP wire) | Working, L1 tests: double-entry topup/grant/debit/refund in atomic units; SIWx challenge+session offline (EIP-4361 message, EIP-191 recover; no RPC); live research with `X-VERITAS-SESSION` and no `X-PAYMENT` debits before work and refunds on non-billable `unavailable` / deadline; insufficient balance returns registered `credits_insufficient`. **Top-up grants only after settled x402** — free/misconfigured refuse inventing credits; failed or indeterminate settlement does not grant. This is **not** on-chain refund of the buyer's original payment and **not** a second payer: credits are prepaid balance only; `X-PAYMENT` still uses the existing verify→claim→work→fsync→settle path when present. Single-instance SQLite; multi-instance credits are open |
| Evidence notary (N0 observe + /v1/notarize) | Working, L1+CI: one engine, SSRF-safe fetch, inv.3 on notarize. Has settled live in an operator-run testnet arc (evidence: `docs/program/fable/settlement/`); external notarize buyers: none |
| EIP-191 attestation (N1.1) + free verify (N1.2) | Working, L1+CI: optional operator sign; free /v1/attestations/verify. Not multi-party origin proof; not on-chain |
| Origin re-fetch verify (P7 product) | Working, L1+CI: url+hash or receipt request_id re-fetches via observe. Legacy content+hash labeled caller_supplied |
| Portable EvidencePack (N1.3) + Merkle log (N1.4/N1.5 inclusion on observe) + inclusion on observe (N1.5) | Working, L1+CI: pack_hash handoff; operator-local inclusion proofs. Not public CT; not on-chain |
| Dogfood cycles 1-5 | Working, CI-gated: first-boot, paying buyer, hostile, operator economics, ecosystem peer. Offline / no chain |
| G9 chain reconcile design | Design + fail-closed ops surface shipped. Gap G9 open; no production RPC required by default |

## What was found false and fixed (2026-08-05 audit)

Three published claims did not hold on the served code path. They are listed
here rather than quietly corrected:

- The relevance gate ran only inside one retriever, so in production any source
  of 40+ characters became a billable `completed` answer however unrelated —
  and the CI quality gate certified a filter production never applied.
- The custody chain was computed and discarded, so `custody_valid: true` was an
  unverifiable self-assertion.
- The keyless retrieval tier scraped multiple search engines through an
  aggregator while labelling every result `duckduckgo`.

All three are fixed and pinned by tests; see `docs/program/STATE.md`.

## What is built but unproven

- **Live settlement is operator-run testnet only.** End-to-end runs against
  the real x402.org facilitator on Base Sepolia have settled and been
  chain-confirmed by `veritas-ops reconcile-chain` — the count and every
  transcript live in `docs/program/fable/settlement/` and the
  `docs/program/STATE.md` header, deliberately not restated here. Mainnet:
  none. Buyers we did not operate: none. Getting the first one required two
  client fixes (facilitator user-agent, x402 v2 wire shape) — the previous
  client could not reach the reference facilitator at all.
- **Credits top-up has settled live once (operator-run).** Grant-on-settled
  and refuse-on-failed/indeterminate are tested with a controlled
  facilitator double, and one real x402 top-up has funded a credit balance
  in an operator-run testnet session (same evidence directory). No external
  buyer has ever topped up.
- **Refunds-as-credits.** When credit-paid research is non-billable
  (`unavailable`, deadline exceeded), the debit is reversed in the credit
  journal so the buyer is not charged for our failure. That is a **ledger
  credit**, not a chain refund of any prior top-up transaction, and not a
  claim that money moved back on-chain.
- **Calibration.** Machinery works and persists; no labelled outcomes exist, so
  it honestly reports `passthrough_untrained`.
- **Aspirational constitution articles.** A16 (portable reputation), A17
  (dispute path), and A18 (registry liveness) are L0 by construction: named
  norms with no enforcement, each citing the roadmap phase expected to promote
  it. Publishing them proves nothing beyond the naming.
- **Known gap G2** (registered in the constitution, pinned by a witness test):
  the local facilitator simulator now enforces payment structure (G1 closed)
  but still does not verify signatures — weaker than the HTTP path's
  facilitator verification. The control plane must not be exposed as a paid
  network surface while G2 is open.
- **What still needs a human**, stated rather than hidden: funding the
  provisioned wallet, TLS/public deployment, the PyPI project + trusted
  publisher (release workflow is otherwise ready), and the GHCR push
  permission for the container.

## What is missing

| Gap | Severity | Note |
|-----|----------|------|
| Commercial-grade retrieval | High | Snippets only; no full-text extraction |
| Answer synthesis across sources | High | Claims are grounded excerpts, not answers |
| Public deployment | High | No hosted instance |
| Quality benchmark vs strong baselines | High | Harness proves invariants, not quality |
| Rate limiting across instances | Medium | Per-IP limiting, body caps and a concurrency cap are in and tested, but all are in-process: each node behind a balancer has its own budget |
| Shared ledger/spend state across instances | Medium | Both are local disk; a second instance does not see them, so a replay routed elsewhere still fails (roadmap 6.2) |
| Chain reconcile as production routine | High | `reconcile-chain` exists and has confirmed real settlements (testnet defaults, env wins), but no production operator runs it on a schedule. Gap G9 is about routine, not capability |
| Bazaar / registry auto-registration | Medium | Manual |
| Durable evidence re-fetch (IPFS pinning) | Medium | Receipts store hashes, not content |
| Solana settlement | Low | Deliberately excluded from advertised networks |

## Honest verdict

The payment path is real code rather than a header check, and after the
2026-08-05 audit the served path no longer makes claims it cannot support.

What remains between this and revenue is still largely operational, not only
code: settlements are operator-run testnet arcs (count and evidence:
`docs/program/STATE.md` header and `docs/program/fable/settlement/`), mainnet
is untouched, and no buyer we did not operate has ever paid; retrieval is
still snippet-grade; PyPI publish needs Trusted Publishing; and G9 chain
reconcile, though exercised against the real chain, still needs production
operators to run it routinely. The programme is tracked in
`docs/program/STATE.md`.

## Security / CI

| Control | State |
|---------|--------|
| CI workflows | On `main` — tests must pass (no soft-fail) |
| Import check | All top-level modules must import |
| Harness quality gates | Fidelity, custody, refusal discrimination, unavailability handling |
| Security scan job | Bandit at `-ll` (medium and high) + pip-audit on runtime and dev |
| Dependabot config | Present (weekly pip + Actions) |
| CODEOWNERS | Present |
| Branch protection | **Documented only** — admin must apply in Settings |
| Dependabot alerts product | Enable in repo Settings → Code security |
