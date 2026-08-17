# Veritas — Delivery roadmap

> **Sequencing only.** Current measured state is `STATUS.md`. Resume /
> NEXT is `docs/program/STATE.md`. The 2026-07-27 evaluation that used
> to occupy this file is git history — it named `veritas/bayesian.py` as
> live architecture and said settlement had never happened. Neither is
> true.

## Remaining (not a claim of completeness)

| Item | Owner | Notes |
|------|--------|--------|
| PyPI trusted publisher | Human | Workflow exists; `PYPI_TRUSTED_PUBLISHER` unset |
| Public seller URL for strangers | Human | Self-host TLS exists; no advertised host |
| Mainnet pay-to | Human | Testnet only; HOLD invent money |
| G13 | Code | Local simulator does not check nonce-unused or balance |
| O6 | Ops | Shared receipts/rate-limit across a real balancer unproven |
| O15 | Ops | SBOM checksummed, not signed |
| Calibration | Product | Unused; `passthrough_untrained` |

Phase sequencing that already landed (constitution, packaging, one engine,
settlement, G9 classify, G12 escrow primitive, peer A2A) is in `CHANGELOG.md`
and `STATUS.md`.
