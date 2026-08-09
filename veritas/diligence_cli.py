"""veritas-diligence: vet a counterparty before paying it.

    veritas-diligence https://seller.example

Fetches the seller's published surfaces, evaluates them, and prints a JSON
verdict with a reason per check. The first consumer of a diligence tool for an
agent-native venue is another agent, so the output is JSON and the decision is
also carried in the exit code:

    0   pass          the seller cleared the checks this policy requires
    1   fail          a contradiction was observed in the seller's own documents
    2   unverifiable  the checks could not be run - say, the seller is offline

**Two and one are different exits on purpose.** A buyer agent that treats
"could not check" as "failed" will refuse honest sellers during its own
network trouble; one that treats it as "passed" will pay anyone who can manage
to be unreachable. Neither is acceptable, so the distinction the evaluator
draws survives all the way out to the process contract.

What a `pass` is not: proof the seller will deliver. Every check is
cross-document consistency or register integrity, and a careful liar with a
coherent set of documents passes all of them.
"""

from __future__ import annotations

import argparse
import json

from .cli import VerdictArgumentParser
from .counterparty import evaluate_seller
from .diligence import DiligencePolicy, Verdict
from .safeurl import UnsafeUrlError

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNVERIFIABLE = 2
#: The buyer's own input was unusable - not a statement about the seller.
EXIT_BAD_INPUT = 3

_EXIT_FOR = {
    Verdict.PASS: EXIT_PASS,
    Verdict.FAIL: EXIT_FAIL,
    Verdict.UNVERIFIABLE: EXIT_UNVERIFIABLE,
}


def build_parser() -> argparse.ArgumentParser:
    parser = VerdictArgumentParser(
        prog="veritas-diligence",
        description="Vet an x402 seller from the documents it publishes.",
        epilog="exit codes: 0 pass · 1 fail · 2 unverifiable · 3 bad input "
               "(1 and 2 are different on purpose: could-not-check is not "
               "seller-failed)",
    )
    parser.add_argument("url", help="Base URL of the seller, e.g. https://seller.example")
    parser.add_argument(
        "--challenge",
        metavar="PATH",
        help="File holding the 402 challenge JSON this buyer received. Without "
             "it the strongest check (challenge agrees with advertised "
             "discovery) is unverifiable rather than passed.",
    )
    parser.add_argument(
        "--min-enforced-articles", type=int, default=1, metavar="N",
        help="Refuse a seller whose constitution enforces fewer than N articles "
             "(default: 1).",
    )
    parser.add_argument(
        "--allow-missing-constitution", action="store_true",
        help="Do not require a constitution at all.",
    )
    parser.add_argument(
        "--allow-undeclared-gaps", action="store_true",
        help="Do not refuse a seller that declares no open gaps. Off by "
             "default: an empty defect register claims perfection.",
    )
    parser.add_argument(
        "--allow-undisclosed-trust", action="store_true",
        help="Do not require the trust document to disclose that it is "
             "self-reported.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    challenge = None
    if args.challenge:
        try:
            with open(args.challenge, encoding="utf-8") as handle:
                challenge = json.load(handle)
        except (OSError, ValueError) as exc:
            print(json.dumps({
                "error": "challenge_unreadable",
                "detail": f"{type(exc).__name__} reading {args.challenge}",
            }, indent=2))
            return EXIT_BAD_INPUT

    policy = DiligencePolicy(
        require_challenge_matches_discovery=challenge is not None,
        require_constitution=not args.allow_missing_constitution,
        require_gap_register=not args.allow_undeclared_gaps,
        require_trust_self_disclosure=not args.allow_undisclosed_trust,
        min_enforced_articles=args.min_enforced_articles,
    )

    try:
        report = evaluate_seller(args.url, challenge=challenge, policy=policy)
    except UnsafeUrlError as exc:
        # The buyer handed us a URL we will not fetch. That is the buyer's
        # input being wrong, not a finding about any seller, so it gets its
        # own exit code rather than masquerading as a verdict.
        print(json.dumps({"error": "unsafe_url", "detail": str(exc)}, indent=2))
        return EXIT_BAD_INPUT

    payload = {"seller": args.url, **report.to_dict()}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return _EXIT_FOR.get(report.verdict, EXIT_UNVERIFIABLE)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
