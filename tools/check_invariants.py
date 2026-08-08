"""Enforce this repository's greppable invariants over the tree.

This is the `Enforce greppable invariants` job and the `invariants` leg of the
gate. What each invariant is, why it exists and which issue decided it are in
`findbuch.invariants`, beside the pattern rather than in a document, so that
somebody who has just been refused can find out why without leaving the file.

It says what it examined. An invariant whose path set reaches no file has not
passed; it has not run, and a run that prints nothing about it says the opposite
of the truth. So the count is printed per invariant and an empty set is a
refusal rather than a quiet zero.

What this cannot do is in `findbuch.invariants` and is not softened here: a
pattern decides that a spelling is absent, never that the property holds.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from findbuch.invariants import (  # noqa: E402
    INVARIANTS,
    NOT_SCANNED,
    scan_tree,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enforce the greppable invariants.")
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the invariants and the issue that decided each one",
    )
    arguments = parser.parse_args(argv)

    if arguments.list:
        for rule in INVARIANTS:
            print(f"{rule.identifier}\t{rule.decided_in}\t{rule.path_set}")
        return 0

    result = scan_tree(arguments.root)

    print(f"invariants: {len(INVARIANTS)} declared")
    for rule in INVARIANTS:
        count = result.examined[rule.identifier]
        print(f"  {rule.identifier} ({rule.decided_in}): {count} file(s) examined")

    if NOT_SCANNED:
        print(
            f"\ninvariants: {len(NOT_SCANNED)} path(s) excluded from every scan, "
            f"with the reason at the exclusion:"
        )
        for name in NOT_SCANNED:
            print(f"  {name}")

    if result.not_evaluated:
        print(
            "\ninvariants: REFUSED, these invariants read no file at all, so they "
            "did not run and cannot be reported as clean:"
        )
        for name in result.not_evaluated:
            print(f"  {name}")
        return 1

    if not result.clean:
        print(f"\ninvariants: {len(result.violations)} violation(s)")
        for violation in result.violations:
            print(f"  {violation}")
        offending = {violation.invariant for violation in result.violations}
        print("\nwhy each of these exists:")
        for rule in INVARIANTS:
            if rule.identifier in offending:
                print(f"\n  {rule.identifier}, decided in {rule.decided_in}")
                print(f"    {rule.reason}")
        print("\ninvariants: REFUSED")
        return 1

    print("\ninvariants: every declared invariant ran and refused nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
