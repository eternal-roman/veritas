"""Optional LAN mDNS advertise/browse for self-hosted peers."""

from __future__ import annotations

import ipaddress

from veritas.peer import PEER_PATH, SCHEMA
from veritas.peer_mdns import (
    SERVICE_TYPE,
    advertise,
    advertise_addresses,
    browse,
    candidate_url,
    candidates_from_addresses,
    filter_candidates,
    is_advertisable_address,
    mdns_available,
    service_txt,
    unadvertise,
)


class _FakeServiceInfo:
    def __init__(
        self,
        type_,
        name,
        port=None,
        properties=b"",
        server=None,
        parsed_addresses=None,
        **kwargs,
    ):
        self.type = type_
        self.name = name
        self.port = port
        self.server = server
        self.properties = {}
        if isinstance(properties, dict):
            for key, value in properties.items():
                raw_key = key.encode() if isinstance(key, str) else key
                if value is None:
                    raw_value = None
                elif isinstance(value, str):
                    raw_value = value.encode()
                else:
                    raw_value = value
                self.properties[raw_key] = raw_value
        self._addresses = list(parsed_addresses or [])

    def parsed_addresses(self, version=None):
        return list(self._addresses)


class _FakeZeroconf:
    registry: dict = {}

    def __init__(self, *args, **kwargs):
        self.closed = False

    def register_service(self, info, **kwargs):
        type(self).registry[info.name] = info

    def unregister_service(self, info):
        type(self).registry.pop(getattr(info, "name", None), None)

    def close(self):
        self.closed = True

    def get_service_info(self, type_, name, timeout=3000, **kwargs):
        return type(self).registry.get(name)


class _FakeBrowser:
    def __init__(self, zc, type_, listener=None, handlers=None, **kwargs):
        target = listener or handlers
        for name in list(_FakeZeroconf.registry):
            target.add_service(zc, type_, name)

    def cancel(self):
        return None


class _FakeZeroconfModule:
    ServiceInfo = _FakeServiceInfo
    ServiceBrowser = _FakeBrowser
    Zeroconf = _FakeZeroconf


def _install_fake(monkeypatch):
    _FakeZeroconf.registry = {}
    fake = _FakeZeroconfModule()
    monkeypatch.setattr("veritas.peer_mdns._load_zeroconf", lambda: fake)
    return fake


def test_advertise_browse_without_zeroconf_are_unavailable(monkeypatch):
    monkeypatch.setattr("veritas.peer_mdns._load_zeroconf", lambda: None)
    advertised = advertise("127.0.0.1", 8080)
    assert advertised["unavailable"] is True
    assert advertised["ok"] is False
    assert advertised["code"] == "unavailable"
    browsed = browse()
    assert browsed["unavailable"] is True
    assert browsed["ok"] is False
    assert browsed["code"] == "unavailable"
    assert browsed.get("peers") == []


def test_candidate_url_localhost_http_and_https():
    assert candidate_url("localhost", 8080) == "http://localhost:8080"
    assert candidate_url("localhost", 8443, https=True) == "https://localhost:8443"
    assert candidate_url("127.0.0.1", 80) == "http://127.0.0.1:80"


def test_metadata_ip_is_filtered_if_it_appears():
    assert is_advertisable_address("169.254.169.254") is False
    assert is_advertisable_address("169.254.1.1") is False
    assert is_advertisable_address("100.100.100.200") is False
    assert is_advertisable_address("192.168.0.10") is True
    assert is_advertisable_address("127.0.0.1") is True

    rows = candidates_from_addresses(
        "mixed",
        ["192.168.0.10", "169.254.169.254", "169.254.1.1"],
        8080,
    )
    urls = [row["url"] for row in rows]
    assert urls == ["http://192.168.0.10:8080"]

    filtered = filter_candidates([
        {"name": "meta", "url": "http://169.254.169.254:80", "https": False},
        {"name": "lan", "url": "http://10.0.0.5:8080", "https": False},
        {"name": "ll", "url": "http://169.254.12.34:9", "https": False},
    ])
    assert [row["name"] for row in filtered] == ["lan"]


def test_txt_has_card_schema_and_no_lan_address():
    txt = service_txt(https=False)
    assert txt["card"] == PEER_PATH == "/v1/peer"
    assert txt["schema"] == SCHEMA == "veritas.peer.v1"
    blob = " ".join(f"{key}={value}" for key, value in txt.items())
    assert "192.168" not in blob
    assert "127.0.0.1" not in blob
    assert "169.254" not in blob


def test_advertise_refuses_metadata_host_without_raising(monkeypatch):
    monkeypatch.setattr("veritas.peer_mdns._load_zeroconf", lambda: None)
    result = advertise("169.254.169.254", 80)
    assert result["ok"] is False
    assert result["code"] == "refused"
    assert advertise_addresses("169.254.169.254") == []


def test_unspecified_listen_host_expands_to_local_addresses(monkeypatch):
    monkeypatch.setattr(
        "veritas.peer_mdns._local_addresses",
        lambda: ["192.168.1.20"],
    )
    assert advertise_addresses("0.0.0.0") == ["192.168.1.20"]
    assert advertise_addresses("::") == ["192.168.1.20"]
    assert advertise_addresses("*") == ["192.168.1.20"]
    assert advertise_addresses("") == ["192.168.1.20"]


def test_fake_zeroconf_advertise_browse_roundtrip(monkeypatch):
    _install_fake(monkeypatch)
    advertised = advertise("127.0.0.1", 8765, name="veritas-mdns-selftest")
    assert advertised["ok"] is True
    assert advertised["unavailable"] is False
    assert advertised["url"] == "http://127.0.0.1:8765"
    assert advertised["txt"]["card"] == "/v1/peer"
    assert advertised["txt"]["schema"] == SCHEMA
    assert "169.254.169.254" not in advertised["addresses"]

    found = browse(timeout=0)
    assert isinstance(found, list)
    assert found == [{
        "name": "veritas-mdns-selftest",
        "url": "http://127.0.0.1:8765",
        "https": False,
    }]
    unadvertise()
    assert browse(timeout=0) == []


def test_browse_filters_metadata_on_a_mixed_service(monkeypatch):
    _install_fake(monkeypatch)
    info = _FakeServiceInfo(
        SERVICE_TYPE,
        f"mixed.{SERVICE_TYPE}",
        port=9,
        properties=service_txt(https=True),
        parsed_addresses=["192.168.1.9", "169.254.169.254", "fe80::1"],
    )
    _FakeZeroconf.registry[info.name] = info
    found = browse(timeout=0)
    assert isinstance(found, list)
    assert found == [{
        "name": "mixed",
        "url": "https://192.168.1.9:9",
        "https": True,
    }]
    for row in found:
        host = ipaddress.ip_address(row["url"].split("://", 1)[1].rsplit(":", 1)[0])
        assert host != ipaddress.ip_address("169.254.169.254")
        assert not host.is_link_local


def test_mdns_available_tracks_loader(monkeypatch):
    monkeypatch.setattr("veritas.peer_mdns._load_zeroconf", lambda: None)
    assert mdns_available() is False
    monkeypatch.setattr("veritas.peer_mdns._load_zeroconf", lambda: _FakeZeroconfModule())
    assert mdns_available() is True
