"""Canonical content hashing for Veritas evidence."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any


def normalize_content(text: str) -> str:
    """Deterministic normalization before hashing."""
    if not text:
        return ""
    text = str(text)
    text = text.encode("utf-8", errors="replace").decode("utf-8")
    text = unicodedata.normalize("NFC", text)
    text = text.lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def compute_content_hash(content: str) -> str:
    """Return sha256:<hex> of normalized content."""
    normalized = normalize_content(content)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def verify_content_hash(content: str, expected_hash: str) -> tuple[bool, dict[str, Any]]:
    """Verify content against a claimed hash."""
    if not expected_hash or not expected_hash.startswith("sha256:"):
        return False, {"valid": False, "error": "malformed_hash"}
    actual = compute_content_hash(content)
    valid = actual == expected_hash
    return valid, {
        "valid": valid,
        "expected": expected_hash,
        "actual": actual,
        "normalized_length": len(normalize_content(content)),
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
