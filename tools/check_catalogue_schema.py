"""Validate every row in the catalogue against the published schema.

This is the `catalogue schema` leg of the gate. It refuses shape and never
meaning; `findbuch.validation` says at length what that means and why the split
is not softened here.

It says how many rows it examined and how many structures it resolved against,
because a run over an empty catalogue and a run over a catalogue whose structure
registry is empty both print no refusals, and neither of those is the same
result as a catalogue that passed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from findbuch.structures import STRUCTURES  # noqa: E402
from findbuch.validation import (  # noqa: E402
    StructureRegistry,
    validate_catalogue,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the catalogue rows.")
    parser.add_argument("--catalogue", type=Path, default=REPO_ROOT / "catalogue")
    # The default comes from the module that reads the directory rather than
    # from a second path built here. The two agreed while the files sat at the
    # repository root; after #84 moved them into the package, a second spelling
    # would have this leg checking rows against a directory the package does not
    # use.
    parser.add_argument("--structures", type=Path, default=STRUCTURES)
    arguments = parser.parse_args(argv)

    registry = (
        StructureRegistry.from_directory(arguments.structures)
        if arguments.structures.is_dir()
        else StructureRegistry([])
    )
    results = validate_catalogue(arguments.catalogue, registry)

    print(
        f"catalogue-schema: examined {len(results)} row(s) against "
        f"{len(registry.identifiers)} structure(s)"
    )
    if not registry.identifiers:
        print(
            f"catalogue-schema: the structure registry is empty, so every row "
            f"naming a structure would be refused as structure.unknown for a "
            f"reason that is not about the row; nothing was read at "
            f"'{arguments.structures}'"
        )
    if not results:
        print("catalogue-schema: no row has been through this check yet")
        return 0

    not_evaluated = [r for r in results if not r.parameters_rule_evaluated]
    refused = [r for r in results if not r.valid]
    for result in refused:
        print(f"\n{result.path.name}")
        for refusal in result.refusals:
            print(f"  {refusal}")

    if not_evaluated:
        print(
            f"\ncatalogue-schema: the undeclared-parameter rule was NOT EVALUATED "
            f"on {len(not_evaluated)} row(s), because their structure declares no "
            f"coordinates to subtract"
        )
        for result in not_evaluated:
            print(f"  {result.path.name}")

    print(
        f"\ncatalogue-schema: {len(results) - len(refused)} row(s) well formed, "
        f"{len(refused)} refused"
    )
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
