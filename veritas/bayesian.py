"""Bayesian belief updating. Belief changes only on verified evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class BayesianBelief:
    hypothesis: str
    prior: float = 0.5
    posterior: float = 0.5
    history: List[dict] = field(default_factory=list)

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
