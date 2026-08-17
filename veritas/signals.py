"""Prediction-market signals. Markets price claims; this service does not.

The research arm was a placeholder for "what is true." That is the wrong
product for a multi-agent commercial venue: facts that can be traded
already have a first-class price on Kalshi and Polymarket. This module
pulls those prices, stores the snapshot through the normal evidence
channel, and refuses to interpret them as truth.

A stored signal attests: at ``observed_at``, venue V advertised these
outcome prices for this market. It does not attest that the event
happened, that the book is complete, or that a later resolution matches.

Venues (public read, no trading, no keys):

* Polymarket Gamma  ``https://gamma-api.polymarket.com``
* Kalshi Trade API  ``https://external-api.kalshi.com/trade-api/v2``

Hosts are allowlisted. Fetches go through ``require_http_url`` and
``assert_public_destination``. Redirects are re-checked against the same
allowlist. A caller cannot steer us at an internal address by supplying
a venue name.

Writes never raise into a paid path: a full disk or a dead venue is a
miss, not a crash. A search miss is empty, not an unfiltered book dump.
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from veritas import __version__
from veritas.evidence_store import EvidenceStore, is_safe_content_hash
from veritas.hashing import compute_content_hash
from veritas.runtime import resolve_runtime_dir
from veritas.safeurl import UnsafeUrlError, assert_public_destination, require_http_url
from veritas.store import StoreUnavailable, connect_target, parse_database_url

METHOD = "veritas.signals.v1"
USER_AGENT = f"veritas-signals/{__version__}"
FETCH_TIMEOUT_SECONDS = 8.0
MAX_MARKETS = 8
MAX_PAGES = 5
MAX_LIST = 100
WATCHLIST_ENV = "VERITAS_SIGNALS_WATCHLIST"
OPEN_BOOK_TOKEN = "*"

VENUE_POLYMARKET = "polymarket"
VENUE_KALSHI = "kalshi"
VENUES = frozenset({VENUE_POLYMARKET, VENUE_KALSHI})

#: Public read hosts only. Anything else is refused before DNS.
VENUE_ENDPOINTS: dict[str, dict[str, str]] = {
    VENUE_POLYMARKET: {
        "host": "gamma-api.polymarket.com",
        "search": "https://gamma-api.polymarket.com/public-search",
        "markets": "https://gamma-api.polymarket.com/markets",
    },
    VENUE_KALSHI: {
        "host": "external-api.kalshi.com",
        "markets": "https://external-api.kalshi.com/trade-api/v2/markets",
        "events": "https://external-api.kalshi.com/trade-api/v2/events",
    },
}

ALLOWED_HOSTS = frozenset(spec["host"] for spec in VENUE_ENDPOINTS.values())

_DB_FILENAME = "signals.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signal_snapshots (
    content_hash TEXT PRIMARY KEY,
    venue        TEXT NOT NULL,
    market_id    TEXT NOT NULL,
    question     TEXT,
    body         TEXT NOT NULL,
    observed_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS signal_snapshots_by_venue_market
    ON signal_snapshots(venue, market_id);
CREATE INDEX IF NOT EXISTS signal_snapshots_by_observed
    ON signal_snapshots(observed_at);
"""


class SignalsError(ValueError):
    """A pull or store step could not proceed."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clamp_price(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    if number < 0.0:
        return 0.0
    if number > 1.0:
        # Kalshi often reports cents (0–100); treat (1, 100] as cents.
        if number <= 100.0:
            number = number / 100.0
        else:
            return None
    return round(number, 6)


def _clamp_cents(value: Any) -> float | None:
    """Kalshi integer fields are cents in [0, 100]. ``1`` is 1¢, not 100%."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number < 0.0 or number > 100.0:
        return None
    return round(number / 100.0, 6)


def _kalshi_yes_price(item: dict[str, Any]) -> float | None:
    """Prefer ``*_dollars`` (0–1). Fall back to integer-cent fields."""
    for key in ("last_price_dollars", "yes_bid_dollars", "yes_ask_dollars"):
        raw = item.get(key)
        if raw is None or raw == "":
            continue
        priced = _clamp_price(raw)
        if priced is not None:
            return priced
    for key in ("last_price", "yes_bid", "yes_ask"):
        raw = item.get(key)
        if raw is None or raw == "":
            continue
        priced = _clamp_cents(raw)
        if priced is not None:
            return priced
    return None


def _body_without_hash(signal: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in signal.items() if k != "content_hash"}


def canonical_signal(signal: dict[str, Any]) -> str:
    return json.dumps(
        _body_without_hash(signal),
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )


def hash_signal(signal: dict[str, Any]) -> str:
    return compute_content_hash(canonical_signal(signal))


def _allowed_url(url: str) -> str:
    try:
        require_http_url(url)
        host = urllib.parse.urlsplit(url).hostname or ""
        if host.lower() not in ALLOWED_HOSTS:
            raise SignalsError(f"venue_host_refused:{host}")
        return assert_public_destination(url)
    except UnsafeUrlError as exc:
        raise SignalsError(f"venue_url_refused:{type(exc).__name__}") from exc


class _AllowlistedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse a 3xx that would leave the venue allowlist."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            _allowed_url(newurl)
        except SignalsError as exc:
            raise urllib.error.URLError(str(exc)) from exc
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_open(request, timeout):
    opener = urllib.request.build_opener(_AllowlistedRedirectHandler())
    return opener.open(request, timeout=timeout)


def fetch_json(url: str, *, opener: Any = None) -> Any:
    """GET JSON from an allowlisted public venue. Never follows off-allowlist."""
    safe = _allowed_url(url)
    request = urllib.request.Request(
        safe,
        method="GET",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    open_url = opener or _default_open
    try:
        with open_url(request, timeout=FETCH_TIMEOUT_SECONDS) as response:  # nosec B310
            raw = response.read()
    except SignalsError:
        raise
    except UnsafeUrlError as exc:
        raise SignalsError(f"venue_url_refused:{type(exc).__name__}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SignalsError(f"venue_transport:{type(exc).__name__}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SignalsError("venue_body_unreadable") from exc


def _parse_maybe_json_list(value: Any) -> list[Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return [value]
    return value if isinstance(value, list) else []


def _normalize_polymarket(item: dict[str, Any], *, observed_at: str) -> dict[str, Any] | None:
    question = item.get("question") or item.get("title") or item.get("slug")
    if not isinstance(question, str) or not question.strip():
        return None
    market_id = str(item.get("id") or item.get("conditionId") or item.get("slug") or "")
    if not market_id:
        return None
    names = _parse_maybe_json_list(item.get("outcomes"))
    prices = _parse_maybe_json_list(item.get("outcomePrices"))
    outcomes = []
    for index, name in enumerate(names):
        if not isinstance(name, str):
            continue
        price = _clamp_price(prices[index] if index < len(prices) else None)
        outcomes.append({"name": name, "price": price})
    status = "open"
    if item.get("closed") is True or str(item.get("active")).lower() == "false":
        status = "closed"
    volume = item.get("volumeNum")
    if not isinstance(volume, (int, float)):
        volume = item.get("volume")
    return {
        "venue": VENUE_POLYMARKET,
        "market_id": market_id,
        "question": question.strip(),
        "outcomes": outcomes,
        "volume": volume,
        "close_time": item.get("endDate") or item.get("end_date_iso"),
        "status": status,
        "observed_at": observed_at,
        "source_url": (
            "https://gamma-api.polymarket.com/markets/"
            + urllib.parse.quote(market_id)
        ),
        "method": METHOD,
        "note": "market-implied prices, not a verdict",
    }


def _normalize_kalshi(item: dict[str, Any], *, observed_at: str) -> dict[str, Any] | None:
    ticker = item.get("ticker") or item.get("event_ticker")
    title = item.get("title") or item.get("yes_sub_title") or ticker
    if not isinstance(ticker, str) or not ticker:
        return None
    if not isinstance(title, str) or not title.strip():
        title = ticker
    yes = _kalshi_yes_price(item)
    no_price = None if yes is None else round(1.0 - yes, 6)
    status_raw = str(item.get("status") or "open").lower()
    if status_raw in {"open", "active", "initialized"}:
        status = "open"
    elif status_raw in {"settled", "finalized", "determined"}:
        status = "settled"
    else:
        status = "closed"
    return {
        "venue": VENUE_KALSHI,
        "market_id": ticker,
        "question": title.strip(),
        "outcomes": [
            {"name": "Yes", "price": yes},
            {"name": "No", "price": no_price},
        ],
        "volume": item.get("volume") or item.get("volume_fp"),
        "close_time": item.get("close_time") or item.get("expiration_time"),
        "status": status,
        "observed_at": observed_at,
        "source_url": (
            "https://external-api.kalshi.com/trade-api/v2/markets/"
            + urllib.parse.quote(ticker)
        ),
        "method": METHOD,
        "note": "market-implied prices, not a verdict",
    }


def _markets_from_polymarket_payload(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    markets: list[Any] = []
    events = payload.get("events")
    if isinstance(events, list):
        for event in events:
            if isinstance(event, dict) and isinstance(event.get("markets"), list):
                markets.extend(event["markets"])
    if not markets and isinstance(payload.get("markets"), list):
        markets = payload["markets"]
    return markets


def _finish_signals(raw_items: list[Any], *, venue_norm, limit: int) -> list[dict[str, Any]]:
    observed = _now()
    out: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        signal = venue_norm(item, observed_at=observed)
        if signal is None:
            continue
        signal["content_hash"] = hash_signal(signal)
        out.append(signal)
        if len(out) >= limit:
            break
    return out


def _kalshi_blob(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "ticker", "yes_sub_title", "subtitle", "event_ticker")
    ).lower()


def pull_polymarket(
    query: str,
    *,
    limit: int = MAX_MARKETS,
    opener: Any = None,
    dump_book: bool = False,
) -> list[dict[str, Any]]:
    """Search Polymarket. A miss is empty — never an unfiltered open book.

    ``dump_book=True`` is the explicit ingest path (watchlist ``*``).
    """
    spec = VENUE_ENDPOINTS[VENUE_POLYMARKET]
    cap = max(1, min(int(limit), MAX_MARKETS))
    text = (query or "").strip()
    if dump_book and not text:
        payload = fetch_json(
            f"{spec['markets']}?closed=false&limit={cap}",
            opener=opener,
        )
        markets = _markets_from_polymarket_payload(payload)
        return _finish_signals(markets, venue_norm=_normalize_polymarket, limit=cap)
    if not text:
        return []
    payload = fetch_json(
        f"{spec['search']}?q={urllib.parse.quote(text)}&limit={cap}",
        opener=opener,
    )
    markets = _markets_from_polymarket_payload(payload)
    return _finish_signals(markets, venue_norm=_normalize_polymarket, limit=cap)


def pull_kalshi(
    query: str,
    *,
    limit: int = MAX_MARKETS,
    opener: Any = None,
    dump_book: bool = False,
) -> list[dict[str, Any]]:
    """Page Kalshi open markets until ``limit`` matches or ``MAX_PAGES``.

    Client-side token filter. A miss is empty, not the open book, unless
    ``dump_book=True`` (watchlist ``*``).
    """
    spec = VENUE_ENDPOINTS[VENUE_KALSHI]
    cap = max(1, min(int(limit), MAX_MARKETS))
    tokens = {tok for tok in (query or "").lower().split() if len(tok) >= 2}
    if not dump_book and not tokens:
        return []
    raw_items: list[Any] = []
    cursor: str | None = None
    page_size = min(200, max(cap, 8))
    for _ in range(MAX_PAGES):
        url = f"{spec['markets']}?limit={page_size}&status=open"
        if cursor:
            url += f"&cursor={urllib.parse.quote(str(cursor))}"
        payload = fetch_json(url, opener=opener)
        page = payload.get("markets") if isinstance(payload, dict) else payload
        if not isinstance(page, list):
            page = []
        raw_items.extend(item for item in page if isinstance(item, dict))
        if not dump_book and tokens:
            matched = sum(
                1
                for item in raw_items
                if isinstance(item, dict)
                and any(tok in _kalshi_blob(item) for tok in tokens)
            )
            if matched >= cap:
                break
        elif dump_book and len(raw_items) >= cap:
            break
        cursor = payload.get("cursor") if isinstance(payload, dict) else None
        if not cursor or not page:
            break
    if dump_book:
        return _finish_signals(raw_items, venue_norm=_normalize_kalshi, limit=cap)
    filtered = [
        item
        for item in raw_items
        if isinstance(item, dict) and any(tok in _kalshi_blob(item) for tok in tokens)
    ]
    return _finish_signals(filtered, venue_norm=_normalize_kalshi, limit=cap)


def pull(
    query: str,
    *,
    venues: list[str] | None = None,
    limit: int = MAX_MARKETS,
    opener: Any = None,
    dump_book: bool = False,
) -> list[dict[str, Any]]:
    """Pull snapshots from the named venues. Unknown venues are refused.

    Each venue is capped separately so a Polymarket hit does not hide Kalshi.
    """
    text = (query or "").strip()
    if not dump_book and not text:
        raise SignalsError("query_empty")
    wanted = list(venues) if venues else [VENUE_POLYMARKET, VENUE_KALSHI]
    for venue in wanted:
        if venue not in VENUES:
            raise SignalsError(f"venue_unknown:{venue}")
    cap = max(1, min(int(limit), MAX_MARKETS))
    collected: list[dict[str, Any]] = []
    errors: list[str] = []
    for venue in wanted:
        try:
            if venue == VENUE_POLYMARKET:
                collected.extend(
                    pull_polymarket(
                        text, limit=cap, opener=opener, dump_book=dump_book
                    )
                )
            else:
                collected.extend(
                    pull_kalshi(text, limit=cap, opener=opener, dump_book=dump_book)
                )
        except SignalsError as exc:
            errors.append(f"{venue}:{exc}")
    if not collected and errors:
        raise SignalsError("venues_unavailable:" + ",".join(errors))
    return collected


def ingest(
    queries: list[str] | None = None,
    *,
    venues: list[str] | None = None,
    limit: int = MAX_MARKETS,
    opener: Any = None,
    store: SignalStore | None = None,
) -> dict[str, Any]:
    """Pull a watchlist into the catalog. ``*`` means the open-book dump.

    Queries come from ``queries`` or ``VERITAS_SIGNALS_WATCHLIST`` (comma
    separated). Empty watchlist is refused rather than inventing a universe.
    """
    wanted = [q.strip() for q in (queries or []) if isinstance(q, str) and q.strip()]
    if not wanted:
        raw = (os.getenv(WATCHLIST_ENV) or "").strip()
        wanted = [part.strip() for part in raw.split(",") if part.strip()]
    if not wanted:
        raise SignalsError("watchlist_empty")
    target = store or SignalStore()
    collected: list[dict[str, Any]] = []
    errors: list[str] = []
    for query in wanted:
        dump = query == OPEN_BOOK_TOKEN
        try:
            batch = pull(
                "" if dump else query,
                venues=venues,
                limit=limit,
                opener=opener,
                dump_book=dump,
            )
        except SignalsError as exc:
            errors.append(f"{query}:{exc}")
            continue
        collected.extend(batch)
    written = target.put_many(collected)
    return {
        "method": METHOD,
        "queries": wanted,
        "pulled": len(collected),
        "stored": written,
        "errors": errors,
        "note": "market-implied prices, not a verdict",
    }


class SignalStore:
    """Persist snapshots in the evidence store and a signals table."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = resolve_runtime_dir(base_dir)
        self.evidence = EvidenceStore(self.base_dir)

    def _connect(self):
        try:
            target = parse_database_url()
        except StoreUnavailable:
            target = None
        if target is not None:
            conn = connect_target(target)
            conn.executescript(_SCHEMA)
            return conn
        self.base_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(self.base_dir / _DB_FILENAME), timeout=10, isolation_level=None
        )
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        return conn

    def put(self, signal: dict[str, Any]) -> str | None:
        excerpt = canonical_signal(signal)
        digest = compute_content_hash(excerpt)
        try:
            stored_excerpt = self.evidence.put(
                digest, excerpt,
                url=signal.get("source_url") if isinstance(signal.get("source_url"), str) else None,
                title=signal.get("question") if isinstance(signal.get("question"), str) else None,
            )
        except Exception:
            return None
        if not stored_excerpt:
            return None
        conn = None
        try:
            conn = self._connect()
            conn.execute(
                "INSERT INTO signal_snapshots "
                "(content_hash, venue, market_id, question, body, observed_at) "
                "VALUES (?,?,?,?,?,?)"
                " ON CONFLICT(content_hash) DO UPDATE SET"
                " venue=excluded.venue, market_id=excluded.market_id,"
                " question=excluded.question, body=excluded.body,"
                " observed_at=excluded.observed_at",
                (
                    digest, signal.get("venue"), signal.get("market_id"),
                    signal.get("question"), excerpt,
                    signal.get("observed_at") or _now(),
                ),
            )
        except Exception:
            return None
        finally:
            if conn is not None:
                conn.close()
        return digest

    def put_many(self, signals: list[dict[str, Any]]) -> int:
        written = 0
        for signal in signals:
            if self.put(signal):
                written += 1
        return written

    def get(self, content_hash: str) -> dict[str, Any] | None:
        if not is_safe_content_hash(content_hash):
            return None
        record = self.evidence.get(content_hash)
        body: dict[str, Any] | None = None
        if record and isinstance(record.get("excerpt"), str):
            try:
                parsed = json.loads(record["excerpt"])
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                body = parsed
        if body is None:
            conn = None
            try:
                conn = self._connect()
                row = conn.execute(
                    "SELECT body FROM signal_snapshots WHERE content_hash = ?",
                    (content_hash,),
                ).fetchone()
            except Exception:
                return None
            finally:
                if conn is not None:
                    conn.close()
            if row is None:
                return None
            try:
                parsed = json.loads(row["body"])
            except (TypeError, json.JSONDecodeError):
                return None
            if not isinstance(parsed, dict):
                return None
            body = parsed
        body["content_hash"] = content_hash
        return body

    def list(
        self,
        *,
        venue: str | None = None,
        q: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Latest snapshot per (venue, market_id). Optional store-side ``q``."""
        cap = max(1, min(int(limit), MAX_LIST))
        needle = (q or "").strip().lower()
        sql = (
            "SELECT body, content_hash, venue, market_id, question, observed_at "
            "FROM ("
            " SELECT body, content_hash, venue, market_id, question, observed_at,"
            " ROW_NUMBER() OVER ("
            "  PARTITION BY venue, market_id ORDER BY observed_at DESC"
            " ) AS rn"
            " FROM signal_snapshots"
            ") ranked WHERE rn = 1"
        )
        params: list[Any] = []
        if venue:
            sql += " AND venue = ?"
            params.append(venue)
        sql += " ORDER BY observed_at DESC LIMIT ?"
        # Over-fetch when filtering in process so ``q`` still sees a catalog.
        params.append(cap if not needle else min(MAX_LIST, cap * 8))
        conn = None
        try:
            conn = self._connect()
            rows = conn.execute(sql, tuple(params)).fetchall()
        except Exception:
            return []
        finally:
            if conn is not None:
                conn.close()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                parsed = json.loads(row["body"])
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(parsed, dict):
                continue
            parsed["content_hash"] = row["content_hash"]
            if needle:
                blob = (
                    f"{parsed.get('question') or ''} "
                    f"{parsed.get('market_id') or ''}"
                ).lower()
                if needle not in blob:
                    continue
            out.append(parsed)
            if len(out) >= cap:
                break
        return out

    def history(
        self,
        *,
        venue: str,
        market_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Newest-first snapshots for one venue market. Arithmetic input, not a forecast."""
        if venue not in VENUES or not market_id:
            return []
        cap = max(1, min(int(limit), MAX_LIST))
        conn = None
        try:
            conn = self._connect()
            rows = conn.execute(
                "SELECT body, content_hash FROM signal_snapshots "
                "WHERE venue = ? AND market_id = ? "
                "ORDER BY observed_at DESC LIMIT ?",
                (venue, market_id, cap),
            ).fetchall()
        except Exception:
            return []
        finally:
            if conn is not None:
                conn.close()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                parsed = json.loads(row["body"])
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(parsed, dict):
                continue
            parsed["content_hash"] = row["content_hash"]
            out.append(parsed)
        return out


ANALYZE_METHOD = "veritas.signals.analyze.v1"


def _primary_price(outcomes: Any) -> float | None:
    """Yes-price if present, else the first numeric outcome. Not a forecast."""
    if not isinstance(outcomes, list):
        return None
    named = None
    first = None
    for item in outcomes:
        if not isinstance(item, dict):
            continue
        price = item.get("price")
        if not isinstance(price, (int, float)):
            continue
        if first is None:
            first = float(price)
        if str(item.get("name") or "").strip().lower() in {"yes", "y"}:
            named = float(price)
            break
    return named if named is not None else first


def analyze(signals: list[dict[str, Any]]) -> dict[str, Any]:
    """Arithmetic on stored venue prices. Not a forecast and not a verdict."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        key = str(signal.get("question") or signal.get("market_id") or "").strip().lower()
        if not key:
            continue
        grouped.setdefault(key, []).append(signal)
    markets: list[dict[str, Any]] = []
    for rows in grouped.values():
        points: list[dict[str, Any]] = []
        prices: list[float] = []
        for row in rows:
            price = _primary_price(row.get("outcomes"))
            points.append({
                "venue": row.get("venue"),
                "market_id": row.get("market_id"),
                "price": price,
                "observed_at": row.get("observed_at"),
                "content_hash": row.get("content_hash"),
            })
            if price is not None:
                prices.append(price)
        markets.append({
            "question": rows[0].get("question"),
            "n_snapshots": len(rows),
            "points": points,
            "price_min": min(prices) if prices else None,
            "price_max": max(prices) if prices else None,
            "price_mean": round(sum(prices) / len(prices), 6) if prices else None,
            "venue_disagreement": (
                round(max(prices) - min(prices), 6) if len(prices) >= 2 else None
            ),
        })
    return {
        "method": ANALYZE_METHOD,
        "n_signals": len(signals),
        "n_markets": len(markets),
        "markets": markets,
        "note": "arithmetic on stored venue prices; not a forecast and not a verdict",
    }


def as_evidence(signal: dict[str, Any]) -> dict[str, Any]:
    """Shape a stored snapshot as a custody evidence item.

    ``text`` is the human sentence the evidence hasher hashes. The structured
    snapshot lives under ``hash_signal`` in the evidence store — a
    different digest, on purpose: one hash, one body.
    """
    outcomes = signal.get("outcomes") or []
    priced = ", ".join(
        f"{o.get('name')}={o.get('price')}"
        for o in outcomes if isinstance(o, dict)
    )
    excerpt = (
        f"{signal.get('venue')} prices '{signal.get('question')}' "
        f"at {priced or 'n/a'} as of {signal.get('observed_at')} "
        f"(market {signal.get('market_id')}). Not a verdict."
    )
    return {
        "url": signal.get("source_url") or "",
        "title": signal.get("question") or signal.get("market_id"),
        "text": excerpt,
        "excerpt": excerpt,
        "content_hash": compute_content_hash(excerpt),
        "provider": signal.get("venue"),
        "provenance": "live_fetch",
        "relevance": 1.0,
        "license": {
            "id": "venue-terms",
            "url": None,
            "note": "snapshot of a public venue book; reuse subject to the venue's terms",
        },
    }
