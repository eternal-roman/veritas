"""Buyer-side counterparty diligence.

The central claim under test is the buyer-side form of the distinction this
service sells: UNVERIFIABLE is not FAIL, exactly as `unavailable` is not
`no_evidence`. Both refuse a payment, because the gate is fail-closed, but a
buyer answers them differently.
"""

from __future__ import annotations

import pytest

from veritas.diligence import DiligencePolicy, Verdict, assess

PAY_TO = "0x" + "11" * 20
OTHER_PAY_TO = "0x" + "22" * 20
ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # USDC on Base
SEPOLIA_ASSET = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"  # USDC on Base Sepolia


def _accepts(pay_to=PAY_TO, amount="10000", asset=ASSET, network="eip155:8453"):
    return {
        "scheme": "exact",
        "network": network,
        "asset": asset,
        "payTo": pay_to,
        "maxAmountRequired": amount,
        "resource": "https://seller.test/v1/research",
        "extra": {"name": "USD Coin", "version": "2"},
    }


def _discovery(**kw):
    return {"x402Version": 1, "accepts": [_accepts(**kw)]}


def _challenge(**kw):
    return {"x402Version": 1, "accepts": [_accepts(**kw)]}


def _constitution(gaps=None, articles=None):
    """Shaped like veritas.constitution.build_constitution() output."""
    return {
        "constitution_version": "2.2",
        "articles": articles if articles is not None else [
            {
                "id": "A1", "title": "One engine", "statement": "One engine.",
                "scope": "service", "evidence_level": "L1",
                "enforcement": [{
                    "kind": "test",
                    "pointer": "tests/test_integration.py::test_control_plane_uses_shared_engine",
                }],
            },
            {
                "id": "A16", "title": "Portable reputation",
                "statement": "Reputation should become portable.",
                "scope": "venue", "evidence_level": "L0",
                "enforcement": [], "promoted_by": "ROADMAP Phase 4.3",
            },
        ],
        "known_gaps": gaps if gaps is not None else [
            {"id": "G10", "article": "A11", "status": "open",
             "description": "The trust score is self-reported."},
        ],
    }


def _trust():
    return {
        "overall": None,
        "recommendation": "UNPROVEN",
        "basis": {
            "min_samples": 10,
            "score_source": "independent_audits",
        },
    }


def _all(**over):
    kw = {"challenge": _challenge(), "discovery": _discovery(),
          "constitution": _constitution(), "trust": _trust()}
    kw.update(over)
    return kw


# -- the central discipline -------------------------------------------------


def test_missing_documents_are_unverifiable_not_failed():
    report = assess(**_all(discovery=None, constitution=None, trust=None))
    assert report.verdict == Verdict.UNVERIFIABLE
    assert report.verdict != Verdict.FAIL
    assert not report.passed


def test_an_observed_defect_outranks_a_missing_observation():
    """FAIL dominates UNVERIFIABLE: something we saw beats something we didn't."""
    report = assess(challenge=_challenge(pay_to=OTHER_PAY_TO),
                    discovery=_discovery(pay_to=PAY_TO),
                    constitution=None, trust=None)
    assert report.verdict == Verdict.FAIL


def test_a_consistent_seller_passes():
    report = assess(**_all())
    assert report.verdict == Verdict.PASS
    assert report.passed


# -- check 1: challenge/discovery agreement ---------------------------------


def test_a_challenge_billing_an_unadvertised_address_fails():
    report = assess(**_all(challenge=_challenge(pay_to=OTHER_PAY_TO)))
    assert report.verdict == Verdict.FAIL
    assert any("pay_to" in r for r in report.reasons)


def test_a_challenge_charging_more_than_advertised_fails():
    report = assess(**_all(challenge=_challenge(amount="99999")))
    assert report.verdict == Verdict.FAIL
    assert any("amount" in r for r in report.reasons)


def test_a_challenge_charging_less_than_advertised_passes():
    """Undercharging is not fraud against the buyer, so the check is one-sided."""
    report = assess(**_all(challenge=_challenge(amount="5000")))
    assert report.verdict == Verdict.PASS


def test_a_challenge_on_an_unadvertised_network_fails():
    """A different network must carry that network's own USDC, or the entry is
    invalid for an unrelated reason and the check never gets to compare."""
    report = assess(**_all(
        challenge=_challenge(network="eip155:84532", asset=SEPOLIA_ASSET)))
    assert report.verdict == Verdict.FAIL
    assert any("network" in r for r in report.reasons)


def test_an_internally_invalid_challenge_is_unverifiable_not_failed():
    """An entry naming an asset that is not that chain's USDC cannot be parsed
    into comparable parameters, so we did not observe a contradiction — we
    failed to look. That is UNVERIFIABLE, and reporting it as FAIL would be
    the exact dishonesty this module exists to refuse."""
    report = assess(**_all(challenge=_challenge(network="eip155:84532")))
    assert report.verdict == Verdict.UNVERIFIABLE


def test_address_comparison_is_case_insensitive():
    """EVM addresses differing only in hex casing are the same address."""
    report = assess(**_all(challenge=_challenge(pay_to=PAY_TO.upper().replace("0X", "0x"))))
    assert report.verdict == Verdict.PASS


def test_an_unparseable_challenge_is_unverifiable_not_failed():
    report = assess(**_all(challenge={"accepts": [{"scheme": "nonsense"}]}))
    assert report.verdict == Verdict.UNVERIFIABLE


# -- check 2: register integrity --------------------------------------------


def test_an_article_claiming_enforcement_without_a_pointer_fails():
    bad = _constitution()
    bad["articles"][0]["enforcement"] = []
    report = assess(**_all(constitution=bad))
    assert report.verdict == Verdict.FAIL
    assert any("A1" in r for r in report.reasons)


def test_an_aspirational_article_carrying_enforcement_fails():
    """L0 means not enforced. Claiming both ways is an incoherent register."""
    bad = _constitution()
    bad["articles"][1]["enforcement"] = [{"kind": "test", "pointer": "tests/x.py::y"}]
    report = assess(**_all(constitution=bad))
    assert report.verdict == Verdict.FAIL
    assert any("A16" in r for r in report.reasons)


def test_a_constitution_with_no_enforced_articles_fails():
    bare = _constitution(articles=[
        {"id": "A1", "title": "Trust us", "statement": "Trust us.",
         "scope": "venue", "evidence_level": "L0", "enforcement": [],
         "promoted_by": "someday"},
    ])
    report = assess(**_all(constitution=bare))
    assert report.verdict == Verdict.FAIL


# -- check 5: a seller claiming perfection ----------------------------------


def test_a_seller_declaring_no_gaps_fails():
    """An empty defect register is evidence of concealment, not of quality."""
    report = assess(**_all(constitution=_constitution(gaps=[])))
    assert report.verdict == Verdict.FAIL
    assert any("gap" in r.lower() for r in report.reasons)


def test_a_register_with_only_closed_gaps_fails():
    """Every gap closed and none open is the same claim of perfection."""
    closed_only = _constitution(gaps=[
        {"id": "G1", "article": "A14", "status": "closed", "description": "fixed"},
    ])
    report = assess(**_all(constitution=closed_only))
    assert report.verdict == Verdict.FAIL


# -- check 4: self-report disclosure ----------------------------------------


def test_a_bare_trust_number_without_disclosure_fails():
    undisclosed = {"overall": 99.0, "recommendation": "RECOMMENDED", "basis": {}}
    report = assess(**_all(trust=undisclosed))
    assert report.verdict == Verdict.FAIL
    assert any("independent" in r.lower() for r in report.reasons)


def test_unproven_with_disclosure_passes():
    """Publishing UNPROVEN honestly beats publishing a flattering number."""
    report = assess(**_all())
    assert report.verdict == Verdict.PASS


# -- policy -----------------------------------------------------------------


def test_policy_can_waive_a_check():
    undisclosed = {"overall": 99.0, "recommendation": "RECOMMENDED", "basis": {}}
    report = assess(**_all(trust=undisclosed),
                    policy=DiligencePolicy(require_trust_self_disclosure=False))
    assert report.verdict == Verdict.PASS


def test_min_enforced_articles_is_configurable():
    report = assess(**_all(), policy=DiligencePolicy(min_enforced_articles=99))
    assert report.verdict == Verdict.FAIL


# -- contract ---------------------------------------------------------------


@pytest.mark.parametrize("garbage", ["", 0, [], "not-a-dict", {"accepts": "no"},
                                     {"accepts": []}, None, 3.14, True])
def test_assess_never_raises_on_garbage(garbage):
    """Failures are results, never control-flow exceptions."""
    report = assess(challenge=garbage, discovery=garbage,
                    constitution=garbage, trust=garbage)
    assert report.verdict in (Verdict.FAIL, Verdict.UNVERIFIABLE)
    assert not report.passed


def test_report_is_serialisable_with_a_reason_per_check():
    body = assess(**_all()).to_dict()
    assert body["verdict"] == Verdict.PASS
    assert len(body["checks"]) >= 4
    for check in body["checks"]:
        assert check["name"] and check["verdict"] and check["detail"]


def test_reasons_are_empty_when_everything_passes():
    assert assess(**_all()).reasons == ()


def test_every_check_names_itself_in_the_report():
    names = {c["name"] for c in assess(**_all()).to_dict()["checks"]}
    assert "challenge_matches_discovery" in names
    assert "register_integrity" in names
    assert "gap_register_present" in names
    assert "trust_self_disclosure" in names


# -- the venue's own reference implementation -------------------------------


def test_veritas_own_constitution_passes_its_own_bar():
    """The service publishing this bar must clear it.

    If this fails it is a finding about Veritas, not about the test.
    """
    from veritas.constitution import build_constitution

    report = assess(
        constitution=build_constitution(),
        policy=DiligencePolicy(require_challenge_matches_discovery=False,
                               require_trust_self_disclosure=False),
    )
    assert report.verdict == Verdict.PASS, report.reasons


def test_veritas_own_trust_document_passes_its_own_bar():
    from veritas.trust import score_service

    report = assess(
        trust=score_service().to_dict(),  # UNPROVEN, independent source
        policy=DiligencePolicy(require_challenge_matches_discovery=False,
                               require_constitution=False,
                               require_gap_register=False),
    )
    assert report.verdict == Verdict.PASS, report.reasons
