"""Dogfood cycles run as a dedicated CI job, not again under pytest.

What remains here is the claim the CI job cannot see: the scripts stay
offline, so their reports describe the product rather than this sandbox's
egress.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_no_dogfood_script_performs_an_outbound_request():
    """The cycles claim to make no network call. That claim is load-bearing:
    it is why their results describe the product rather than this sandbox's
    egress."""
    for name in (
        "dogfood_cycle1.py",
        "dogfood_cycle2.py",
        "dogfood_cycle3.py",
        "dogfood_cycle4.py",
        "dogfood_cycle5.py",
    ):
        source = (REPO / "scripts" / name).read_text(encoding="utf-8")
        for forbidden in ("urlopen(", "requests.get", "requests.post", "httpx.get"):
            assert forbidden not in source, f"{name} may reach the network via {forbidden}"
