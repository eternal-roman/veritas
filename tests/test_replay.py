"""Replay protection (roadmap 0.4): a resubmitted X-PAYMENT header must not
make us perform the paid work twice.

The acceptance criterion is behavioural, not structural: the second submission
of the same header must be refused *before* a retrieval pass is consumed.
"""

import base64
import json

import pytest
from fastapi.testclient import TestClient

from veritas.replay import SpentNonceStore, extract_nonce

NONCE = "0x" + "ab" * 32
OTHER_NONCE = "0x" + "cd" * 32


def _payload(nonce=NONCE):
    return {
        "x402Version": 1,
        "scheme": "exact",
        "network": "eip155:8453",
        "payload": {"signature": "0xsig", "authorization": {"nonce": nonce}},
    }


def _header(nonce=NONCE):
    return base64.b64encode(json.dumps(_payload(nonce)).encode()).decode()


# -- nonce extraction -------------------------------------------------------


def test_extract_nonce_from_authorization():
    assert extract_nonce(_payload()) == NONCE


def test_extract_nonce_tolerates_hoisted_shapes():
    assert extract_nonce({"payload": {"nonce": NONCE}}) == NONCE
    assert extract_nonce({"nonce": NONCE}) == NONCE


def test_extract_nonce_normalises_case():
    assert extract_nonce({"nonce": "0x" + "AB" * 32}) == NONCE


@pytest.mark.parametrize("payload", [
    {}, {"payload": {}}, {"nonce": "not-a-nonce"}, {"nonce": "0xabc"}, "string", None,
])
def test_extract_nonce_returns_none_when_absent_or_malformed(payload):
    assert extract_nonce(payload) is None


# -- the store --------------------------------------------------------------


def test_first_claim_succeeds_second_is_refused(tmp_path):
    store = SpentNonceStore(tmp_path)
    first = store.claim(NONCE)
    assert first.claimed and first.nonce == NONCE
    second = store.claim(NONCE)
    assert not second.claimed
    assert second.reason == "payment_nonce_already_spent"


def test_distinct_nonces_both_claim(tmp_path):
    store = SpentNonceStore(tmp_path)
    assert store.claim(NONCE).claimed
    assert store.claim(OTHER_NONCE).claimed


def test_claims_survive_restart(tmp_path):
    assert SpentNonceStore(tmp_path).claim(NONCE).claimed
    # A restarted instance must still refuse the nonce, or a crash-loop
    # becomes a way to replay paid work.
    assert not SpentNonceStore(tmp_path).claim(NONCE).claimed


def test_casing_cannot_evade_the_guard(tmp_path):
    store = SpentNonceStore(tmp_path)
    assert store.claim(NONCE).claimed
    assert not store.claim("0x" + "AB" * 32).claimed


def test_missing_and_malformed_nonces_are_named(tmp_path):
    store = SpentNonceStore(tmp_path)
    assert store.claim(None).reason == "payment_nonce_missing"
    assert store.claim("0xzz").reason == "payment_nonce_malformed"


def test_unusable_store_fails_closed(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("a regular file where the store directory should be")
    result = SpentNonceStore(blocked).claim(NONCE)
    assert not result.claimed
    assert result.reason.startswith("replay_store_unavailable")


def test_torn_final_line_does_not_discard_earlier_nonces(tmp_path):
    store = SpentNonceStore(tmp_path)
    store.claim(NONCE)
    with store.path.open("a") as fh:
        fh.write('{"nonce": "0xdeadbeef')  # truncated write
    assert not store.claim(NONCE).claimed, "earlier nonces must survive a torn line"


# -- end to end through the HTTP surface ------------------------------------


@pytest.fixture
def live_client(tmp_path, monkeypatch):
    """A live-mode server whose facilitator always accepts."""
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("VERITAS_REQUIRE_PAYMENT", "true")
    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://veritas.test")
    monkeypatch.setenv("VERITAS_PAY_TO", "0x" + "11" * 20)
    monkeypatch.setenv("VERITAS_NETWORK", "eip155:8453")
    monkeypatch.setenv("VERITAS_FACILITATOR", "https://facilitator.test")

    import veritas.server as server
    from veritas.facilitator import SettlementResult, VerificationResult

    class _AcceptingFacilitator:
        def verify(self, payload, requirements):
            return VerificationResult(True, payer="0xpayer")

        def settle(self, payload, requirements):
            return SettlementResult(True, transaction="0xtx", network="eip155:8453")

    monkeypatch.setattr(server, "get_facilitator", lambda *a, **k: _AcceptingFacilitator())
    monkeypatch.setattr(server, "nonces", SpentNonceStore(tmp_path))

    calls = {"n": 0}
    real_run = server.run_research

    def counting_run(query, **kwargs):
        calls["n"] += 1
        return real_run(query, allow_network=False, **kwargs)

    monkeypatch.setattr(server, "run_research", counting_run)
    return TestClient(server.app), calls


def test_resubmitted_header_does_the_work_once(live_client):
    """Roadmap 0.4 acceptance, stated exactly."""
    client, calls = live_client
    body = {"query": "What is the x402 protocol?"}
    headers = {"X-PAYMENT": _header()}

    first = client.post("/v1/research", json=body, headers=headers)
    assert first.status_code == 200, first.text
    assert calls["n"] == 1

    second = client.post("/v1/research", json=body, headers=headers)
    assert second.status_code == 409
    assert second.json()["error"] == "payment_nonce_already_spent"
    assert calls["n"] == 1, "the retrieval pass must not run a second time"


def test_fresh_nonce_is_served_after_a_replay_attempt(live_client):
    client, calls = live_client
    body = {"query": "What is the x402 protocol?"}

    assert client.post("/v1/research", json=body,
                       headers={"X-PAYMENT": _header()}).status_code == 200
    assert client.post("/v1/research", json=body,
                       headers={"X-PAYMENT": _header()}).status_code == 409
    # The guard must reject replays without wedging the endpoint.
    third = client.post("/v1/research", json=body,
                        headers={"X-PAYMENT": _header(OTHER_NONCE)})
    assert third.status_code == 200
    assert calls["n"] == 2


def test_payment_without_a_nonce_is_refused_before_work(live_client):
    client, calls = live_client
    naked = base64.b64encode(json.dumps({"x402Version": 1, "scheme": "exact"}).encode()).decode()
    response = client.post("/v1/research", json={"query": "What is the x402 protocol?"},
                           headers={"X-PAYMENT": naked})
    assert response.status_code == 409
    assert response.json()["error"] == "payment_nonce_missing"
    assert calls["n"] == 0
