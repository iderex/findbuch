"""Gate coverage on the code that decides a verdict, and report the rest.

A whole-codebase number is dominated by whichever part of the codebase is
largest, which here is the plumbing: the runners, the printers and the argument
handling. A bar over that number moves when somebody adds a printing function,
so it gets lowered, and by then it has stopped saying anything about the part
that matters. This gates the part that matters and reports everything else, and
it is #54.

WHAT THE GATED SURFACE IS. The code that decides whether a row is verified.
Today that is the loader's and the schema's refusal paths; when the bracket
computation, the polynomial reduction, the ideal reduction, the drift
measurement and the control run comparison land, they belong here too. The test
beside this file refuses a shipped module that is in neither list, so a module
arrives on one side or the other by somebody deciding, never by defaulting to
the ungated side in silence. That is the failure this file is most exposed to:
the surface is small today and the checker is not written yet, so a bar that
could not notice the checker arriving would be green for years and mean nothing.

WHAT A PERCENTAGE CANNOT SAY, written here rather than left to be assumed from a
green check. A bar is a floor under a ratio of executed statements. It cannot
require that a PARTICULAR refusal path is executed by a test, and the gap
between the bar and today's measurement is a handful of statements that may be
any of them. The obligation that each refusal is proven by a test that reddens
without it is a different property, it is stronger, and this is not it.

This is not a leg of `tools/gate.py`. It runs the same suite the tests leg runs,
under measurement, so a default gate carrying both would run the suite twice for
one extra verdict. It is a job on a pull request and a command a contributor
runs directly.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The gated surface, with the reason each module is on it. Everything that can
# turn a wrong row green.
VERDICT_SURFACE: dict[str, str] = {
    "src/findbuch/validation.py": (
        "the refusal paths of the loader and of the schema. A row that gets "
        "past these is treated as well formed by everything downstream, so a "
        "refusal that quietly stops firing is a wrong row reported as a good one"
    ),
}

# Everything else this project ships, with the reason it is not gated. An entry
# here is a decision that a regression in this module cannot turn a wrong row
# green, and it is written where somebody arguing with it will find it.
REPORTED_ONLY: dict[str, str] = {
    "src/findbuch/__init__.py": (
        "the package marker. It decides nothing and holds no path a row travels"
    ),
    "src/findbuch/invariants.py": (
        "a scan of this repository's own source. It decides whether a spelling "
        "is present in a tracked file, never anything about a row, and its own "
        "proof is the fixture pair each invariant ships with rather than a ratio"
    ),
    "tools/check_catalogue_format.py": (
        "a runner. It reads the rows and prints, and the deciding it does is "
        "the formatter's rather than its own"
    ),
    "tools/check_catalogue_schema.py": (
        "a runner over the validator above, which is on the gated surface. "
        "Gating the caller as well would count the same decisions twice and "
        "would put the bar partly on argument handling"
    ),
    "tools/check_interpreter.py": (
        "a comparison of two version strings, before any row is read"
    ),
    "tools/check_invariants.py": (
        "a runner over the scan above, for the same reason as the scan"
    ),
    "tools/floor.py": (
        "the dependency floor build. It decides which versions a run installs "
        "and nothing about a row"
    ),
    "tools/gate.py": (
        "the gate's own leg list and its runner. It decides what runs, and "
        "what each leg decides is the leg's"
    ),
    "tools/coverage_bar.py": (
        "this file. It measures, and a measuring instrument gating itself on "
        "its own measurement says nothing about either"
    ),
}

# The bar, as a whole-number percentage.
#
# WHY THIS VALUE. The gated surface measures 93 with branch coverage today, over
# 152 statements, and the command that produced that number is in docs/coverage.md
# beside it. The bar sits below the measurement rather than at it, because a bar
# at the measurement reddens the first time somebody lands a statement and its
# test in two commits, and a gate that reds for arithmetic is a gate people learn
# to re-run rather than read.
#
# WHAT THAT COSTS, stated rather than left to be worked out: three points of 152
# statements is about four, so this bar refuses a regression of five uncovered
# statements and permits one of four. Raising it is a change with its own
# reasoning and its own measurement, in this file, and not a ratchet that runs
# on its own.
BAR = 90


def surface_arguments() -> list[str]:
    return ["--include=" + ",".join(sorted(VERDICT_SURFACE))]


def _coverage(arguments: list[str], into: Path | None = None) -> int:
    command = [sys.executable, "-m", "coverage", *arguments]
    print(f"\n=== coverage {' '.join(arguments)}", flush=True)
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=into is not None,
        text=True,
    )
    if into is not None:
        into.write_text(completed.stdout + completed.stderr, encoding="utf-8")
        print(completed.stdout + completed.stderr, flush=True)
    return completed.returncode


def run(report_into: Path) -> int:
    """Measure, write the reports, then decide.

    The reports are written before the verdict is taken, and the job keeps them
    whatever the verdict is. A failing bar is exactly the moment somebody needs
    the per-line report, and a report that only survives a green run is a report
    that is never read.
    """
    report_into.mkdir(parents=True, exist_ok=True)

    _coverage(["erase"])
    measured = _coverage(["run", "-m", "unittest", "discover", "-s", "tests"])
    if measured != 0:
        print("\ncoverage: REFUSED, the suite failed under measurement")
        return measured

    print(f"\ncoverage: the gated surface, and the bar is {BAR}")
    _coverage(
        ["report", "--show-missing", *surface_arguments()],
        into=report_into / "verdict-surface.txt",
    )

    print("\ncoverage: everything this project ships, reported and not gated")
    _coverage(["report", "--show-missing"], into=report_into / "whole-tree.txt")
    _coverage(["html", "--directory", str(report_into / "html")])

    verdict = _coverage([*["report", f"--fail-under={BAR}"], *surface_arguments()])
    if verdict != 0:
        print(
            f"\ncoverage: REFUSED, the gated surface is below {BAR}. The report "
            f"naming the uncovered lines is in {report_into}, and it says which "
            "of them decide a row. Cover them, or argue the bar down in "
            "tools/coverage_bar.py where its reason is written."
        )
        return 1
    print(f"\ncoverage: the gated surface is at or above {BAR}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate coverage on the verdict path.")
    parser.add_argument(
        "--report-into",
        default=str(REPO_ROOT / "htmlcov"),
        metavar="DIR",
        help="where the reports are written; the job attaches this directory",
    )
    parser.add_argument(
        "--bar",
        action="store_true",
        help="print the bar and stop, so nothing else has to hold the number",
    )
    arguments = parser.parse_args(argv)
    if arguments.bar:
        print(BAR)
        return 0
    return run(Path(arguments.report_into))


if __name__ == "__main__":
    raise SystemExit(main())
