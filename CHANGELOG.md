# Changelog

## [0.8.1] - 2026-08-08

### Added
- **N1.5** Completed observe/notarize envelopes include `evidence_log.inclusion_proof` so peers verify Merkle membership offline without `GET /v1/log/proof`.

### Honesty
- Still operator-local log (not public CT, not on-chain)
- On-chain settlements: **0**; G9 still open; not a new PyPI publish by itself
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

- On-chain settlements from this codebase: **0**
- Constitution gap **G9** remains open until operators configure RPC and production uses it
- Package **not** published to PyPI by this bump alone (release workflow needs Trusted Publishing)
- Multi-billion A2A revenue is direction only, not measured

### Upgrade notes

- Single-sourced version: `veritas.__version__` is `0.8.0`
- Discovery/llms advertise notarize, attestations, packs, evidence log surfaces

## [0.7.0]

Prior baseline (credits/SIWx, supply-chain pins, ops ledger). See git history.
