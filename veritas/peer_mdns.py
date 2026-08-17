"""Optional LAN mDNS advertise/browse for self-hosted Veritas peers.

Discovery only. Browse returns *candidate* URLs; ``veritas.peer.connect``
still applies the SSRF guard (``--allow-local`` is required for loopback
and RFC1918). This module never writes the local peer book and never
puts LAN addresses in TXT.

This is **not** the program Mesh Runner, not a DHT, and not a public
address book. The ``zeroconf`` extra is optional: missing it makes
``advertise`` / ``browse`` return a structured unavailable result
instead of raising. Install with ``pip install 'veritas-research[mdns]'``.
"""

from __future__ import annotations

import atexit
import ipaddress
import re
import socket
import threading
import time
from typing import Any
from urllib.parse import urlsplit

from veritas.peer import PEER_PATH, SCHEMA

SERVICE_TYPE = "_veritas._tcp.local."
CARD_PATH = PEER_PATH
UNAVAILABLE_NOTE = "optional extra: pip install 'veritas-research[mdns]'"

#: Cloud metadata endpoints. Never returned as candidates, even on LAN.
_METADATA_IPS = frozenset({
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
})

_LABEL_RE = re.compile(r"[^A-Za-z0-9-]+")

_LIVE: list[dict[str, Any]] = []


def _load_zeroconf() -> Any | None:
    try:
        import zeroconf
    except ImportError:
        return None
    return zeroconf


def mdns_available() -> bool:
    return _load_zeroconf() is not None


def _unavailable(error: str) -> dict[str, Any]:
    return {
        "ok": False,
        "unavailable": True,
        "code": "unavailable",
        "error": error,
        "peers": [],
        "note": UNAVAILABLE_NOTE,
    }


def _refused(error: str) -> dict[str, Any]:
    return {
        "ok": False,
        "unavailable": False,
        "code": "refused",
        "error": error,
        "peers": [],
    }


def service_txt(*, https: bool = False) -> dict[str, str]:
    """TXT records. Card path + schema only, plus an https flag.

    LAN addresses do not belong here (or in any public book).
    """
    return {
        "card": CARD_PATH,
        "schema": SCHEMA,
        "https": "1" if https else "0",
    }


def candidate_url(host: str, port: int, *, https: bool = False) -> str:
    """Build an http(s) candidate URL. Always includes the port."""
    scheme = "https" if https else "http"
    rendered = _render_host(host)
    return f"{scheme}://{rendered}:{int(port)}"


def _render_host(host: str) -> str:
    text = (host or "").strip()
    if text.startswith("[") and text.endswith("]"):
        return text
    try:
        ip = ipaddress.ip_address(_strip_zone(text))
    except ValueError:
        return text
    if ip.version == 6:
        return f"[{ip}]"
    return str(ip)


def _strip_zone(host: str) -> str:
    text = (host or "").strip()
    if text.startswith("[") and "]" in text:
        text = text[1:text.index("]")]
    if "%" in text:
        text = text.split("%", 1)[0]
    return text


def is_advertisable_address(address: str) -> bool:
    """True when ``address`` may appear in a browse candidate URL.

    Cloud metadata (169.254.169.254 and 100.100.100.200) and every
    link-local address are refused. Loopback and RFC1918 stay — connect
    still requires ``--allow-local`` before they are fetched.
    """
    text = _strip_zone(address)
    if not text:
        return False
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return True
    if ip in _METADATA_IPS or ip.is_link_local:
        return False
    if ip.is_unspecified or ip.is_multicast:
        return False
    return True


def filter_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop candidates whose URL host is metadata or link-local."""
    kept: list[dict[str, Any]] = []
    for row in candidates:
        if not isinstance(row, dict):
            continue
        url = row.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        host = urlsplit(url).hostname or ""
        if not is_advertisable_address(host):
            continue
        kept.append(row)
    return kept


def advertise_addresses(host: str) -> list[str]:
    """Resolve ``host`` to IPs that may be advertised. Never metadata."""
    text = (host or "").strip()
    if not text or text == "*":
        return _local_addresses()
    if text.lower() in {"localhost", "localhost.localdomain"}:
        return ["127.0.0.1"]
    try:
        ip = ipaddress.ip_address(_strip_zone(text))
    except ValueError:
        return _resolve_host(text)
    if ip.is_unspecified:
        return _local_addresses()
    rendered = str(ip)
    return [rendered] if is_advertisable_address(rendered) else []


def _resolve_host(host: str) -> list[str]:
    found: list[str] = []
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return []
    for info in infos:
        addr = info[4][0]
        if is_advertisable_address(addr) and addr not in found:
            found.append(addr)
    return found


def _local_addresses() -> list[str]:
    found = _resolve_host(socket.gethostname())
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("192.0.2.1", 80))
            addr = probe.getsockname()[0]
        finally:
            probe.close()
        if is_advertisable_address(addr) and addr not in found:
            found.append(addr)
    except OSError:
        pass
    if not found:
        found.append("127.0.0.1")
    return found


def _instance_label(name: str | None, port: int) -> str:
    raw = (name or "").strip() or f"veritas-{socket.gethostname()}-{int(port)}"
    cleaned = _LABEL_RE.sub("-", raw).strip("-")
    if not cleaned:
        cleaned = f"veritas-{int(port)}"
    return cleaned[:63]


def _service_name(label: str) -> str:
    if label.endswith(SERVICE_TYPE):
        return label if label.endswith(".") else f"{label}."
    return f"{label}.{SERVICE_TYPE}"


def _instance_from_service_name(full_name: str) -> str:
    text = (full_name or "").rstrip(".")
    suffix = SERVICE_TYPE.rstrip(".")
    if text.endswith(suffix):
        text = text[: -len(suffix)].rstrip(".")
    return text or full_name


def _decode_properties(properties: Any) -> dict[str, str]:
    if not isinstance(properties, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in properties.items():
        name = key.decode("utf-8", "replace") if isinstance(key, (bytes, bytearray)) else str(key)
        if value is None:
            out[name] = ""
        elif isinstance(value, (bytes, bytearray)):
            out[name] = value.decode("utf-8", "replace")
        else:
            out[name] = str(value)
    return out


def _https_from_properties(properties: dict[str, str], service_name: str) -> bool:
    flag = properties.get("https", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    if flag in {"0", "false", "no"}:
        return False
    label = _instance_from_service_name(service_name).lower()
    return label.endswith("-https")


def _info_addresses(info: Any) -> list[str]:
    parsed = getattr(info, "parsed_addresses", None)
    if callable(parsed):
        try:
            return [str(addr) for addr in parsed() if addr]
        except Exception:  # noqa: BLE001 - hostile/odd ServiceInfo must not raise
            pass
    out: list[str] = []
    for item in getattr(info, "addresses", None) or []:
        if isinstance(item, (bytes, bytearray)):
            raw = bytes(item)
            try:
                if len(raw) == 4:
                    out.append(socket.inet_ntoa(raw))
                else:
                    out.append(socket.inet_ntop(socket.AF_INET6, raw))
            except OSError:
                continue
        elif item:
            out.append(str(item))
    return out


def candidates_from_addresses(
    name: str,
    addresses: list[str],
    port: int,
    *,
    https: bool = False,
) -> list[dict[str, Any]]:
    """Build browse rows from a name + address list. Filters metadata."""
    label = _instance_from_service_name(name)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for address in addresses:
        if not is_advertisable_address(address):
            continue
        url = candidate_url(address, port, https=https)
        if url in seen:
            continue
        seen.add(url)
        rows.append({"name": label, "url": url, "https": bool(https)})
    return rows


def _candidates_from_info(info: Any) -> list[dict[str, Any]]:
    if info is None:
        return []
    name = str(getattr(info, "name", "") or "")
    port = int(getattr(info, "port", 0) or 0)
    if port < 1 or port > 65535:
        return []
    properties = _decode_properties(getattr(info, "properties", None))
    schema = properties.get("schema", "")
    if schema and schema != SCHEMA:
        return []
    https = _https_from_properties(properties, name)
    return candidates_from_addresses(
        name, _info_addresses(info), port, https=https
    )


def advertise(
    host: str,
    port: int,
    *,
    https: bool = False,
    name: str | None = None,
) -> dict[str, Any]:
    """Register ``_veritas._tcp`` on the LAN. Never raises.

    Missing ``zeroconf`` or a runtime mDNS failure returns a structured
    unavailable result. Metadata / link-local hosts are refused.
    """
    try:
        port_n = int(port)
    except (TypeError, ValueError):
        return _refused("invalid port")
    if port_n < 1 or port_n > 65535:
        return _refused("invalid port")

    addresses = advertise_addresses(host)
    if not addresses:
        return _refused("no advertisable addresses (metadata/link-local filtered)")

    zc_mod = _load_zeroconf()
    if zc_mod is None:
        return _unavailable("zeroconf is not installed")

    label = _instance_label(name, port_n)
    service_name = _service_name(label)
    txt = service_txt(https=https)
    try:
        info = zc_mod.ServiceInfo(
            SERVICE_TYPE,
            service_name,
            port=port_n,
            properties=txt,
            server=f"{label}.local.",
            parsed_addresses=addresses,
        )
        zc = zc_mod.Zeroconf()
        zc.register_service(info, allow_name_change=True)
    except Exception as exc:  # noqa: BLE001 - optional extra must not raise
        return _unavailable(f"mdns advertise failed: {type(exc).__name__}")

    live = {"zc": zc, "info": info, "name": service_name, "label": label}
    _LIVE.append(live)
    return {
        "ok": True,
        "unavailable": False,
        "name": label,
        "service_type": SERVICE_TYPE,
        "port": port_n,
        "https": bool(https),
        "addresses": list(addresses),
        "txt": dict(txt),
        "url": candidate_url(addresses[0], port_n, https=https),
    }


def unadvertise(name: str | None = None) -> None:
    """Unregister one advertisement, or all if ``name`` is omitted. Never raises."""
    wanted = None if name is None else _instance_from_service_name(str(name))
    remaining: list[dict[str, Any]] = []
    for live in _LIVE:
        label = str(live.get("label") or "")
        full = str(live.get("name") or "")
        if wanted is not None and wanted not in {label, _instance_from_service_name(full)}:
            remaining.append(live)
            continue
        zc = live.get("zc")
        info = live.get("info")
        if zc is not None and info is not None:
            try:
                zc.unregister_service(info)
            except Exception:  # noqa: BLE001
                pass
        if zc is not None:
            try:
                zc.close()
            except Exception:  # noqa: BLE001
                pass
    _LIVE[:] = remaining


def browse(*, timeout: float = 1.0) -> list[dict[str, Any]] | dict[str, Any]:
    """Browse LAN peers. Success is ``[{name, url, https}, ...]``.

    Missing ``zeroconf`` or a runtime mDNS failure returns a structured
    unavailable result and does not raise. Metadata IPs never appear.
    Candidates are not connected — ``veritas.peer.connect`` still applies
    SSRF (``--allow-local`` for loopback/RFC1918).
    """
    zc_mod = _load_zeroconf()
    if zc_mod is None:
        return _unavailable("zeroconf is not installed")

    try:
        wait = max(0.0, float(timeout))
    except (TypeError, ValueError):
        wait = 1.0

    found: dict[str, dict[str, Any]] = {}
    lock = threading.Lock()

    class _Listener:
        def add_service(self, zc: Any, type_: str, svc_name: str) -> None:
            try:
                info_timeout = max(200, int(wait * 1000))
                info = zc.get_service_info(type_, svc_name, timeout=info_timeout)
            except Exception:  # noqa: BLE001
                return
            for row in _candidates_from_info(info):
                with lock:
                    found[row["url"]] = row

        def remove_service(self, zc: Any, type_: str, svc_name: str) -> None:
            return None

        def update_service(self, zc: Any, type_: str, svc_name: str) -> None:
            self.add_service(zc, type_, svc_name)

    zc = None
    browser = None
    try:
        zc = zc_mod.Zeroconf()
        browser = zc_mod.ServiceBrowser(zc, SERVICE_TYPE, _Listener())
        if wait:
            time.sleep(wait)
    except Exception as exc:  # noqa: BLE001 - optional extra must not raise
        return _unavailable(f"mdns browse failed: {type(exc).__name__}")
    finally:
        if browser is not None:
            try:
                browser.cancel()
            except Exception:  # noqa: BLE001
                pass
        if zc is not None:
            try:
                zc.close()
            except Exception:  # noqa: BLE001
                pass
    return filter_candidates(list(found.values()))


atexit.register(unadvertise)
