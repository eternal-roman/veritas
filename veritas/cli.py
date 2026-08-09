"""Shared CLI plumbing for the exit-code-contract family.

The verdict-bearing CLIs (diligence, audit, buy, money-loop) assign meanings
to exit codes 1 and 2 — "fail" and "could not check" are deliberately
different exits. Stdlib argparse exits 2 on a usage error, so a typo'd flag
made `veritas-diligence` report "unverifiable" to a shelling agent. A usage
error is the caller's input being wrong, not a finding about any subject, so
it exits with the family's bad-input code instead.
"""

from __future__ import annotations

import argparse
import sys

#: The caller's own input was unusable — not a statement about any subject.
EXIT_BAD_INPUT = 3


class VerdictArgumentParser(argparse.ArgumentParser):
    """ArgumentParser whose usage errors exit 3 (bad input), never 2."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_BAD_INPUT, f"{self.prog}: error: {message}\n")
