"""Declared licence labels must classify reuse without silent permission.

A notary that stores body text must tell a buyer whether redistribution is
safe. Missing or unknown licences are a first-class class — never assumed
permissive — matching the product rule already held for retrieval evidence.
"""

from __future__ import annotations

import pytest

from veritas.notary.license import (
    ReuseClass,
    classify_license,
    unknown_license,
)


def test_missing_licence_is_unknown_not_permitted():
    label = classify_license(None)
    assert label.reuse == ReuseClass.UNKNOWN
    assert label.id == "unknown"
    assert label.assumed_permissive is False
    assert label.may_reuse is False


def test_empty_and_blank_declarations_are_unknown():
    for declared in ({}, {"id": ""}, {"id": "  "}, "", "   "):
        label = classify_license(declared)
        assert label.reuse == ReuseClass.UNKNOWN, declared
        assert label.may_reuse is False


def test_unknown_id_stays_explicit_never_permissive():
    label = classify_license({"id": "Some-Vendor-Proprietary-Thing"})
    assert label.reuse == ReuseClass.UNKNOWN
    assert label.id == "Some-Vendor-Proprietary-Thing"
    assert label.assumed_permissive is False
    assert label.may_reuse is False


def test_unknown_license_helper_matches_retrieval_honesty_shape():
    label = unknown_license()
    d = label.to_dict()
    assert d["id"] == "unknown"
    assert d["url"] is None
    assert "note" in d and d["note"]
    assert d["reuse"] == ReuseClass.UNKNOWN
    assert d.get("assumed_permissive") is not True


def test_cc0_is_permitted_reuse():
    label = classify_license({"id": "CC0-1.0", "url": "https://creativecommons.org/publicdomain/zero/1.0/"})
    assert label.reuse == ReuseClass.PERMITTED
    assert label.may_reuse is True
    assert label.attribution_required is False


def test_cc_by_sa_requires_attribution():
    label = classify_license("CC-BY-SA-4.0")
    assert label.reuse == ReuseClass.ATTRIBUTION
    assert label.may_reuse is True
    assert label.attribution_required is True
    assert label.url and "creativecommons.org" in label.url


def test_cc_by_is_attribution():
    label = classify_license({"id": "CC-BY-4.0"})
    assert label.reuse == ReuseClass.ATTRIBUTION
    assert label.attribution_required is True
    assert label.may_reuse is True


def test_permissive_osi_licences_are_permitted():
    for spdx in ("MIT", "Apache-2.0", "BSD-3-Clause"):
        label = classify_license(spdx)
        assert label.reuse == ReuseClass.PERMITTED, spdx
        assert label.may_reuse is True


def test_all_rights_reserved_is_forbidden():
    label = classify_license("all-rights-reserved")
    assert label.reuse == ReuseClass.FORBIDDEN
    assert label.may_reuse is False
    assert label.attribution_required is False


def test_non_commercial_is_restricted_not_silently_free():
    label = classify_license("CC-BY-NC-4.0")
    assert label.reuse == ReuseClass.RESTRICTED
    # Commercial re-sale of the body is not free; buyer must decide.
    assert label.may_reuse is False


def test_string_id_and_dict_id_agree():
    a = classify_license("CC-BY-4.0")
    b = classify_license({"id": "CC-BY-4.0"})
    assert a.reuse == b.reuse
    assert a.id == b.id


def test_to_dict_is_json_stable_and_includes_reuse_class():
    label = classify_license({"id": "CC-BY-SA-4.0"})
    d = label.to_dict()
    assert d["id"] == "CC-BY-SA-4.0"
    assert d["reuse"] == ReuseClass.ATTRIBUTION
    assert d["attribution_required"] is True
    assert isinstance(d["may_reuse"], bool)


def test_whitespace_and_case_on_known_ids_normalize():
    label = classify_license("  cc-by-4.0  ")
    assert label.id == "CC-BY-4.0"
    assert label.reuse == ReuseClass.ATTRIBUTION


@pytest.mark.parametrize(
    "declared",
    [
        None,
        "unknown",
        {"id": "unknown"},
        {"id": "Totally-Made-Up-1.0"},
    ],
)
def test_unknown_never_reports_assumed_permissive(declared):
    label = classify_license(declared)
    assert label.assumed_permissive is False
    assert label.reuse == ReuseClass.UNKNOWN
