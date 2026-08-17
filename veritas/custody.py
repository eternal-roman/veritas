"""Append-only hash-chain custody ledger (blockchain-style)."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .hashing import compute_content_hash
from .retention import is_expired
from .runtime import resolve_runtime_dir


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_record(record: dict) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def redact_receipt_for_wire(record: dict[str, Any]) -> dict[str, Any]:
    """Strip a research question from a receipt before it leaves the process.

    Origin URLs stay: ``POST /v1/verify`` re-fetches them. A free-text
    question is the buyer's, and GET /v1/receipts is unauthenticated (L6).
    Legacy on-disk receipts that still carry a question are redacted here
    so an upgrade does not keep serving them.
    """
    out = dict(record)
    query = out.get("query")
    if isinstance(query, str) and query and not query.startswith(("http://", "https://")):
        out.pop("query", None)
        out["query_redacted"] = True
        if "query_hash" not in out:
            out["query_hash"] = compute_content_hash(query)
    return out


@dataclass
class CustodyEvent:
    event_type: str          # names are defined at their emit sites (pipeline.py, notary/observe.py)
    actor: str
    timestamp: str
    prev_hash: str | None
    payload: dict[str, Any]
    event_hash: str = ""

    def compute_hash(self) -> str:
        data = {
            "event_type": self.event_type,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "payload": self.payload,
        }
        return _hash_record(data)


class CustodyLedger:
    """Append-only ledger. Any mutation of past events breaks the chain."""

    def __init__(self):
        self.events: list[CustodyEvent] = []

    def append(self, event_type: str, actor: str, payload: dict[str, Any]) -> CustodyEvent:
        prev_hash = self.events[-1].event_hash if self.events else None
        event = CustodyEvent(
            event_type=event_type,
            actor=actor,
            timestamp=_now(),
            prev_hash=prev_hash,
            payload=payload,
        )
        event.event_hash = event.compute_hash()
        self.events.append(event)
        return event

    def verify_chain(self) -> bool:
        if not self.events:
            return True
        for i, event in enumerate(self.events):
            if event.event_hash != event.compute_hash():
                return False
            if i == 0:
                if event.prev_hash is not None:
                    return False
            else:
                if event.prev_hash != self.events[i - 1].event_hash:
                    return False
        return True

    def root_hash(self) -> str | None:
        return self.events[-1].event_hash if self.events else None

    def to_list(self) -> list[dict[str, Any]]:
        return [asdict(e) for e in self.events]


def verify_chain_records(events: list[dict[str, Any]]) -> bool:
    """Verify a chain that was serialised earlier (e.g. loaded from a receipt).

    Lets a buying agent re-run our integrity check against stored JSON without
    reconstructing CustodyEvent objects.
    """
    if not events:
        return True
    prev_hash = None
    for record in events:
        rebuilt = CustodyEvent(
            event_type=record.get("event_type", ""),
            actor=record.get("actor", ""),
            timestamp=record.get("timestamp", ""),
            prev_hash=record.get("prev_hash"),
            payload=record.get("payload", {}),
        )
        if rebuilt.compute_hash() != record.get("event_hash"):
            return False
        if record.get("prev_hash") != prev_hash:
            return False
        prev_hash = record.get("event_hash")
    return True


def _atomic_write(path: Path, text: str) -> None:
    """Write a receipt so a reader never sees a half-written one.

    `write_text` truncates in place: a crash mid-write leaves a receipt that
    parses as nothing, and the receipt is precisely the artifact a buyer
    relies on once the response is gone. Write to a sibling temporary file,
    fsync it, then rename — rename within a directory is atomic on POSIX, so
    a reader sees the old complete file or the new complete file.
    """
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


#: A request id we would actually mint: uuid4, or a caller-supplied id in the
#: same shape. Deliberately an allowlist. The ids reaching `load` come from
#: `GET /v1/receipts/{request_id}`, i.e. straight off the wire, and the old
#: code interpolated them into a filesystem path. Starlette will not match a
#: path parameter containing "/", which made the hole invisible on Linux — but
#: "\" is a separator on Windows and is not a URL separator, so
#: `GET /v1/receipts/..%5Csecrets` arrived intact and read a file one
#: directory up. Any *.json the process could open was readable by an
#: unauthenticated caller, and the agent's own `wallet.keystore.json` is one.
_SAFE_REQUEST_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def is_safe_request_id(request_id: object) -> bool:
    """True when this id can be used as a filename with no further escaping.

    Rejects separators of every flavour, drive letters, UNC prefixes, leading
    dots and the empty string, so no input can name a file outside the receipt
    directory. `..` cannot pass: the first character must be alphanumeric.
    """
    return isinstance(request_id, str) and _SAFE_REQUEST_ID.match(request_id) is not None


class ReceiptPresence(str, Enum):
    """What `lookup` knows about a request id.

    `present` — body on disk and loadable.
    `gone`    — we once held it and retention deleted it (tombstone remains).
    `unknown` — never seen, or the id is not a safe filename.
    """

    PRESENT = "present"
    GONE = "gone"
    UNKNOWN = "unknown"


class CustodyStore:
    """Durable custody receipts.

    An in-memory ledger that dies with the request cannot be audited after the
    fact, which defeats the point of custody: the buyer's verification step in
    the workflow happens *after* the response is returned. Receipts are written
    as JSON so a result stays checkable for its retention window.

    When that window ends, `prune` deletes the body and leaves a durable
    tombstone so `GET /v1/receipts/{id}` can answer 410 Gone rather than
    collapsing "we deleted this" into 404 "never existed". Tombstones are never
    pruned: re-deleting them would reintroduce the 410→404 collapse.
    """

    def __init__(self, base_dir: str | None = None):
        runtime = resolve_runtime_dir(base_dir)
        self.base_dir = runtime / "receipts"
        # Sibling of receipts, not a child: a recursive wipe of the receipt
        # directory must not take the tombstones with it.
        self.tombstone_dir = runtime / "receipt_tombstones"

    def save(self, result: dict[str, Any]) -> dict[str, Any]:
        query = result.get("query")
        record: dict[str, Any] = {
            "request_id": result.get("request_id"),
            "status": result.get("status"),
            "custody_root": result.get("custody_root"),
            "custody_valid": result.get("custody_valid"),
            "evidence_hashes": [e.get("content_hash") for e in result.get("evidence", [])],
            "stored_at": _now(),
        }
        # L6: a research question is the buyer's business. Persist a hash
        # so the receipt still binds to what was asked; persist the
        # plaintext only when it is an origin URL (notarize refetch).
        if isinstance(query, str) and query:
            record["query_hash"] = compute_content_hash(query)
            if query.startswith(("http://", "https://")):
                record["query"] = query
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            # The write side takes the same guard as the read side: ids are
            # server-minted today, but a store that validates only on read is
            # one refactor away from writing outside its directory.
            path = self._receipt_path(record["request_id"])
            if path is None:
                raise ValueError("unsafe request_id")
            _atomic_write(path, json.dumps(record, indent=2))
            # A re-saved id is live again; drop any prior gone mark.
            tomb = self._tombstone_path(record["request_id"])
            if tomb is not None:
                tomb.unlink(missing_ok=True)
            record["persisted"] = True
        except ValueError:
            record["persisted"] = False
            record["error"] = "receipt_not_persisted_unsafe_request_id"
        except OSError as exc:
            # Never fail a paid request because the disk is unavailable; report
            # honestly that the receipt is not durable. Exception type only:
            # the message names server filesystem paths and this record is
            # served to buyers as the custody receipt.
            record["persisted"] = False
            record["error"] = f"receipt_not_persisted_{type(exc).__name__}"
        return record

    def _contained_path(self, directory: Path, request_id: object, suffix: str) -> Path | None:
        """Filename under `directory` for a safe request id, or None.

        Same two guards as the original receipt path helper: allowlist first,
        then containment after realpath, so no wire id can name a file outside
        the intended directory on any platform. Does not create directories:
        lookup must not mkdir on attacker-controlled ids.
        """
        if not is_safe_request_id(request_id):
            return None
        name = os.path.basename(f"{request_id}{suffix}")
        # realpath on a not-yet-created directory still yields a stable parent
        # path on every platform we support; missing files just fail the open.
        base = os.path.realpath(directory)
        candidate = os.path.realpath(os.path.join(base, name))
        # Compare as normalised strings with the separator appended: a bare
        # prefix test would accept a sibling directory whose name merely starts
        # with ours (".../receipts_public").
        if not candidate.startswith(base + os.sep):
            return None
        if os.path.dirname(candidate) != base or os.path.basename(candidate) != name:
            return None
        return Path(candidate)

    def _receipt_path(self, request_id: object) -> Path | None:
        """The path a receipt id names, or None if it does not name one."""
        return self._contained_path(self.base_dir, request_id, ".json")

    def _tombstone_path(self, request_id: object) -> Path | None:
        """The path a tombstone for this id would occupy, or None if unsafe."""
        return self._contained_path(self.tombstone_dir, request_id, ".json")

    def lookup(self, request_id: str) -> ReceiptPresence:
        """Classify an id as present, gone (pruned), or unknown (never seen).

        Unsafe ids are unknown: they never name a receipt we would mint, so
        they are not "gone" either. Path guards still run on every branch.
        """
        path = self._receipt_path(request_id)
        if path is not None and path.is_file():
            return ReceiptPresence.PRESENT
        tomb = self._tombstone_path(request_id)
        if tomb is not None and tomb.is_file():
            return ReceiptPresence.GONE
        return ReceiptPresence.UNKNOWN

    def load(self, request_id: str) -> dict[str, Any] | None:
        # Resolve before opening, never after: a check that runs after the read
        # has already leaked the file.
        path = self._receipt_path(request_id)
        if path is None:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def prune(self, cutoff: datetime | str) -> dict[str, int]:
        """Delete receipt bodies older than `cutoff`; leave durable tombstones.

        Returns counts only. Unparseable `stored_at` values are skipped, not
        deleted. Tombstones already on disk are never removed. Not for the
        request path — call from ops on a schedule.
        """
        if isinstance(cutoff, str):
            from .retention import parse_utc

            parsed = parse_utc(cutoff)
            if parsed is None:
                raise ValueError(f"unusable prune cutoff: {cutoff!r}")
            cutoff_dt = parsed
        else:
            cutoff_dt = cutoff
            if cutoff_dt.tzinfo is None:
                cutoff_dt = cutoff_dt.replace(tzinfo=timezone.utc)
            else:
                cutoff_dt = cutoff_dt.astimezone(timezone.utc)

        deleted = 0
        tombstoned = 0
        skipped = 0
        archived = 0
        if not self.base_dir.is_dir():
            return {"deleted": 0, "tombstoned": 0, "skipped": 0, "archived": 0}

        try:
            self.tombstone_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return {"deleted": 0, "tombstoned": 0, "skipped": 0, "archived": 0}

        for path in list(self.base_dir.iterdir()):
            if not path.is_file() or not path.name.endswith(".json"):
                continue
            if path.name.startswith("."):
                continue
            request_id = path.name[: -len(".json")]
            if not is_safe_request_id(request_id):
                skipped += 1
                continue
            # Refuse to act on a path that fails containment for this id —
            # same guard as load/lookup.
            if self._receipt_path(request_id) is None:
                skipped += 1
                continue
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                skipped += 1
                continue
            if not is_expired(record.get("stored_at"), cutoff_dt):
                skipped += 1
                continue
            tomb_path = self._tombstone_path(request_id)
            if tomb_path is None:
                skipped += 1
                continue
            marker = {
                "request_id": request_id,
                "stored_at": record.get("stored_at"),
                "pruned_at": _now(),
                "status": "gone",
            }
            from .archive import archive_enabled, archive_receipt

            if archive_enabled():
                try:
                    archive_receipt(record)
                    archived += 1
                except OSError:
                    # Configured archive failed: keep the live copy.
                    skipped += 1
                    continue
            try:
                _atomic_write(tomb_path, json.dumps(marker, indent=2))
                path.unlink(missing_ok=True)
            except OSError:
                skipped += 1
                continue
            deleted += 1
            tombstoned += 1
        return {
            "deleted": deleted,
            "tombstoned": tombstoned,
            "skipped": skipped,
            "archived": archived,
        }
