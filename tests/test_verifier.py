"""The standalone verifier must be standalone, and must agree with the engine.

Two independent implementations that agree is a stronger statement than one
asserting it is right — but only if the agreement is actually checked, and only
if the second one really is independent. Both are pinned here.
"""

from __future__ import annotations

import copy
import json
import subprocess  # nosec B404 - runs this repo's own file, no external input
import sys
from pathlib import Path

import pytest

from veritas.custody import CustodyLedger, verify_chain_records
from veritas.hashing import compute_content_hash as engine_hash
from veritas.hashing import normalize_content as engine_normalize
from veritas.verifier import (
    EXIT_INVALID,
    EXIT_UNREADABLE,
    EXIT_VALID,
    compute_content_hash,
    main,
    normalize_content,
    verify_chain,
    verify_response,
)

VERIFIER_PATH = Path(__file__).resolve().parent.parent / "veritas" / "verifier.py"


@pytest.fixture
def response():
    excerpt = "catalog snapshot body"
    digest = engine_hash(excerpt)
    ledger = CustodyLedger()
    ledger.append("created", "catalog", {"query": "fed"})
    ledger.append("delivered", "catalog", {"hash": digest})
    return {
        "request_id": "v1",
        "status": "completed",
        "query": "fed",
        "claims": [
            {
                "id": "c1",
                "statement": excerpt,
                "evidence_hash": digest,
                "source_url": "https://example.test/m",
            }
        ],
        "evidence": [
            {
                "url": "https://example.test/m",
                "excerpt": excerpt,
                "content_hash": digest,
            }
        ],
        "custody_root": ledger.root_hash(),
        "custody_valid": True,
        "custody_chain": ledger.to_list(),
        "support": {"n_evidence": 1},
        "attests": "fixture",
        "retrieval": {},
        "refusal_reason": None,
        "billable": True,
        "timestamp": "2026-08-17T00:00:00Z",
    }


# -- it must actually be standalone -----------------------------------------


def test_the_verifier_imports_nothing_from_veritas():
    """The whole claim. A buyer must be able to vendor this one file, and a
    verifier that imported the seller's package would validate the seller's
    forgeries with the seller's own code."""
    source = VERIFIER_PATH.read_text(encoding="utf-8")
    offenders = [
        line.strip() for line in source.splitlines()
        if line.startswith(("import ", "from "))
        and ("veritas" in line or line.startswith("from ."))
    ]
    assert not offenders, f"verifier is not standalone: {offenders}"


def test_the_verifier_imports_only_the_standard_library():
    source = VERIFIER_PATH.read_text(encoding="utf-8")
    imported = {
        line.split()[1].split(".")[0]
        for line in source.splitlines()
        if line.startswith(("import ", "from ")) and "__future__" not in line
    }
    assert imported <= set(sys.stdlib_module_names), (
        f"non-stdlib imports: {imported - set(sys.stdlib_module_names)}")


def test_the_verifier_runs_as_a_copied_out_file(tmp_path, response):
    """Copied anywhere, with no veritas package importable from that cwd."""
    vendored = tmp_path / "verifier.py"
    vendored.write_text(VERIFIER_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(response), encoding="utf-8")

    result = subprocess.run(  # nosec B603 - fixed argv, this repo's own file
        [sys.executable, str(vendored), str(receipt)],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == EXIT_VALID, result.stdout + result.stderr
    assert json.loads(result.stdout)["valid"] is True


# -- differential agreement with the engine ---------------------------------


@pytest.mark.parametrize("text", [
    "", "plain text", "  leading and trailing  ", "tabs\tand   spaces",
    "windows\r\nline\rendings", "unicode: café ☕ 日本語",
    "﻿byte order mark", "many\n\n\n\n\nnewlines", "é combining",
])
def test_normalisation_matches_the_engine_exactly(text):
    """Any divergence here makes every hash disagree, silently."""
    assert normalize_content(text) == engine_normalize(text)
    assert compute_content_hash(text) == engine_hash(text)


def test_chain_verdict_matches_the_engine_on_real_output(response):
    chain = response["custody_chain"]
    assert verify_chain(chain).valid is verify_chain_records(chain) is True


def test_chain_verdict_matches_the_engine_on_a_tampered_payload(response):
    tampered = copy.deepcopy(response["custody_chain"])
    tampered[0]["payload"]["query"] = "a different question"
    assert verify_chain(tampered).valid is verify_chain_records(tampered) is False


def test_chain_verdict_matches_the_engine_on_a_rehashed_forgery(response):
    """The sophisticated forgery: alter an event and recompute its own hash, so
    only the *link* to the next event betrays it."""
    from veritas.custody import CustodyEvent

    tampered = copy.deepcopy(response["custody_chain"])
    tampered[0]["payload"]["query"] = "a different question"
    tampered[0]["event_hash"] = CustodyEvent(
        event_type=tampered[0]["event_type"], actor=tampered[0]["actor"],
        timestamp=tampered[0]["timestamp"], prev_hash=tampered[0]["prev_hash"],
        payload=tampered[0]["payload"],
    ).compute_hash()

    assert verify_chain(tampered).valid is verify_chain_records(tampered) is False


def test_chain_verdict_matches_the_engine_on_a_dropped_event(response):
    tampered = copy.deepcopy(response["custody_chain"])
    del tampered[0]
    assert verify_chain(tampered).valid is verify_chain_records(tampered) is False


# -- response-level checks --------------------------------------------------


def test_a_real_response_verifies(response):
    report = verify_response(response)
    assert report.valid, report.failures


def test_a_swapped_excerpt_is_caught(response):
    tampered = copy.deepcopy(response)
    tampered["evidence"][0]["excerpt"] = "something the seller never retrieved"
    report = verify_response(tampered)
    assert not report.valid
    assert any("content_hash" in f for f in report.failures)


def test_a_claim_citing_undelivered_evidence_is_caught(response):
    tampered = copy.deepcopy(response)
    tampered["claims"][0]["evidence_hash"] = "sha256:" + "00" * 32
    report = verify_response(tampered)
    assert not report.valid
    assert any("not delivered" in f for f in report.failures)


def test_a_forged_custody_root_is_caught(response):
    tampered = copy.deepcopy(response)
    tampered["custody_root"] = "sha256:" + "ff" * 32
    report = verify_response(tampered)
    assert not report.valid
    assert any("custody_root" in f for f in report.failures)


def test_billing_for_an_outage_is_caught():
    """The seller's core commercial promise, checked by the buyer."""
    report = verify_response({
        "status": "unavailable", "billable": True,
        "custody_chain": [], "evidence": [], "claims": [],
    })
    assert not report.valid
    assert any("charging for its own failure" in f for f in report.failures)


def test_a_receipt_wrapping_the_response_is_accepted(response):
    assert verify_response({"request_id": "r1", "response": response}).valid


def test_verify_response_never_raises_on_garbage():
    for garbage in ("", 0, [], None, {"custody_chain": "no"}, {"claims": 5}):
        assert verify_response(garbage).valid is False


def test_an_empty_chain_does_not_read_as_valid():
    """Vacuous truth must not become a passing verdict: a response claiming
    custody while carrying none has not been verified."""
    assert not verify_response({"custody_chain": [], "evidence": [], "claims": []}).valid


# -- the CLI ----------------------------------------------------------------


def test_cli_exits_zero_on_a_valid_receipt(tmp_path, capsys, response):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(response), encoding="utf-8")
    assert main([str(path)]) == EXIT_VALID
    assert json.loads(capsys.readouterr().out)["valid"] is True


def test_cli_exits_one_on_a_tampered_receipt(tmp_path, capsys, response):
    tampered = copy.deepcopy(response)
    tampered["evidence"][0]["excerpt"] = "swapped"
    path = tmp_path / "r.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    assert main([str(path)]) == EXIT_INVALID


def test_cli_separates_an_unreadable_file_from_an_invalid_one(tmp_path, capsys):
    """Exit 2 is not a verdict about the seller."""
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert main([str(path)]) == EXIT_UNREADABLE
    assert json.loads(capsys.readouterr().out)["error"] == "unreadable_input"


def test_the_report_states_what_it_does_not_attest(response):
    """Tamper-evidence is not attestation, and the report must say so itself."""
    attests = verify_response(response).to_dict()["attests"]
    assert "not that the seller contacted the URLs" in attests
