"""robots.txt fetch allowance: deny is never silently ignored.

Notary observation classifies whether a path may be fetched for a user-agent.
Missing robots is ``unknown`` (fail-closed for automated fetch), not assumed
allow. An operator override is an explicit class, not an implicit bypass.
"""

from __future__ import annotations

import pytest

from veritas.notary.robots import FetchClass, evaluate_robots, parse_robots

UA = "VeritasNotary/0.7.0"
PATH = "https://example.org/article/x"


def test_missing_robots_body_is_unknown_not_allowed():
    decision = evaluate_robots(None, PATH, UA)
    assert decision.allowance == FetchClass.UNKNOWN
    assert decision.may_fetch is False
    assert decision.assumed_allow is False


def test_empty_robots_allows_all():
    """RFC 9309: an empty robots file is treat-as-allow-all."""
    decision = evaluate_robots("", PATH, UA)
    assert decision.allowance == FetchClass.ALLOWED
    assert decision.may_fetch is True


def test_disallow_all_is_denied():
    body = "User-agent: *\nDisallow: /\n"
    decision = evaluate_robots(body, PATH, UA)
    assert decision.allowance == FetchClass.DENIED
    assert decision.may_fetch is False
    assert decision.assumed_allow is False


def test_robots_deny_is_not_silently_ignored():
    """A Disallow rule must surface as DENIED, not collapse to ALLOWED."""
    body = "User-agent: *\nDisallow: /private\n"
    decision = evaluate_robots(body, "https://example.org/private/secret", UA)
    assert decision.allowance == FetchClass.DENIED
    assert decision.may_fetch is False
    # Evidence the deny was observed, not dropped.
    assert decision.matched_rule is not None or "disallow" in decision.detail.lower()


def test_allowed_path_beside_disallow():
    body = "User-agent: *\nDisallow: /private\nAllow: /\n"
    decision = evaluate_robots(body, "https://example.org/public/page", UA)
    assert decision.allowance == FetchClass.ALLOWED
    assert decision.may_fetch is True


def test_specific_user_agent_rule_beats_star():
    body = (
        "User-agent: VeritasNotary\n"
        "Disallow: /blocked-for-us\n"
        "\n"
        "User-agent: *\n"
        "Disallow:\n"
    )
    denied = evaluate_robots(body, "https://example.org/blocked-for-us", UA)
    assert denied.allowance == FetchClass.DENIED
    allowed = evaluate_robots(body, "https://example.org/open", UA)
    assert allowed.allowance == FetchClass.ALLOWED


def test_explicit_override_is_its_own_class_and_records_underlying():
    body = "User-agent: *\nDisallow: /\n"
    decision = evaluate_robots(
        body,
        PATH,
        UA,
        override="operator_policy:notarize_despite_robots",
    )
    assert decision.allowance == FetchClass.OVERRIDE
    assert decision.may_fetch is True
    assert decision.underlying == FetchClass.DENIED
    assert decision.override == "operator_policy:notarize_despite_robots"
    # Override must not erase the fact of the deny.
    assert decision.underlying == FetchClass.DENIED


def test_override_requires_non_empty_reason():
    body = "User-agent: *\nDisallow: /\n"
    with pytest.raises(ValueError):
        evaluate_robots(body, PATH, UA, override="")
    with pytest.raises(ValueError):
        evaluate_robots(body, PATH, UA, override="   ")


def test_path_only_urls_are_accepted():
    body = "User-agent: *\nDisallow: /secret\n"
    decision = evaluate_robots(body, "/secret/x", UA)
    assert decision.allowance == FetchClass.DENIED


def test_parse_robots_exposes_raw_groups():
    body = "User-agent: *\nDisallow: /a\nAllow: /a/public\n"
    rules = parse_robots(body)
    assert rules is not None
    # Pure parse: no network, no silent default to "open internet".
    decision = rules.evaluate(PATH.replace("article/x", "a/hidden"), UA)
    assert decision.allowance == FetchClass.DENIED


def test_to_dict_carries_allowance_and_never_hides_deny():
    body = "User-agent: *\nDisallow: /\n"
    d = evaluate_robots(body, PATH, UA).to_dict()
    assert d["allowance"] == FetchClass.DENIED
    assert d["may_fetch"] is False
    assert d["assumed_allow"] is False
    assert d["user_agent"] == UA


def test_whitespace_only_body_is_empty_allow_all():
    decision = evaluate_robots("\n\n  \n", PATH, UA)
    assert decision.allowance == FetchClass.ALLOWED


def test_comments_only_robots_is_allow_all():
    body = "# crawl if you like\n# no rules\n"
    decision = evaluate_robots(body, PATH, UA)
    assert decision.allowance == FetchClass.ALLOWED
