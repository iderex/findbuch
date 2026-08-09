"""The `symbolic verification (fast)` leg of the gate.

The check name is an interface. #57 makes these names required on the default
branch and matches them literally, so the name has to exist before the criterion
behind it does, and the leg grows into the name rather than appearing beside a
finished feature. That is what this file is: the leg, with the criterion still
to come.

WHAT IT DECIDES TODAY: nothing. The symbolic criterion is
`docs/decisions/0006-symbolic-criterion.md`, its implementation is #26, and the
reduction modulo the constraint ideal that conditional cases need is #27. None
of that is in the tree, so this leg decides no row and says so in the words
"NOT DECIDED" rather than printing a count of zero refusals, because a run that
refused nothing because it checked nothing prints the same colour as one that
checked everything and found it sound.

WHY IT REFUSES A NON-EMPTY CATALOGUE. Passing over an empty catalogue is the
whole of what this leg can honestly do. The moment a row exists, a green check
called `symbolic verification (fast)` says that row was symbolically verified,
and nothing here did that. So a row this leg cannot decide is refused, and the
refusal names the issue that makes it decidable. This is deliberate and it is a
forcing function: it means the first row cannot land under a check that claims
to have verified it. #26 is the one-line change that replaces the refusal with a
verdict.
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

LEG = "symbolic-fast"
CRITERION_RECORD = "docs/decisions/0006-symbolic-criterion.md"
WHAT_IMPLEMENTS_IT = "#26, and #27 for the conditional cases"


def rows_in(catalogue: Path) -> list[Path]:
    if not catalogue.is_dir():
        return []
    return sorted(catalogue.glob("*.toml"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decide rows symbolically, fast.")
    parser.add_argument("--catalogue", type=Path, default=REPO_ROOT / "catalogue")
    arguments = parser.parse_args(argv)

    rows = rows_in(arguments.catalogue)
    print(f"{LEG}: examined {len(rows)} row(s) in {arguments.catalogue.name}/")
    print(
        f"{LEG}: the criterion is {CRITERION_RECORD} and nothing in this tree "
        f"implements it yet; that is {WHAT_IMPLEMENTS_IT}"
    )

    if not rows:
        print(f"{LEG}: no row has been through this check yet")
        return 0

    for row in rows:
        print(f"  NOT DECIDED  {row.name}")
    print(
        f"\n{LEG}: REFUSED {len(rows)} row(s) this leg cannot decide. A green "
        f"check under this name over an undecided row would say the row was "
        f"symbolically verified, and it was not."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
