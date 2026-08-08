"""Append-only hash-chain custody ledger (blockchain-style)."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_record(record: dict) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class CustodyEvent:
    event_type: str          # created | transformed | verified | reviewed | updated
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


class CustodyStore:
    """Durable custody receipts.

    An in-memory ledger that dies with the request cannot be audited after the
    fact, which defeats the point of custody: the buyer's verification step in
    the workflow happens *after* the response is returned. Receipts are written
    as JSON so a result stays checkable for its retention window.
    """

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or os.getenv("VERITAS_RUNTIME_DIR", ".veritas_runtime")) / "receipts"

    def save(self, result: dict[str, Any]) -> dict[str, Any]:
        record = {
            "request_id": result.get("request_id"),
            "query": result.get("query"),
            "status": result.get("status"),
            "custody_root": result.get("custody_root"),
            "custody_valid": result.get("custody_valid"),
            "evidence_hashes": [e.get("content_hash") for e in result.get("evidence", [])],
            "stored_at": _now(),
        }
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            # The write side takes the same guard as the read side: ids are
            # server-minted today, but a store that validates only on read is
            # one refactor away from writing outside its directory.
            path = self._receipt_path(record["request_id"])
            if path is None:
                raise ValueError("unsafe request_id")
            _atomic_write(path, json.dumps(record, indent=2))
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

    def _receipt_path(self, request_id: object) -> Path | None:
        """The path a receipt id names, or None if it does not name one.

        Two independent guards, because they fail differently. The allowlist
        rejects anything that is not a filename we would mint, and runs before
        a path exists at all. The containment check then re-derives the name
        with `basename` and requires the resolved result to sit directly in the
        receipt directory — so even if the pattern were later loosened, or a
        symlink were planted in the directory, the read still cannot leave it.
        """
        if not is_safe_request_id(request_id):
            return None
        name = os.path.basename(f"{request_id}.json")
        base = os.path.realpath(self.base_dir)
        candidate = os.path.realpath(os.path.join(base, name))
        # Compare as normalised strings with the separator appended: a bare
        # prefix test would accept a sibling directory whose name merely starts
        # with ours (".../receipts_public").
        if not candidate.startswith(base + os.sep):
            return None
        if os.path.dirname(candidate) != base or os.path.basename(candidate) != name:
            return None
        return Path(candidate)

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
