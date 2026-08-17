# Changelog

## [Unreleased]

### Removed
- Research product and engine (`pipeline`, `retrieval`, `providers`,
  `synthesis`, zero-key retrieval, evaluation harness). `POST /v1/research`
  is 410 `product_removed`. Catalog pull is the sold SKU.

### Changed
- Honesty: README no longer advertises deleted JIT/hiding-wallet
  prototypes. `STATE.md` resume tip is `#163`. Identity-TLS design
  doc records issued/card/intro as shipped and pin-on-fetch as wired.
  `CONSTITUTION.md` enforcement lines match `constitution.py` (A11,
  A12, A13, A22, A23); the markdown sync test now requires every
  pointer. Adopt card name is Veritas. First-boot copy and cycle-1
  report drop `run_research`. README, identity, `/llms.txt`, and the
  package abstract describe the catalog seller, not a research API.
- Catalog: `GET /v1/signals` is latest-per-market and store-searchable
  (`q`). History is newest-first. Kalshi pull pages a cursor. A
  Polymarket search miss is empty, not an open-book dump. `veritas-ops
  signals-ingest` pulls a watchlist (`*` = bounded open book).
- A2A: `connect` / `pull-signals` pin the presented cert to the peer
  card fingerprint. No public CA. HTTPS without a `tls` block is
  `peer_tls_required` (LAN `--allow-local` excepted).
- Live `POST /v1/signals` is payment-gated (same price as notarize).
  GET catalog stays free. Credit refunds name `refund_rail: ledger_credit`.
  `/health` and `/v1/operator` report `store_mode` (unset/sqlite/postgres).
- CI runs dogfood cycles, catalog honesty, and the payment-model
  checker once each. Pytest no longer repeats those jobs. The payment-model
  mutant (charge-on-signer-failure) stays in pytest — CI's module run
  does not replace it. A1's `test_control_plane_uses_shared_engine` now
  walks HTTP and MCP onto the catalog engine.

### Removed
- Duplicate pytest wrappers for the harness and the payment-model
  enumeration, plus the five dogfood cycle re-runs.
- `test_product_worth` (humility report) and `test_unblock_probe`
  (leftover program probe). Existence tests keep landmass honesty only.
- Second product in the wheel: VAAT ledger, HMAC plane visas, org-cycle
  mesh runner, evolver CLI, block board, plane stock. Enroll is commerce
  wallet + did:pkh card only.
- Off-path prototypes: `zk_wallet`, JIT packets, self-calibrator, the
  unused `control_plane` entry. Local facilitator remains for G13.
- Unused `record_attempt` (hardcoded `$0.25`) on the local simulator.
  Identity defaults now follow `DEFAULT_PRICE` / `DEFAULT_NETWORK`
  (`$0.01` on Base Sepolia), not the retracted `$0.25` / mainnet pair.
- Program theater (role ticks, CURRENT stamps, Rhai org workflows,
  Superpowers diligence plan). Tenets stay in `AGENTS.md` / `MIND.md`.
- Duplicate status files (`DOME.md`, `fable/STATE.md`). `STATUS.md` is
  measured state; `docs/program/STATE.md` is resume only.
- Tests for the removed wheel/theater surfaces, the empty
  `test_known_gaps.py` register, duplicate integration smokes, and an
  untracked copy-hygiene walk. Constitution-pinned tests stay.
- CI import of `veritas.autonomous.control_plane` (module deleted).

### Added
- Identity-bound self-hosted HTTPS (`serve --tls`), optional LAN mDNS
  browse, and signed public-URL introductions (`GET /v1/peer/introductions`).
  TLS key is not the commerce key. Not a registry, not a public network.
- Self-host A2A peer connect (`veritas.peer.v1`): `GET /v1/peer` advertises
  this node; `veritas-agent connect` / `peers` / `pull-signals` talk to
  another self-hosted agent. No central network, no public peer list.
  Local/LAN needs `--allow-local`. Cloud metadata stays refused.
- Local facilitator recovers the EIP-712 signer of an EIP-3009
  `transferWithAuthorization` (constitution G2 closed, 2.9). Forged,
  expired, and incomplete authorizations fail closed. Balance and
  nonce-unused stay on-chain and are not claimed.
- Signal analysis (`veritas.signals.analyze.v1`) and
  `GET /v1/signals/history`. Arithmetic on stored venue prices, not a
  forecast. POST `/v1/signals` returns `analysis` with the snapshots.
- Wikipedia retrieval uses the official MediaWiki Extracts API
  (`prop=extracts&explaintext=1`) instead of the REST lead-paragraph
  summary. ``exintro`` is omitted (MediaWiki treats a present boolean
  as true, so ``exintro=0`` still returned the lead). Each title is
  fetched on its own request because TextExtracts will not return
  more than one full-article extract. Served-path research
  re-observes search hits through `notary.observe`. Unobserved
  Serper/DDG hits are labelled `search_snippet`.
- Operator deploy runbook: `docs/deploy/PUBLIC_HOST.md`, `deploy/Caddyfile`,
  `deploy/fly.toml`. No public host is claimed.
- VCAE (`veritas.escrow`, `veritas.escrow.v1`): EIP-3009 authorization
  is the lock. `escrow_bond` / `escrow_stake` persist; `settle_forfeit`
  submits through the existing facilitator after a fired challenge. A
  facilitator refusal leaves the lock collectable. HTTP:
  `POST /v1/escrow`, `GET /v1/escrow/{lock_id}`,
  `POST /v1/escrow/{lock_id}/release` (never submits),
  `POST /v1/escrow/{lock_id}/forfeit` (live facilitator required).
  `veritas-ops escrow-sweep` / `escrow <lock_id>`. Not a vault contract.
  Mainnet collect unproven.
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
- Adopt sell step: public TLS is optional for stranger discovery;
  local/LAN A2A works with `--allow-local`.
- Identity and product copy: prediction-market signals and x402
  commerce first. Research is an observe primitive and does not
  auto-attach a warranty.
- ROADMAP Part I no longer names the removed Bayesian module as live
  architecture. Changelog Unreleased is one Added / one Changed block.
- Constitution 2.8: G12 closed. Warranties that carry an EIP-3009 lock
  are `bond_binding: eip3009_authorization` and collectable via
  `settle_forfeit`. Warranties that omit a lock stay
  `signed_commitment_not_escrow`.
- Runtime directory (O5): default is
  `$XDG_DATA_HOME/veritas/runtime` or `~/.local/share/veritas/runtime`,
  never cwd-relative `.veritas_runtime`. `veritas-agent` binds
  `{base-dir}/runtime`. `/readyz` is 503 if the directory cannot be
  written. A pre-existing `./.veritas_runtime` is still honoured.
- Receipts (L6): research questions persist as `query_hash` only. GET
  `/v1/receipts/{id}` never returns a free-text question. Origin URLs
  stay so notarize re-fetch works.
- Retrieval (R10): Serper is not registered in free mode unless
  `VERITAS_SERPER_IN_FREE_MODE` is set.
- VCAE HTTP: GET strips `authorization.signature`. Forfeit re-runs
  `evaluate_challenge` on the supplied warranty + deliverable. Release
  is loopback-only.
- `veritas-buy --content` reports a real hash match (the previous
  `bool((ok, meta))` was always true).
- Kalshi pull never returns the unfiltered open book for a
  non-matching query. `SignalStore.put` returns None on write failure.
- `/v1/hooks` 1.8: receipt query redaction, escrow GET/release/forfeit
  honesty, runtime-dir wording.
- VCAE collect claims `locked` → `settling` before the facilitator
  submit so two agents cannot both submit the same nonce. A refusal
  reverts to `locked`; success or indeterminate stays `forfeited`.
- Kalshi integer fields are cents (`last_price=1` is 1¢). Dollar
  fields win when present. Amount mismatch on an escrowed warranty is
  refused before the lock is written.
- Escrow/signals HTTP error envelopes carry category codes only
  (no exception text on the wire).
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
