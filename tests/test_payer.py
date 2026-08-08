"""Buyer-side x402 payment machinery: challenge validation, EIP-712 authorization
construction, spend-policy gating, and the fail-closed payment client.

The load-bearing property is key-custody inversion: no key material may ever
exist inside veritas/ — the typed-data payload travels to a signer, only a
signature comes back. These tests also pin the two policy layers (validation
gate + spend caps) and that every failure is an explicit result, not an
exception.
"""

import base64
import dataclasses
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import veritas.payer
from veritas.payer import (
    PaymentClient,
    SpendPolicy,
    ValidatedAccepts,
    build_authorization,
    validate_accepts,
)
from veritas.x402 import USDC_ASSETS

NETWORK = "eip155:8453"
ASSET = USDC_ASSETS[NETWORK]["address"]
PAY_TO = "0x" + "ab" * 20
PAYER = "0x" + "cd" * 20
NOW = 1_753_600_000


def _entry(**overrides):
    entry = {
        "scheme": "exact",
        "network": NETWORK,
        "maxAmountRequired": "250000",
        "payTo": PAY_TO,
        "asset": ASSET,
        "extra": {"name": "USDC", "version": "2"},
    }
    entry.update(overrides)
    return entry


def _valid():
    validated, problems = validate_accepts(_entry())
    assert problems == []
    return validated


def _policy(tmp_path, per_request=2, per_day=4, per_counterparty=None, networks=None):
    return SpendPolicy(
        max_per_request=per_request,
        max_per_day=per_day,
        max_per_day_per_counterparty=per_counterparty,
        allowed_networks=networks,
        base_dir=tmp_path,
    )


class _StubSigner:
    """Test-only signer double. Holds no key bytes — returns a fixed hex blob."""

    address = PAYER

    def __init__(self):
        self.calls = []

    def sign_typed_data(self, payload):
        self.calls.append(payload)
        return "0x" + "ab" * 65


class _RaisingSigner:
    address = PAYER

    def __init__(self):
        self.calls = []

    def sign_typed_data(self, payload):
        self.calls.append(payload)
        raise RuntimeError("hardware wallet unplugged")


# ---------------------------------------------------------------- validation


def test_validate_accepts_accepts_canonical_entry():
    validated, problems = validate_accepts(_entry())
    assert problems == []
    assert validated.scheme == "exact"
    assert validated.network == NETWORK
    assert validated.chain_id == 8453
    assert validated.asset == ASSET
    assert validated.pay_to == PAY_TO
    assert validated.amount_atomic == 250000
    assert validated.domain_name == "USDC"
    assert validated.domain_version == "2"


def test_validate_accepts_asset_compare_case_insensitive_preserves_casing():
    lowered = ASSET.lower()
    validated, problems = validate_accepts(_entry(asset=lowered))
    assert problems == []
    assert validated.asset == lowered  # not silently re-cased


def test_validate_accepts_rejects_wrong_scheme():
    validated, problems = validate_accepts(_entry(scheme="upto"))
    assert validated is None
    assert problems


def test_validate_accepts_rejects_unknown_network():
    validated, problems = validate_accepts(_entry(network="eip155:999999"))
    assert validated is None
    assert problems


def test_validate_accepts_rejects_non_caip2_network():
    validated, problems = validate_accepts(_entry(network="base"))
    assert validated is None
    assert problems


def test_validate_accepts_rejects_wrong_asset():
    wrong = "0x" + "11" * 20
    validated, problems = validate_accepts(_entry(asset=wrong))
    assert validated is None
    assert problems


@pytest.mark.parametrize("bad", ["0x123", "abcdef", "0x" + "zz" * 20, "", "0x" + "ab" * 21])
def test_validate_accepts_rejects_malformed_pay_to(bad):
    validated, problems = validate_accepts(_entry(payTo=bad))
    assert validated is None
    assert problems


@pytest.mark.parametrize("bad", ["0", "-5", "abc", "1.5", ""])
def test_validate_accepts_rejects_bad_amounts(bad):
    validated, problems = validate_accepts(_entry(maxAmountRequired=bad))
    assert validated is None
    assert problems


def test_validate_accepts_domain_defaults_and_overrides():
    entry = _entry()
    del entry["extra"]
    validated, problems = validate_accepts(entry)
    assert problems == []
    assert (validated.domain_name, validated.domain_version) == ("USDC", "2")

    validated, problems = validate_accepts(_entry(extra={"name": "USD Coin", "version": "1"}))
    assert problems == []
    assert (validated.domain_name, validated.domain_version) == ("USD Coin", "1")


def test_validate_accepts_enumerates_multiple_problems():
    validated, problems = validate_accepts(
        _entry(scheme="upto", network="eip155:999999", payTo="nope", maxAmountRequired="0")
    )
    assert validated is None
    assert len(problems) >= 3


@pytest.mark.parametrize(
    "garbage",
    [{}, {"scheme": None}, {"maxAmountRequired": None, "network": 42, "payTo": [], "asset": 7}],
)
def test_validate_accepts_never_raises(garbage):
    validated, problems = validate_accepts(garbage)
    assert validated is None
    assert problems


def test_validated_accepts_cannot_be_constructed_directly():
    """Construction is token-guarded so instances only come from validate_accepts.
    This is structural, not cryptographic — deliberate internal code can bypass it."""
    fields = dict(
        scheme="exact",
        network=NETWORK,
        chain_id=8453,
        asset=ASSET,
        pay_to=PAY_TO,
        amount_atomic=250000,
        domain_name="USDC",
        domain_version="2",
    )
    with pytest.raises(TypeError):
        ValidatedAccepts(**fields)
    with pytest.raises(TypeError):
        ValidatedAccepts(**fields, _token=object())


def test_validated_accepts_is_frozen():
    validated = _valid()
    with pytest.raises(dataclasses.FrozenInstanceError):
        validated.amount_atomic = 1


# ---------------------------------------------------------- build_authorization


def test_build_authorization_payload_shape():
    payload = build_authorization(_valid(), PAYER, now=NOW)

    assert payload["primaryType"] == "TransferWithAuthorization"
    assert payload["types"]["EIP712Domain"] == [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ]
    assert payload["types"]["TransferWithAuthorization"] == [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ]
    domain = payload["domain"]
    assert domain["name"] == "USDC"
    assert domain["version"] == "2"
    assert domain["chainId"] == 8453
    assert domain["verifyingContract"] == ASSET

    message = payload["message"]
    assert message["from"] == PAYER
    assert message["to"] == PAY_TO
    assert message["value"] == "250000"  # value travels as a string
    assert int(message["validAfter"]) == NOW - 1
    assert int(message["validBefore"]) == NOW + 60
    assert re.fullmatch(r"0x[0-9a-f]{64}", message["nonce"])


def test_build_authorization_nonce_default_is_fresh_bytes32():
    first = build_authorization(_valid(), PAYER, now=NOW)["message"]["nonce"]
    second = build_authorization(_valid(), PAYER, now=NOW)["message"]["nonce"]
    assert first != second
    assert re.fullmatch(r"0x[0-9a-f]{64}", first)


def test_build_authorization_honours_explicit_nonce_and_validity():
    nonce = "0x" + "5a" * 32
    payload = build_authorization(_valid(), PAYER, now=NOW, validity_seconds=300, nonce=nonce)
    assert payload["message"]["nonce"] == nonce
    assert int(payload["message"]["validBefore"]) == NOW + 300


# ------------------------------------------------------------------ SpendPolicy


def test_policy_allows_within_caps_and_names_ok(tmp_path):
    decision = _policy(tmp_path).authorize(2, NETWORK, PAY_TO)
    assert decision.allowed is True
    assert decision.check == "ok"


def test_policy_decision_is_frozen(tmp_path):
    decision = _policy(tmp_path).authorize(1, NETWORK, PAY_TO)
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.allowed = False


def test_policy_network_allowlist(tmp_path):
    policy = _policy(tmp_path, networks={"eip155:1"})
    decision = policy.authorize(1, NETWORK, PAY_TO)
    assert decision.allowed is False
    assert decision.check == "network_allowlist"


def test_policy_none_allowlist_means_any_known_network(tmp_path):
    policy = _policy(tmp_path, networks=None)
    assert policy.authorize(1, NETWORK, PAY_TO).allowed is True
    unknown = policy.authorize(1, "eip155:999999", PAY_TO)
    assert unknown.allowed is False
    assert unknown.check == "network_allowlist"


def test_policy_per_request_cap(tmp_path):
    decision = _policy(tmp_path, per_request=2).authorize(3, NETWORK, PAY_TO)
    assert decision.allowed is False
    assert decision.check == "per_request_cap"


def test_policy_per_day_cap_accumulates(tmp_path):
    policy = _policy(tmp_path, per_request=2, per_day=4)
    for _ in range(2):
        assert policy.authorize(2, NETWORK, PAY_TO).allowed is True
        policy.record(2, PAY_TO)
    decision = policy.authorize(1, NETWORK, PAY_TO)
    assert decision.allowed is False
    assert decision.check == "per_day_cap"


def test_policy_per_counterparty_cap(tmp_path):
    other = "0x" + "ef" * 20
    policy = _policy(tmp_path, per_request=3, per_day=10, per_counterparty=3)
    assert policy.authorize(3, NETWORK, PAY_TO).allowed is True
    policy.record(3, PAY_TO)
    decision = policy.authorize(1, NETWORK, PAY_TO)
    assert decision.allowed is False
    assert decision.check == "per_counterparty_cap"
    assert policy.authorize(1, NETWORK, other).allowed is True


def test_policy_counters_survive_reinstantiation(tmp_path):
    """Roadmap 3.3 acceptance: caps hold across process restarts, so a crashed
    and restarted buyer cannot double its daily budget."""
    first = _policy(tmp_path, per_request=2, per_day=4)
    assert first.authorize(2, NETWORK, PAY_TO).allowed is True
    first.record(2, PAY_TO)

    reborn = _policy(tmp_path, per_request=2, per_day=4)
    assert reborn.authorize(2, NETWORK, PAY_TO).allowed is True
    reborn.record(2, PAY_TO)
    decision = reborn.authorize(1, NETWORK, PAY_TO)
    assert decision.allowed is False
    assert decision.check == "per_day_cap"


def test_policy_state_file_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path))
    policy = SpendPolicy(max_per_request=2, max_per_day=4, max_per_day_per_counterparty=None)
    policy.record(1, PAY_TO)
    state = json.loads((tmp_path / "spend_policy.json").read_text(encoding="utf-8"))
    assert set(state) == {"date", "spent", "per_counterparty"}
    assert state["spent"] == 1
    assert state["per_counterparty"] == {PAY_TO: 1}


def test_policy_day_rollover_resets_counters(tmp_path):
    stale = {"date": "2020-01-01", "spent": 4, "per_counterparty": {PAY_TO: 3}}
    (tmp_path / "spend_policy.json").write_text(json.dumps(stale))
    policy = _policy(tmp_path, per_request=2, per_day=4, per_counterparty=3)
    decision = policy.authorize(2, NETWORK, PAY_TO, now_utc_date="2020-01-02")
    assert decision.allowed is True


def test_policy_same_day_state_is_honoured(tmp_path):
    stale = {"date": "2020-01-01", "spent": 4, "per_counterparty": {PAY_TO: 3}}
    (tmp_path / "spend_policy.json").write_text(json.dumps(stale))
    policy = _policy(tmp_path, per_request=2, per_day=4)
    decision = policy.authorize(1, NETWORK, PAY_TO, now_utc_date="2020-01-01")
    assert decision.allowed is False
    assert decision.check == "per_day_cap"


def test_policy_corrupt_state_fails_closed(tmp_path):
    """Superseded the earlier "corrupt state = fresh day" behaviour: an
    adversarial review showed that re-granting the full budget on a damaged
    file hands a daily budget to anything able to damage it. If we cannot
    establish today's spend, we cannot bound it, so we refuse."""
    (tmp_path / "spend_policy.json").write_text("{not json")
    policy = _policy(tmp_path, per_request=2, per_day=4)
    decision = policy.authorize(1, NETWORK, PAY_TO)
    assert decision.allowed is False
    assert decision.check == "corrupt_state"
    assert "spend_policy.json" in decision.detail


def test_policy_absent_state_is_a_fresh_start(tmp_path):
    """Absent state is first-run, not damage — it must still be allowed."""
    assert _policy(tmp_path, per_request=2, per_day=4).authorize(2, NETWORK, PAY_TO).allowed


def test_policy_recovers_once_corrupt_state_is_removed(tmp_path):
    (tmp_path / "spend_policy.json").write_text("{not json")
    policy = _policy(tmp_path, per_request=2, per_day=4)
    assert policy.authorize(1, NETWORK, PAY_TO).check == "corrupt_state"
    (tmp_path / "spend_policy.json").unlink()
    assert policy.authorize(1, NETWORK, PAY_TO).allowed, "operator repair must clear the latch"


def test_corrupt_state_blocks_signing_end_to_end(tmp_path):
    (tmp_path / "spend_policy.json").write_text('{"date": "2026-07-27", "spent": -5}')
    signer = _StubSigner()
    client = PaymentClient(signer, _policy(tmp_path, per_request=250000, per_day=500000))
    result = client.pay(_valid(), now=NOW)
    assert not result.paid and result.check == "corrupt_state"
    assert signer.calls == [], "no signature may be requested on unbounded budget"


def test_policy_write_failure_keeps_memory_counters_authoritative(tmp_path):
    """If state cannot be persisted (OSError), the process must not under-count:
    in-memory counters stay authoritative for subsequent authorize calls."""
    not_a_dir = tmp_path / "occupied"
    not_a_dir.write_text("this path is a file, so writing occupied/spend_policy.json fails")
    policy = _policy(not_a_dir, per_request=2, per_day=4)
    assert policy.authorize(2, NETWORK, PAY_TO).allowed is True
    policy.record(2, PAY_TO)  # persist fails; must not raise, must still count
    policy.record(2, PAY_TO)
    decision = policy.authorize(1, NETWORK, PAY_TO)
    assert decision.allowed is False
    assert decision.check == "per_day_cap"


# ---------------------------------------------------------------- PaymentClient


def test_pay_success_header_decodes_to_spec_shape(tmp_path):
    signer = _StubSigner()
    client = PaymentClient(signer, _policy(tmp_path, per_request=250000, per_day=500000))
    result = client.pay(_valid(), now=NOW)

    assert result.paid is True
    assert result.denial is None
    assert len(signer.calls) == 1

    decoded = json.loads(base64.b64decode(result.header))
    assert decoded["x402Version"] == 1
    assert decoded["scheme"] == "exact"
    assert decoded["network"] == NETWORK
    assert decoded["payload"]["signature"] == "0x" + "ab" * 65
    authorization = decoded["payload"]["authorization"]
    assert authorization["from"] == PAYER
    assert authorization["to"] == PAY_TO
    assert authorization["value"] == "250000"  # exactly the quoted amount
    assert authorization["nonce"] == result.nonce
    assert re.fullmatch(r"0x[0-9a-f]{64}", result.nonce)
    assert result.nonce in json.dumps(result.authorization)


def test_pay_result_is_frozen(tmp_path):
    client = PaymentClient(_StubSigner(), _policy(tmp_path, per_request=250000, per_day=500000))
    result = client.pay(_valid(), now=NOW)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.paid = False


def test_pay_rejects_unvalidated_input_without_raising(tmp_path):
    """A raw accepts dict must be refused as a result, not an exception — the
    only path to payment runs through validate_accepts."""
    signer = _StubSigner()
    client = PaymentClient(signer, _policy(tmp_path, per_request=250000, per_day=500000))
    result = client.pay(_entry(), now=NOW)
    assert result.paid is False
    assert result.denial == "unvalidated_input"
    assert result.header is None
    assert signer.calls == []


def test_pay_policy_denial_never_calls_signer(tmp_path):
    signer = _StubSigner()
    client = PaymentClient(signer, _policy(tmp_path, per_request=1, per_day=500000))
    result = client.pay(_valid(), now=NOW)
    assert result.paid is False
    assert result.check == "per_request_cap"
    assert result.denial
    assert result.header is None
    assert signer.calls == []


def test_pay_signer_error_fails_closed_and_policy_not_charged(tmp_path):
    policy = _policy(tmp_path, per_request=250000, per_day=250000)
    client = PaymentClient(_RaisingSigner(), policy)
    result = client.pay(_valid(), now=NOW)
    assert result.paid is False
    assert result.denial == "signer_error:RuntimeError"
    assert result.header is None
    # The failed attempt must not consume budget: the full day cap remains.
    assert policy.authorize(250000, NETWORK, PAY_TO).allowed is True


def test_pay_refuses_duplicate_nonce(tmp_path, monkeypatch):
    """Nonce collisions should be impossible from 32 random bytes; if one ever
    appears the client must refuse rather than sign a replayable authorization."""
    monkeypatch.setattr(
        veritas.payer, "secrets", SimpleNamespace(token_bytes=lambda n: b"\x11" * n)
    )
    signer = _StubSigner()
    policy = _policy(tmp_path, per_request=250000, per_day=1_000_000)
    client = PaymentClient(signer, policy)

    first = client.pay(_valid(), now=NOW)
    assert first.paid is True
    second = client.pay(_valid(), now=NOW)
    assert second.paid is False
    assert second.denial == "nonce_reuse"
    assert second.header is None
    assert len(signer.calls) == 1  # denial means zero signer calls for that request
    # And the refused request must not consume budget.
    assert policy.authorize(250000, NETWORK, PAY_TO).allowed is True


# ------------------------------------------------------------- source hygiene


def test_payer_module_docstring_states_custody_inversion():
    assert veritas.payer.__doc__
    assert "key" in veritas.payer.__doc__.lower()


def test_payer_source_contains_no_key_material():
    """Key-custody inversion is only real if no key bytes, private-key handling,
    or hardcoded 32-byte hex literals exist in the module source."""
    source = Path(veritas.payer.__file__).read_text(encoding="utf-8")
    assert not re.search(r"0x[0-9a-fA-F]{64}", source)
    lowered = source.lower()
    assert "privkey" not in lowered
    assert "private_key" not in lowered
    assert "mnemonic" not in lowered
    # The stdlib `secrets` module (nonce entropy) is the only permitted match.
    for match in re.finditer(r"secret\w*", lowered):
        assert match.group(0) == "secrets"


# ---------------------------------------------------------------------------
# Regressions from the adversarial review panel (policy edges, nonce/time,
# parameter provenance). Each pins a finding that was demonstrated live.
# ---------------------------------------------------------------------------


def test_per_counterparty_cap_binds_across_address_casings(tmp_path):
    """One recipient has 2**40 hex casings; all must share one budget."""
    policy = _policy(tmp_path, per_request=3, per_day=100, per_counterparty=3)
    lower = "0x" + "ab" * 20
    upper = "0x" + "AB" * 20
    mixed = "0x" + "aB" * 20
    policy.record(3, lower)
    for spelling in (upper, mixed, lower):
        decision = policy.authorize(1, NETWORK, spelling)
        assert not decision.allowed
        assert decision.check == "per_counterparty_cap"


def test_state_file_counterparty_keys_fold_on_load(tmp_path):
    (tmp_path / "spend_policy.json").write_text(json.dumps({
        "date": "2026-07-27",
        "spent": 4,
        "per_counterparty": {"0x" + "ab" * 20: 2, "0x" + "AB" * 20: 2},
    }))
    policy = _policy(tmp_path, per_request=5, per_day=100, per_counterparty=5)
    decision = policy.authorize(2, NETWORK, "0x" + "aB" * 20, now_utc_date="2026-07-27")
    assert not decision.allowed and decision.check == "per_counterparty_cap"


def test_two_policy_instances_sharing_state_accumulate(tmp_path):
    """Last-writer-wins under-counting: instance B must see instance A's spend."""
    a = _policy(tmp_path, per_request=2, per_day=4)
    b = _policy(tmp_path, per_request=2, per_day=4)  # constructed before A spends
    a.record(2, PAY_TO)
    a.record(2, PAY_TO)
    decision = b.authorize(2, NETWORK, PAY_TO)
    assert not decision.allowed and decision.check == "per_day_cap"


def test_backwards_date_does_not_reset_daily_cap(tmp_path):
    policy = _policy(tmp_path, per_request=2, per_day=2)
    assert policy.authorize(2, NETWORK, PAY_TO, now_utc_date="2026-07-27").allowed
    policy.record(2, PAY_TO, now_utc_date="2026-07-27")
    # Alternating back to an earlier day must not re-grant the budget.
    decision = policy.authorize(2, NETWORK, PAY_TO, now_utc_date="2026-07-26")
    assert not decision.allowed and decision.check == "per_day_cap"


def test_malformed_date_is_denied(tmp_path):
    decision = _policy(tmp_path).authorize(1, NETWORK, PAY_TO, now_utc_date="yesterday")
    assert not decision.allowed and decision.check == "invalid_date"


def test_nonpositive_amounts_denied_and_record_raises(tmp_path):
    policy = _policy(tmp_path)
    for bad in (0, -1, True):
        assert policy.authorize(bad, NETWORK, PAY_TO).check == "invalid_amount"
    with pytest.raises(ValueError):
        policy.record(-4, PAY_TO)
    with pytest.raises(ValueError):
        policy.record(0, PAY_TO)


def test_negative_or_bool_state_counters_treated_as_corrupt(tmp_path):
    (tmp_path / "spend_policy.json").write_text(json.dumps({
        "date": "2026-07-27", "spent": -1000000, "per_counterparty": {},
    }))
    policy = _policy(tmp_path, per_request=2, per_day=4)
    # Negative spent would silently EXPAND the budget; it must load as fresh.
    assert not policy.authorize(2, NETWORK, PAY_TO).allowed or policy._spent == 0
    (tmp_path / "spend_policy.json").write_text(json.dumps({
        "date": "2026-07-27", "spent": True, "per_counterparty": {},
    }))
    assert _policy(tmp_path)._spent == 0


def test_build_authorization_rejects_degenerate_windows():
    with pytest.raises(ValueError):
        build_authorization(_valid(), PAYER, now=0)
    with pytest.raises(ValueError):
        build_authorization(_valid(), PAYER, now=-5)
    with pytest.raises(ValueError):
        build_authorization(_valid(), PAYER, now=NOW, validity_seconds=0)


def test_pay_rejects_out_of_range_validity_window(tmp_path):
    signer = _StubSigner()
    client = PaymentClient(signer, _policy(tmp_path, per_request=250000, per_day=500000))
    for now, validity in ((NOW, 0), (NOW, -5), (NOW, 999_999_999), (0, 60)):
        result = client.pay(_valid(), now=now, validity_seconds=validity)
        assert not result.paid and result.check == "invalid_validity_window"
    assert signer.calls == []


def test_replace_derived_instance_is_refused(tmp_path):
    """dataclasses.replace() mints an equal-typed instance that never passed
    validate_accepts; the client must refuse it."""
    tampered = dataclasses.replace(_valid(), pay_to="0x" + "ee" * 20)
    signer = _StubSigner()
    client = PaymentClient(signer, _policy(tmp_path, per_request=250000, per_day=500000))
    result = client.pay(tampered, now=NOW)
    assert not result.paid and result.check == "unvalidated_input"
    assert signer.calls == []


def test_attempt_journal_written_ahead_of_signer(tmp_path):
    signer = _StubSigner()
    client = PaymentClient(signer, _policy(tmp_path, per_request=250000, per_day=500000))
    result = client.pay(_valid(), now=NOW)
    assert result.paid
    lines = [json.loads(x) for x in
             (tmp_path / "authorization_attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [x["stage"] for x in lines] == ["pre_sign", "signed"]
    assert lines[0]["nonce"] == result.nonce
    assert lines[0]["amount"] == 250000
    assert lines[0]["pay_to"] == PAY_TO


def test_signer_error_leaves_pre_sign_journal_entry(tmp_path):
    class _RaisingSigner:
        address = PAYER

        def sign_typed_data(self, payload):
            raise ConnectionError("transport lost after send")

    client = PaymentClient(_RaisingSigner(), _policy(tmp_path, per_request=250000,
                                                     per_day=500000))
    result = client.pay(_valid(), now=NOW)
    assert not result.paid and result.check == "signer_error"
    lines = [json.loads(x) for x in
             (tmp_path / "authorization_attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert lines[0]["stage"] == "pre_sign"
    assert lines[1]["stage"].startswith("signer_error:")


def test_unwritable_journal_refuses_to_sign(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("a regular file where the journal dir should be")
    signer = _StubSigner()
    client = PaymentClient(signer, _policy(tmp_path, per_request=250000, per_day=500000),
                           base_dir=blocked)
    result = client.pay(_valid(), now=NOW)
    assert not result.paid and result.check == "journal_error"
    assert signer.calls == []


@pytest.mark.parametrize("raw", ["2_500_000", " 250000", "250000\n", "+250000",
                                 str(2**256)])
def test_amount_wire_format_is_strict(raw):
    validated, problems = validate_accepts(_entry(maxAmountRequired=raw))
    assert validated is None
    assert problems
