"""N0 EvidenceRecord: content_hash binds the full extracted body, not a snippet."""

from __future__ import annotations

from veritas.hashing import compute_content_hash, verify_content_hash
from veritas.notary.extract import EXTRACT_VERSION, extract_body
from veritas.notary.record import (
    RETENTION_CLASS_STANDARD,
    EvidenceRecord,
    build_evidence_record,
)


def test_record_content_hash_binds_full_extracted_body_not_snippet():
    """Anti-theater: hash is of the full body we store, not a truncated excerpt."""
    long_text = ("Paragraph of observed evidence. " * 80).strip()
    extracted = extract_body(long_text.encode("utf-8"), content_type="text/plain")
    record = build_evidence_record(
        url="https://example.com/page",
        extracted=extracted,
        observed_at="2026-08-08T12:00:00Z",
    )
    assert isinstance(record, EvidenceRecord)
    assert record.body == extracted.text
    assert len(record.body) > 500
    assert record.content_hash == compute_content_hash(record.body)
    ok, _ = verify_content_hash(record.body, record.content_hash)
    assert ok
    # A snippet-only hash would match the first N chars; full-body hash must not.
    snippet = record.body[:220]
    assert compute_content_hash(snippet) != record.content_hash


def test_record_stamps_extract_version_and_retention_class():
    extracted = extract_body(b"observed", content_type="text/plain")
    record = build_evidence_record(
        url="https://example.com/a",
        extracted=extracted,
        observed_at="2026-08-08T00:00:00Z",
    )
    assert record.extract_version == EXTRACT_VERSION
    assert record.retention_class == RETENTION_CLASS_STANDARD
    assert record.media_kind == "text"
    assert record.url == "https://example.com/a"
    assert record.observed_at == "2026-08-08T00:00:00Z"


def test_record_to_dict_is_json_friendly_and_includes_body():
    extracted = extract_body(
        b"<html><head><title>T</title></head><body><p>Body text here.</p></body></html>",
        content_type="text/html",
    )
    record = build_evidence_record(
        url="https://example.com/html",
        extracted=extracted,
        observed_at="2026-08-08T01:02:03Z",
        content_type="text/html; charset=utf-8",
        status_code=200,
        request_id="req-1",
    )
    payload = record.to_dict()
    assert payload["body"] == record.body
    assert payload["content_hash"] == record.content_hash
    assert payload["extract_version"] == EXTRACT_VERSION
    assert payload["title"] == "T"
    assert payload["status_code"] == 200
    assert payload["request_id"] == "req-1"
    assert payload["retention_class"] == RETENTION_CLASS_STANDARD
    # No non-JSON types
    assert all(
        isinstance(v, (str, int, type(None))) for v in payload.values()
    )


def test_tampered_body_fails_hash_check():
    extracted = extract_body(b"authentic observation", content_type="text/plain")
    record = build_evidence_record(
        url="https://example.com/x",
        extracted=extracted,
        observed_at="2026-08-08T00:00:00Z",
    )
    ok, detail = verify_content_hash(record.body + "x", record.content_hash)
    assert not ok
    assert detail["expected"] == record.content_hash


def test_custom_retention_class_is_recorded():
    extracted = extract_body(b"short", content_type="text/plain")
    record = build_evidence_record(
        url="https://example.com/e",
        extracted=extracted,
        observed_at="2026-08-08T00:00:00Z",
        retention_class="ephemeral",
    )
    assert record.retention_class == "ephemeral"


def test_build_is_deterministic_for_fixed_observed_at():
    extracted = extract_body(b"same", content_type="text/plain")
    a = build_evidence_record(
        url="https://example.com/s",
        extracted=extracted,
        observed_at="2026-01-01T00:00:00Z",
    )
    b = build_evidence_record(
        url="https://example.com/s",
        extracted=extracted,
        observed_at="2026-01-01T00:00:00Z",
    )
    assert a == b
    assert a.to_dict() == b.to_dict()
