# Changelog

## [Unreleased]

### Added
- Human operator viewer: `GET /ui` (HTML, excluded from hooks) and
  `GET /v1/operator` (JSON snapshot). `POST /v1/operator/enroll` writes the
  local account from loopback only. Plane visa is stripped from GET.

### Changed
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
