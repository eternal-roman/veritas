"""veritas-audit: audit an EvidencePack, verify audit records, count survival.

    veritas-audit run pack.json            # re-fetch origin, emit signed AuditRecord
    veritas-audit verify record.json       # check one record's signature and shape
    veritas-audit report r1.json r2.json   # survival report over records you hold

The first consumer is another agent, so output is JSON on stdout and the
decision is also carried in the exit code. For ``run``:

    0   confirmed    the origin served a body matching the attested hash
    1   diverged     the origin answered with a different body — divergence,
                     not fraud proof: pages change between T1 and T2
    2   unobserved   the origin could not be observed — evidence of nothing,
                     and never scored against the seller
    3   bad input    the pack itself was unreadable or failed integrity —
                     a claim never validly made cannot be audited

**Two and one are different exits on purpose**, for the same reason
`veritas-diligence` separates them: an agent that treats "could not look" as
"caught lying" will destroy honest reputations during its own network
trouble. ``verify`` exits 0/1; ``report`` always exits 0 (its output is
counts, not a judgment).

Signing: ``run`` signs with ``VERITAS_SIGNING_KEY`` or the agent wallet when
configured (the same resolution as evidence attestation); without a key the
record is emitted unsigned and counts for nothing in a survival report —
stated in the output rather than silently.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .audit import (
    VERDICT_CONFIRMED,
    VERDICT_DIVERGED,
    AuditError,
    perform_audit,
    survival_report,
    verify_audit_record,
)
from .cli import VerdictArgumentParser
from .notary.sign import NotarySignError, operator_signer_from_env

EXIT_CONFIRMED = 0
EXIT_DIVERGED = 1
EXIT_UNOBSERVED = 2
EXIT_BAD_INPUT = 3


def build_parser() -> argparse.ArgumentParser:
    parser = VerdictArgumentParser(
        prog="veritas-audit",
        description="Independent audit of evidence attestations; survival as counts.",
        epilog="exit codes (run): 0 confirmed · 1 diverged · 2 unobserved · "
               "3 bad input (2 is evidence of nothing and never scored)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Audit one EvidencePack against its origin.")
    run.add_argument("pack", help="Path to an EvidencePack JSON file.")

    verify = sub.add_parser("verify", help="Verify one AuditRecord JSON file.")
    verify.add_argument("record", help="Path to an AuditRecord JSON file.")

    report = sub.add_parser(
        "report", help="Survival report over AuditRecord JSON files you hold."
    )
    report.add_argument("records", nargs="+", help="AuditRecord JSON files.")
    report.add_argument(
        "--seller",
        metavar="ADDRESS",
        help="Count only records attesting this seller key; others are "
             "reported as foreign_excluded.",
    )
    return parser


def _load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _emit(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        pack = _load_json(args.pack)
    except (OSError, json.JSONDecodeError) as exc:
        _emit({"error": "pack_unreadable", "detail": type(exc).__name__})
        return EXIT_BAD_INPUT
    try:
        signer = operator_signer_from_env()
    except NotarySignError:
        _emit({"error": "signing_key_invalid"})
        return EXIT_BAD_INPUT
    try:
        record = perform_audit(pack, signer=signer)
    except AuditError as exc:
        _emit({"error": "pack_invalid", "detail": str(exc)})
        return EXIT_BAD_INPUT
    if signer is None:
        record["unsigned"] = (
            "no signing key configured; this record counts for nothing in a "
            "survival report"
        )
    _emit(record)
    if record["verdict"] == VERDICT_CONFIRMED:
        return EXIT_CONFIRMED
    if record["verdict"] == VERDICT_DIVERGED:
        return EXIT_DIVERGED
    return EXIT_UNOBSERVED


def _cmd_verify(args: argparse.Namespace) -> int:
    try:
        record = _load_json(args.record)
    except (OSError, json.JSONDecodeError) as exc:
        _emit({"valid": False, "reason": "record_unreadable", "detail": type(exc).__name__})
        return EXIT_DIVERGED
    ok, reason = verify_audit_record(record)
    _emit({"valid": ok, "reason": reason})
    return EXIT_CONFIRMED if ok else EXIT_DIVERGED


def _cmd_report(args: argparse.Namespace) -> int:
    records: list[Any] = []
    unreadable = 0
    for path in args.records:
        try:
            records.append(_load_json(path))
        except (OSError, json.JSONDecodeError):
            unreadable += 1
    report = survival_report(records, seller=args.seller, publication=records)
    if unreadable:
        report["unreadable_files"] = unreadable
    _emit(report)
    return EXIT_CONFIRMED


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "verify":
        return _cmd_verify(args)
    return _cmd_report(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
