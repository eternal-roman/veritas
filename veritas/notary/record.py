"""EvidenceRecord: what this service received at time T, with content_hash binding.

N0-E / N0-H: the record stores the full extracted body (not hash-and-discard
theater) and stamps the extract algorithm version. ``content_hash`` is always
``compute_content_hash(body)`` of that stored text so a buyer can re-verify
without trusting a truncated snippet.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from veritas.hashing import compute_content_hash
from veritas.notary.extract import EXTRACT_VERSION, ExtractedBody

# Default retention label for notarized evidence. Ops/policy may choose others;
# the class is recorded on the record so prune jobs do not guess.
RETENTION_CLASS_STANDARD = "standard"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class EvidenceRecord:
    """Observation of a URL at a point in time, body stored and hash-bound."""

    url: str
    observed_at: str
    content_hash: str
    body: str
    extract_version: str
    media_kind: str
    retention_class: str
    content_type: str | None = None
    status_code: int | None = None
    title: str | None = None
    request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_evidence_record(
    *,
    url: str,
    extracted: ExtractedBody,
    observed_at: str | None = None,
    retention_class: str = RETENTION_CLASS_STANDARD,
    content_type: str | None = None,
    status_code: int | None = None,
    title: str | None = None,
    request_id: str | None = None,
) -> EvidenceRecord:
    """Build a record whose content_hash binds the full extracted body.

    ``observed_at`` is injectable so tests (and later observe) can pin time;
    when omitted, wall clock is used once at construction.
    """
    body = extracted.text
    content_hash = compute_content_hash(body)
    resolved_title = title if title is not None else extracted.title
    return EvidenceRecord(
        url=url,
        observed_at=observed_at if observed_at is not None else _now(),
        content_hash=content_hash,
        body=body,
        extract_version=extracted.extract_version or EXTRACT_VERSION,
        media_kind=extracted.media_kind,
        retention_class=retention_class,
        content_type=content_type,
        status_code=status_code,
        title=resolved_title,
        request_id=request_id,
    )
