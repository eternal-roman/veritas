# Changelog

## [Unreleased]

### Added
- VCAE (`veritas.escrow`, `veritas.escrow.v1`): EIP-3009 authorization
  is the lock. `escrow_bond` / `escrow_stake` persist; `settle_forfeit`
  submits through the existing facilitator after a fired challenge. A
  facilitator refusal leaves the lock collectable. HTTP:
  `POST /v1/escrow`, `GET /v1/escrow/{lock_id}`,
  `POST /v1/escrow/{lock_id}/release` (never submits),
  `POST /v1/escrow/{lock_id}/forfeit` (live facilitator required).
  `veritas-ops escrow-sweep` / `escrow <lock_id>`. Not a vault contract.
  Local facilitator still G2. Mainnet collect unproven.
- Prediction-market signals (`veritas.signals`, `veritas.signals.v1`):
  public Kalshi + Polymarket book snapshots stored through the evidence
  channel. Prices, not verdicts. No trading, no keys. Hosts allowlisted;
  redirects re-checked. HTTP: `GET /v1/signals`,
  `GET /v1/signals/{content_hash}`, `POST /v1/signals`.
  `PredictionMarketRetriever` is opt-in and is not on the default
  research path.
- Shared financial state via `VERITAS_DATABASE_URL`: a sqlite file URL
  shares ledger, credits, evidence blobs, and rate-limit hits across
  processes on one host; a postgres URL (optional `postgres` extra) is
  the multi-host seam. Unset keeps per-directory SQLite. In-memory
  sqlite is refused.
- Lexical NLI-gated synthesis on the research path. Extractive claims
  stay. Synthesized claims (`kind: synthesized`, `support_hashes`) emit
  only when every content token is present in the cited excerpts. Not
  an LLM and not commercial-grade.
- `GET /v1/evidence/{content_hash}` returns the stored excerpt for a
  published hash (404 `not_found` on a miss). Pipeline persists excerpts
  so a hash stays retrievable after the origin 404s.
- `veritas-ops reconcile-loop` — one local reconcile + chain classify
  pass (the cron shape) with optional `VERITAS_RECONCILE_ALERT_URL`.
  Does not rewrite the ledger. Mainnet still needs `VERITAS_RPC_URL`.
- Cold archive of pruned receipts when `VERITAS_ARCHIVE_DIR` is set.
  A failed archive write keeps the live copy. Local directory, not S3.
- Known-free providers default to cost 0 (`wikipedia`,
  `duckduckgo_instant_answer`, `static_corpus`, `zero_key`, `composite`,
  `prediction_markets`, `polymarket`, `kalshi`).
  Paid APIs stay unpriced. A rejected env override drops that default.

### Changed
- Constitution 2.8: G12 closed. Warranties that carry an EIP-3009 lock
  are `bond_binding: eip3009_authorization` and collectable via
  `settle_forfeit`. Warranties that omit a lock stay
  `signed_commitment_not_escrow`.
- `/v1/hooks` 1.7: escrow + signals routes and stores; `escrow-sweep` /
  `escrow` on the ops CLI.
- `/v1/hooks` 1.6: evidence route, evidence/archive stores, reconcile-loop
  on the ops CLI, shared-store locations.
- Served research observes source URLs when `VERITAS_OBSERVE_URLS` is
  unset or truthy. `run_research()` itself still defaults off. Tests pin
  the env to `0`.
- Metric path collapse covers `/v1/evidence/{content_hash}`.

## [0.12.0] - 2026-08-14

### Added
- Adopt card: root `adopt.json` + `GET /adopt.json` (`/v1/hooks` 1.5). A
  GitHub-only agent fetches the raw file and runs `veritas-agent adopt`.
- Wallet-signed ecosystem identity (`did:pkh` + EIP-191) on enroll when
  the signing extra is present. Recoverable off-box; not ERC-8004.
- `veritas-agent fund-proof` observes USDC `Transfer` logs to the commerce
  address. `funded` is true only with a seen Transfer. Not a faucet.

### Changed
- `whoami` carries `readiness` (listed_on_registry stays false; funded is
  null until fund-proof). First-engagement docs lead with `adopt`.

## [0.11.0] - 2026-08-14

### Added
- Human operator viewer: `GET /ui` (HTML, excluded from hooks) and
  `GET /v1/operator` (JSON snapshot). `POST /v1/operator/enroll` writes the
  local account from loopback only. Plane visa is stripped from GET.
- `POST /v1/trust` scores caller-supplied independently verified audits.
- `Ledger.reconcile_against_chain` — report-only RPC classify.

### Changed
- Constitution 2.7: G9, G10, G11 closed. G12 remains open (bonds are not
  escrowed on payment rails).
- `survival_report` is `surviving` only against an auditor publication.
- `/v1/hooks` 1.4: POST `/v1/trust`.
- Tightened agent-facing docs (AGENTS.md, README, STATUS, VISION, CONTRIBUTING)
  without dropping commands, invariants, honesty bounds, or field notes.
- `plane_bootstrap.bootstrap` is a thin wrapper around
  `bootstrap_economy(..., stipend=1000)`.
- `/v1/hooks` 1.3: operator snapshot + loopback enroll.
- `actions/download-artifact` pin 7.0.0 → 8.0.1 (SHA).

## [0.10.0] - 2026-08-14

### Added
- Plugin-and-play agent account: `veritas-agent enroll` / `whoami` / `skills`
  bind plane identity (DID + visa), commerce wallet, plane VAAT, and
  interest-mapped catalog skills into one local `account.json`. `init`/`up`
  enroll a default account when none exists. MCP tool `whoami` reads it.
  Unknown interests stay unmapped.

### Changed
- `/v1/hooks` 1.2: `veritas-agent` description covers enroll; MCP `whoami`;
  durable store for the local account.
- Single plane roster: `plane_bootstrap.DEFAULT_ROSTER` is
  `agent_economy.FULL_ROSTER` (includes `researcher`).
- First-engagement docs (`AGENTS.md`, README, `llms.txt`) lead with enroll.
- Satellite clone paths retired; canonical tree is this repository.

### Removed
- Anthropic/Claude authorship trailers, vendor CLI examples, host temp
  paths, `CLAUDE.md` (use `AGENTS.md`), and local model-pin settings.

## [0.9.1] - 2026-08-09

Review-driven cleanup, debloat and polish: a six-territory adversarial
review of the whole repository, then fixes.

### Fixed
- **Buyer CLIs crashed on every real invocation**: `veritas-diligence` and
  `veritas-buy` passed `resolver=None` into the SSRF guard (TypeError), and
  the crash's exit 1 read as a seller-failed verdict. Every test injected a
  resolver, so the suite stayed green — found by running the installed CLI.
- Live mode with a settleable-but-domain-unverified network (10 of 12) now
  fails closed as `misconfigured` instead of 500ing every paid request and
  `/.well-known/x402`.
- `DEFAULT_FACILITATOR` single-sourced on the only facilitator this codebase
  has settled through (`https://x402.org/facilitator`); the bootstrap and
  the unblock probe no longer name a never-exercised counterparty, and the
  probe reads the env names the money path actually reads.
- Top-up replay during a replay-store outage now serves a retriable 503
  instead of a false 409 "already used"; settlement-failed top-up bodies
  carry the registered `error` code; payment blocks expose both `settled`
  and `success` on every path.
- `/metrics` 404/401 and log-proof errors now use codes at their registered
  statuses (`not_found` / `unauthorized` added to `/v1/errors`).
- Served JSON Schema gains the `license` / `attribution` / `observed`
  evidence properties the pipeline has always emitted; `notary.observe`
  provenance registered; `veritas-ops revenue` degrades structurally instead
  of crashing when the ledger is unreachable.
- Metering docstring example now prices `duckduckgo_instant_answer` (the
  name requests actually report); copying the old example made every request
  permanently UNPRICED.

### Changed
- `/v1/hooks` 1.1: corrected exit-code maps for `veritas-money-loop` and
  `veritas-verify` (2 = could-not-check, never "error"), registered the
  metrics bearer and `Retry-After` headers.
- Verdict-bearing CLIs exit 3 on usage errors (argparse's 2 collided with
  the semantic "unverifiable"); `veritas-agent` provision output is JSON;
  `veritas-server` / `veritas-mcp` answer `--help` instead of booting.
- Notarize traffic counted as `veritas_notarize_total` (was research);
  request-counter label cardinality bounded via the hooks registry.
- Release workflow restructured: build once, publish the GitHub release
  (artifacts + this file's section as notes) from a job that never sees the
  OIDC token; PyPI publish runs only when a maintainer sets the
  `PYPI_TRUSTED_PUBLISHER=configured` repository variable.

### Removed
- `veritas/bayesian.py` (nothing imported it; package metadata no longer
  advertises "Bayesian updating" — completing the 2026-08-05 retraction),
  the never-instantiated schema dataclasses, the unreachable retrieval
  fallback seam, `free_retrieve`, dead x402/ops/notary code.
- Stale root docs `ANALYSIS.md`, `WORKFLOW.md`, `DISTRIBUTABLE.md`,
  `LIVE_PAYMENTS.md` (they still claimed Bayesian updating and "no
  settlement ever"); `JIT_PACKET.md` / `ZK_WALLET.md` moved to
  `docs/design/`.

### Honesty
- All settlements to date are operator-run testnet arcs; count and evidence
  live at `docs/program/STATE.md` (header) and `docs/program/fable/settlement/`.
  Mainnet: none. Buyers we did not operate: none. PyPI: not yet published.

## [0.9.0] - 2026-08-09

North star + integration registry + first live product arcs (PRs #134-#142).

### Added
- **VISION.md** (root): the single north star; program docs point at it.
- **`GET /v1/hooks`** (constitution 2.5, A28): machine-readable integration
  registry — every HTTP route, MCP tool, CLI exit-code contract, payment
  header and durable store; states plainly that no push delivery exists.
- Buyer journey CLI (`veritas-buy`), Stage-1 status in `veritas-agent
  status`, catalog seed (#136).
- Honest refusal class for research-receipt re-fetch
  (`receipt_not_refetchable`, #139).

### Live evidence (operator-run, Base Sepolia, chain-confirmed)
- First composed money loop (`veritas-money-loop` exit 0), first live buyer
  journey (4/4 diligence checks), first live session-commerce loop
  (SIWx → x402 top-up settle → credit-paid research), first live
  evidence-notary arc (paid notarize → attestation → pack → independent-key
  audit CONFIRMED → survival report → Merkle inclusion). Evidence:
  `docs/program/fable/settlement/`.

## [0.8.1] - 2026-08-08

### Added
- **N1.5** Completed observe/notarize envelopes include `evidence_log.inclusion_proof` so peers verify Merkle membership offline without `GET /v1/log/proof`.

### Honesty
- Still operator-local log (not public CT, not on-chain)
- On-chain settlements at release time: **0**; G9 still open; not a new PyPI publish by itself

## [0.8.0] - 2026-08-08

Agent-to-agent commerce **substrate** cut: notary spine + dogfood 1–5 + G9 design.

### Added

- **N0** Evidence notary core: SSRF-safe observe, `POST /v1/notarize`, inv.3 credits parity
- **N1.1** Optional EIP-191 attestation of EvidenceRecord bound fields
- **N1.2** Free `POST /v1/attestations/verify` + MCP `verify_attestation`
- **P7 product** Origin re-fetch on `POST /v1/verify` (`url`+hash or `request_id`)
- **N1.3** Portable EvidencePack (`pack_hash`) + free `POST /v1/packs/verify`
- **N1.4** Operator-local Merkle evidence log + inclusion proofs (`/v1/log*`)
- **G9 design** Fail-closed `veritas-ops reconcile-chain` / `veritas.chain_reconcile` (gap still open)
- **Dogfood cycles 1 and 5** cold first-boot + ecosystem participant (2–4 already present)

### Honesty (not claimed in 0.8.0)

- On-chain settlements at release time: **0**
- Constitution gap **G9** remains open until operators configure RPC and production uses it
- Package **not** published to PyPI by this bump alone (release workflow needs Trusted Publishing)
- Multi-billion A2A revenue is direction only, not measured

### Upgrade notes

- Single-sourced version: `veritas.__version__` is `0.8.0`
- Discovery/llms advertise notarize, attestations, packs, evidence log surfaces

## [0.7.0]

Prior baseline (credits/SIWx, supply-chain pins, ops ledger). See git history.
