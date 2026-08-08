"""Declared licence labels → reuse allowance.

A notary that stores body text must not leave redistribution risk implicit.
Silence about a licence would let a buyer assume reuse is safe; this module
makes the gap a first-class class: ``unknown`` is never treated as permissive.

Classification is of *declared* labels only. No silent scrape theater: we do
not invent a licence from page content heuristics. Unknown IDs stay unknown.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


# Reuse classes are plain strings so they serialise cleanly into records.
class ReuseClass:
    """How the declared licence treats redistribution of the stored body."""

    PERMITTED = "permitted"  # free reuse (CC0, permissive OSI)
    ATTRIBUTION = "attribution"  # reuse OK when attribution is kept
    RESTRICTED = "restricted"  # non-commercial / limited — not free for resale
    FORBIDDEN = "forbidden"  # all-rights-reserved / no redistribution
    UNKNOWN = "unknown"  # not established; never assume permissive


# Known SPDX / short ids we can classify without network. Unlisted → UNKNOWN.
# url is the canonical deed / SPDX reference when one is standard.
_KNOWN: dict[str, tuple[str, str | None, bool]] = {
    # (reuse_class, url, attribution_required)
    "CC0-1.0": (
        ReuseClass.PERMITTED,
        "https://creativecommons.org/publicdomain/zero/1.0/",
        False,
    ),
    "CC-BY-4.0": (
        ReuseClass.ATTRIBUTION,
        "https://creativecommons.org/licenses/by/4.0/",
        True,
    ),
    "CC-BY-SA-4.0": (
        ReuseClass.ATTRIBUTION,
        "https://creativecommons.org/licenses/by-sa/4.0/",
        True,
    ),
    "CC-BY-NC-4.0": (
        ReuseClass.RESTRICTED,
        "https://creativecommons.org/licenses/by-nc/4.0/",
        True,
    ),
    "CC-BY-NC-SA-4.0": (
        ReuseClass.RESTRICTED,
        "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        True,
    ),
    "MIT": (
        ReuseClass.PERMITTED,
        "https://spdx.org/licenses/MIT.html",
        False,
    ),
    "Apache-2.0": (
        ReuseClass.PERMITTED,
        "https://www.apache.org/licenses/LICENSE-2.0",
        False,
    ),
    "BSD-3-Clause": (
        ReuseClass.PERMITTED,
        "https://spdx.org/licenses/BSD-3-Clause.html",
        False,
    ),
    "all-rights-reserved": (ReuseClass.FORBIDDEN, None, False),
    "unknown": (ReuseClass.UNKNOWN, None, False),
}

# Normalise common aliases buyers and sources actually ship.
_ALIASES: dict[str, str] = {
    "cc0": "CC0-1.0",
    "cc-zero": "CC0-1.0",
    "cc-by": "CC-BY-4.0",
    "cc-by-sa": "CC-BY-SA-4.0",
    "cc-by-nc": "CC-BY-NC-4.0",
    "apache-2": "Apache-2.0",
    "apache2": "Apache-2.0",
    "bsd": "BSD-3-Clause",
    "arr": "all-rights-reserved",
    "all rights reserved": "all-rights-reserved",
}


@dataclass(frozen=True)
class LicenseLabel:
    """A classified licence declaration, ready to stamp on an EvidenceRecord."""

    id: str
    reuse: str
    url: str | None = None
    note: str | None = None
    attribution_required: bool = False
    assumed_permissive: bool = False

    @property
    def may_reuse(self) -> bool:
        """Whether redistribution is classified as free enough to proceed.

        RESTRICTED and FORBIDDEN and UNKNOWN all refuse. Buyers that accept
        non-commercial-only bodies must decide outside this gate.
        """
        return self.reuse in (ReuseClass.PERMITTED, ReuseClass.ATTRIBUTION)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "note": self.note,
            "reuse": self.reuse,
            "attribution_required": self.attribution_required,
            "assumed_permissive": self.assumed_permissive,
            "may_reuse": self.may_reuse,
        }


def unknown_license(
    *,
    note: str = "licence not established; check the source before redistributing",
) -> LicenseLabel:
    """The explicit unknown label. Compatible in spirit with retrieval.UNKNOWN_LICENSE."""
    return LicenseLabel(
        id="unknown",
        reuse=ReuseClass.UNKNOWN,
        url=None,
        note=note,
        attribution_required=False,
        assumed_permissive=False,
    )


def _normalize_id(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in _ALIASES:
        return _ALIASES[lowered]
    # Preserve canonical case for known SPDX keys (case-insensitive match).
    for key in _KNOWN:
        if key.lower() == lowered:
            return key
    return text


def _extract_id(declared: str | Mapping[str, Any] | None) -> str | None:
    if declared is None:
        return None
    if isinstance(declared, str):
        text = declared.strip()
        return text or None
    if isinstance(declared, Mapping):
        value = declared.get("id")
        if value is None:
            return None
        text = str(value).strip()
        return text or None
    return None


def classify_license(declared: str | Mapping[str, Any] | None) -> LicenseLabel:
    """Classify a declared licence into a reuse allowance.

    Missing, blank, or unrecognised IDs become ``unknown`` with
    ``assumed_permissive=False``. Known labels never upgrade unknown silence
    into permission.
    """
    raw_id = _extract_id(declared)
    if raw_id is None:
        return unknown_license()

    license_id = _normalize_id(raw_id)
    if not license_id:
        return unknown_license()

    # Caller-supplied url/note win when present on a dict declaration.
    supplied_url: str | None = None
    supplied_note: str | None = None
    if isinstance(declared, Mapping):
        url_val = declared.get("url")
        if url_val is not None and str(url_val).strip():
            supplied_url = str(url_val).strip()
        note_val = declared.get("note")
        if note_val is not None and str(note_val).strip():
            supplied_note = str(note_val).strip()

    known = _KNOWN.get(license_id)
    if known is None:
        return LicenseLabel(
            id=license_id,
            reuse=ReuseClass.UNKNOWN,
            url=supplied_url,
            note=supplied_note
            or "licence id not in the notary catalogue; treat as not established",
            attribution_required=False,
            assumed_permissive=False,
        )

    reuse, default_url, attribution_required = known
    note: str | None = supplied_note
    if reuse == ReuseClass.UNKNOWN and note is None:
        note = "licence not established; check the source before redistributing"
    elif reuse == ReuseClass.FORBIDDEN and note is None:
        note = "redistribution forbidden under the declared licence"
    elif reuse == ReuseClass.RESTRICTED and note is None:
        note = "reuse is restricted (e.g. non-commercial); not free for resale"

    return LicenseLabel(
        id=license_id,
        reuse=reuse,
        url=supplied_url if supplied_url is not None else default_url,
        note=note,
        attribution_required=attribution_required,
        assumed_permissive=False,
    )


__all__ = [
    "LicenseLabel",
    "ReuseClass",
    "classify_license",
    "unknown_license",
]
