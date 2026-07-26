# Veritas Status — Adversarial Review Cycle

## Why the product currently fails to be useful to agents

1. **Low research value**: Retrieval remains limited. The claims that come out are often generic. A competent agent can produce similar or better answers itself with standard search tools.
2. **No proven quality delta**: There is no public, reproducible demonstration that Veritas is more accurate, better calibrated, or more reliable than a strong DIY research loop.
3. **Custody and Bayesian machinery decorate weak content**: The epistemic machinery is real, but it is currently applied to low-signal outputs. Agents pay for useful research, not for beautiful metadata around weak research.
4. **Calibration is unproven**: Likelihood ratios are still heuristic.
5. **Payment and discovery path is incomplete in practice**: Agents cannot yet discover, pay, and receive high-value results in a single fluid flow.

## What this cycle fixed

- Added a real, runnable evaluation harness (`evaluations/harness.py`) that measures custody validity, basic fidelity signals, and refusal behavior.
- Expanded tests to cover the harness.
- Kept the core contracts (hash, custody, Bayesian, refusal) strict.
- Updated this STATUS with the ruthless diagnosis so no one can claim the product is further along than it is.

## Remaining holes (still open)

- Production multi-source retrieval and grounded claim synthesis.
- Calibrated likelihood model.
- Side-by-side evaluation numbers against a strong baseline.
- Live x402 settlement.
- Content-addressable long-term evidence store.

Until the research *content* is demonstrably better or more trustworthy than what agents can produce themselves, the product will not be used at scale. The architecture is no longer the bottleneck; the quality of the research output is.

## Design rule going forward

Never claim usefulness that the evaluation harness cannot support. Prefer refusal and honest STATUS over impressive but empty demos.
