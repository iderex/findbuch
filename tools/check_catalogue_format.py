"""Check that every catalogue row is written in the canonical TOML form.

The rows are the product. They are read far more often than the code, and a
transcription error is normally spotted by putting two rows side by side, which
only works if the two are written the same way. So this refuses a difference
rather than quietly rewriting the file.

It says how many files it examined. A run over an empty catalogue and a run that
never found the catalogue at all print nothing otherwise, and those are not the
same result.

Run it as

    python tools/check_catalogue_format.py

Add --write to rewrite the rows instead of refusing. Nothing in the gate passes
that flag; it is here so that a contributor can fix what the check reported.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = REPO_ROOT / "catalogue"


def rows() -> list[Path]:
    """Every row in the catalogue, in a fixed order so the output is stable."""
    return sorted(CATALOGUE.rglob("*.toml"))


def run_toml_sort(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    """Call toml-sort through the running interpreter rather than through PATH.

    The console script is not on PATH on every platform a contributor uses, and
    a check that cannot be run locally is a check that only fails in CI.
    """
    return subprocess.run(
        [sys.executable, "-c", "from toml_sort.cli import cli; cli()", *arguments],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the catalogue row format.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="rewrite the rows instead of refusing a difference",
    )
    arguments = parser.parse_args(argv)

    found = rows()
    # Flushed, because what follows is another process's output on another
    # stream, and a count that lands after the failures it counts is worse than
    # no count.
    print(
        f"catalogue-format: examined {len(found)} row(s) under catalogue/", flush=True
    )
    if not found:
        print("catalogue-format: no row has been through this check yet")
        return 0

    mode = "--in-place" if arguments.write else "--check"
    result = run_toml_sort([mode, *(str(path) for path in found)])
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
