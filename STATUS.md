# Veritas Status

Written to be accurate rather than encouraging. An earlier version of this
file described a system that did not import.

## What actually works (tests + CI)

| Component | State |
|-----------|-------|
| Hashing + normalization | Tested |
| Custody chain, delivered with the response | Tested — buyer re-runs `verify_chain_records` on delivered bytes |
| Durable receipts (`/v1/receipts`) | Tested |
| Relevance gate on the served path | Tested — irrelevant evidence is refused |
| Refusal taxonomy (`no_evidence`, `irrelevant_evidence`, `unavailable`) | Tested |
| Retrieval error surfacing | Tested |
| x402 402 challenge (atomic amounts) | Tested |
| Facilitator verify/settle, fail-closed | Tested against unreachable host |
| Payment misconfiguration guard | Tested |
| Hiding-wallet commitments | Tested |
| Signed JIT packets (expiry, chain) | Tested |
| Trust score | Independent audits via POST; GET is UNPROVEN from the operator log |
| Evaluation harness + CI quality gates | Working |
| Installable package (single `veritas` namespace) | CI builds and installs the wheel. Not on PyPI |
| Keyed Serper tier | Fixture-shaped responses; live key not exercised |
| Buyer pay + spend policy (`veritas.payer`) | L1 + L2 (I1–I7, 8,720 traces). EIP-712 vs `eth_account`. No on-chain settle in those tests |
| Container / deploy | Files tested: allowlist context, no `COPY . .`, non-root, declared VOLUME, compose with no baked credentials. Image not built in CI |
| Observability | JSON access logs; `/metrics` behind token; queries and `X-PAYMENT` absent from logs. Per-node counters |
| Unit economics (`metering`, `pricing`, `veritas-ops`) | Calls, bytes, wall time on every request. Default cost table is empty — unpriced stays unpriced |
| Replay + ledger | Resubmitted `X-PAYMENT` works once, returns the stored deliverable. Single-instance SQLite. Chain check is `reconcile_against_chain` |
| Constitution (`/v1/constitution`) | L1 pointers resolve; L0 carry none; `CONSTITUTION.md` sync-tested |
| Error contract (`/v1/errors`) | Registered codes on every non-402 error |
| Discovery | `/.well-known/x402`, `/llms.txt`, `/adopt.json`, `/v1/schema`; identity does not invent a base URL |
| Wallet self-provisioning | Encrypted keystore; owner-only where POSIX allows. Funding external |
| `veritas-agent` (adopt/enroll/whoami/skills/fund-proof/init/serve/up/status) | One account binds plane identity, commerce wallet, signed did:pkh card, interest-mapped skills; fund-proof observes Transfer logs; `init`/`up` enroll if missing |
| Operator viewer (`/ui`, `/v1/operator`) | HTML + JSON over existing config. Enroll is loopback-only. Visa stripped from GET |
| MCP (`veritas-mcp`; listed at `/v1/hooks`) | Tested against the SDK. Local free-mode engine; no payment path |
| Release workflow | Dockerfile CI-built. PyPI job waits on `PYPI_TRUSTED_PUBLISHER=configured` |
| Credits via SIWx | Double-entry; grant only after settled x402; refund on non-billable `unavailable`. Ledger credit, not a chain refund. Single-instance SQLite |
| Evidence notary (`/v1/notarize`) | One engine, SSRF-safe, inv.3. Operator-run testnet settle exists; external buyers: none |
| EIP-191 attestation + free verify | Not multi-party origin proof; not on-chain |
| Origin re-fetch (`/v1/verify`) | `url`+hash or receipt id. Legacy content+hash is `caller_supplied` |
| EvidencePack + Merkle log | Operator-local. Not public CT; not on-chain |
| Dogfood cycles 1–5 | CI-gated. Offline / no chain |
| G9 chain reconcile | `Ledger.reconcile_against_chain` + money_loop. Mainnet still needs env RPC |

## Found false and fixed (2026-08-05)

Published claims that did not hold on the served path:

- Relevance gate ran in one retriever only — any 40+ character source became a billable `completed` answer. CI certified a filter production never applied.
- Custody chain was computed and discarded, so `custody_valid: true` was unverifiable.
- Keyless retrieval scraped multiple engines through an aggregator and labelled every result `duckduckgo`.

Fixed and test-pinned. See `docs/program/STATE.md`.

## Built but unproven

- **Settlement is operator-run testnet only.** Real x402.org facilitator, Base Sepolia, chain-confirmed. Count and transcripts: `docs/program/fable/settlement/` and `docs/program/STATE.md`. Mainnet: none. Unsolicited buyers: none. First live run needed a User-Agent fix and the x402 v2 wire adapter.
- **Credits top-up** has settled live once (operator-run). External top-ups: none.
- **Refunds-as-credits** reverse a non-billable debit in the credit journal. Not a chain refund.
- **Calibration** reports `passthrough_untrained` — no labelled outcomes.
- **Aspirational articles** A16–A18 are L0: named, unenforced.
- **G2:** local facilitator checks payment structure (G1 closed) but not signatures. Do not expose the control plane as a paid network surface while G2 is open.
- **Still needs a human:** fund the wallet, TLS/public host, PyPI trusted publisher, GHCR push.

## Missing

| Gap | Severity | Note |
|-----|----------|------|
| Commercial-grade retrieval | High | Snippets only |
| Cross-source synthesis | High | Excerpts, not answers |
| Public host | High | None |
| Quality vs strong baselines | High | Harness proves invariants |
| Cross-instance rate limits | Medium | In-process per node |
| Shared ledger across instances | Medium | Local disk; replay routed elsewhere still fails (roadmap 6.2) |
| Production-routine chain reconcile | Medium | Ledger method + money_loop; mainnet still needs env RPC |
| Registry auto-registration | Medium | Manual |
| Durable evidence re-fetch | Medium | Receipts store hashes, not content |
| Solana settlement | Low | Deliberately not advertised |

## Honest verdict

The payment path is real code. After the 2026-08-05 audit the served path no
longer claims what it cannot support.

What remains is mostly operational: operator-run testnet only, no unsolicited
buyers, snippet retrieval, PyPI unpublished. G12 escrow still open.
Tracked in `docs/program/STATE.md`.

## Security / CI

| Control | State |
|---------|--------|
| CI on `main` | Tests must pass (no soft-fail) |
| Import check | All top-level modules |
| Harness gates | Fidelity, custody, refusal, unavailability |
| Security job | Bandit `-ll` + pip-audit |
| Dependabot | Weekly pip + Actions |
| CODEOWNERS | Present |
| Branch protection | **Documented only** — apply in Settings |
| Dependabot alerts | Enable in Settings → Code security |
