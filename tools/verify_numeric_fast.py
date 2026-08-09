"""The `numeric verification (fast)` leg of the gate.

The same shape as tools/verify_symbolic_fast.py and for the same reason: the
check name is matched literally by the gate #57 puts on the default branch, so
the name exists from the beginning and the leg grows into it.

WHAT IT DECIDES TODAY: nothing. The numeric criterion is
`docs/decisions/0007-numeric-criterion.md`. The structure-respecting integrator
at arbitrary precision is #30, the initial conditions inside the declared domain
are #31, and the drift measured against the Casimir noise floor is #32. None of
it is in the tree.

The fast leg is not the sweep. The sweep integrates every row twice, once at the
declared precision and once raised, takes minutes to hours, and lives outside
the default run in its own harness, which is #34. This leg is the short one that
belongs on a pull request. Neither of them exists yet and neither is claimed to.

WHY IT REFUSES A NON-EMPTY CATALOGUE: tools/verify_symbolic_fast.py says it, and
the reason is the same one. A green check called `numeric verification (fast)`
over a row nothing integrated is an assurance nobody earned.
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

LEG = "numeric-fast"
CRITERION_RECORD = "docs/decisions/0007-numeric-criterion.md"
WHAT_IMPLEMENTS_IT = "#30 and #31, with the drift measurement in #32"


def rows_in(catalogue: Path) -> list[Path]:
    if not catalogue.is_dir():
        return []
    return sorted(catalogue.glob("*.toml"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decide rows numerically, fast.")
    parser.add_argument("--catalogue", type=Path, default=REPO_ROOT / "catalogue")
    arguments = parser.parse_args(argv)

    rows = rows_in(arguments.catalogue)
    print(f"{LEG}: examined {len(rows)} row(s) in {arguments.catalogue.name}/")
    print(
        f"{LEG}: the criterion is {CRITERION_RECORD} and nothing in this tree "
        f"implements it yet; that is {WHAT_IMPLEMENTS_IT}"
    )
    print(f"{LEG}: this is the fast leg and not the full sweep, which is #34")

    if not rows:
        print(f"{LEG}: no row has been through this check yet")
        return 0

    for row in rows:
        print(f"  NOT DECIDED  {row.name}")
    print(
        f"\n{LEG}: REFUSED {len(rows)} row(s) this leg cannot decide. A green "
        f"check under this name over an undecided row would say the row was "
        f"numerically verified, and it was not."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
