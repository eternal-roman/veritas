"""Bayesian belief updating — library utility, not a product surface.

The served research path no longer publishes a posterior. Likelihoods here are
hand-typed and the hypothesis is a free-form query string, so the module was
removed from `pipeline.run_research` and from package-root exports / identity
capabilities. Kept only for callers who import it explicitly and accept those
limits. Prefer `veritas.support.support_report` for buyer-recomputable counts.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BayesianBelief:
    hypothesis: str
    prior: float = 0.5
    posterior: float = 0.5
    history: list[dict] = field(default_factory=list)

    def __post_init__(self):
        self.prior = max(1e-6, min(1.0 - 1e-6, self.prior))
        self.posterior = self.prior


def update_belief(
    belief: BayesianBelief,
    likelihood_if_true: float,
    likelihood_if_false: float,
    evidence_id: str,
    note: str = "",
) -> BayesianBelief:
    """
    Bayes update:
    P(H|E) = P(E|H) P(H) / P(E)
    where P(E) = P(E|H)P(H) + P(E|~H)P(~H)
    """
    p_h = belief.posterior
    p_not_h = 1.0 - p_h

    # Bound likelihoods to avoid numerical extremes
    likelihood_if_true = max(1e-6, min(1.0 - 1e-6, likelihood_if_true))
    likelihood_if_false = max(1e-6, min(1.0 - 1e-6, likelihood_if_false))

    p_e = likelihood_if_true * p_h + likelihood_if_false * p_not_h
    if p_e <= 0:
        return belief

    new_posterior = (likelihood_if_true * p_h) / p_e
    new_posterior = max(1e-6, min(1.0 - 1e-6, new_posterior))

    belief.history.append({
        "evidence_id": evidence_id,
        "prior": belief.posterior,
        "likelihood_if_true": likelihood_if_true,
        "likelihood_if_false": likelihood_if_false,
        "posterior": new_posterior,
        "note": note,
    })
    belief.posterior = new_posterior
    return belief
