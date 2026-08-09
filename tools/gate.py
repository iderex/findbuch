"""One command that runs every leg of the gate, in order, and says what it did not run.

Two procedures for one gate is one procedure and one thing that drifts away from
it. So the legs are declared once, here, and both callers read the same list: a
contributor runs

    python tools/gate.py

before pushing, and the workflow runs each leg on its own with

    python tools/gate.py --leg lint

so that the check names stay separate on the pull request. `--list` prints the
names for whoever is writing that workflow.

This is not enforcement. Nothing in the tree knows whether anybody ran it, and
what stands behind a merge is the protection on the default branch. It is a way
to find out in seconds rather than after a push.

The run says what it examined. A leg that did not run prints that it did not
run and what asking for it would cost, so that a run covering part of the set
cannot be mistaken for a run that covered all of it and found nothing. That
matters most for the full verification sweep, which is not in the default run
and which would otherwise be assumed to have happened.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The full sweep lands in #34. Until it does, the gate looks for it here and
# reports it missing rather than silently having no sweep leg at all. #34 either
# creates this path or changes this line, and the second is a one-line change
# made deliberately instead of a leg that quietly disappeared.
SWEEP_ENTRY_POINT = REPO_ROOT / "tools" / "run_sweep.py"


@dataclass(frozen=True)
class Leg:
    """One leg of the gate.

    `cost` is what running it takes, in words a person can act on. It is printed
    whenever the leg does not run, because "skipped" on its own does not tell a
    reader whether to ask for it.
    """

    name: str
    what: str
    command: Sequence[str]
    cost: str
    in_default_run: bool = True
    requires: Path | None = field(default=None)

    def is_available(self) -> bool:
        return self.requires is None or self.requires.exists()


LEGS: tuple[Leg, ...] = (
    Leg(
        name="interpreter",
        what="the running interpreter is the one .python-version pins",
        command=(sys.executable, str(REPO_ROOT / "tools" / "check_interpreter.py")),
        cost="no measurable time",
    ),
    Leg(
        name="lint",
        what="ruff, in check mode",
        command=(sys.executable, "-m", "ruff", "check", "."),
        cost="under a second",
    ),
    Leg(
        name="format",
        what="ruff's formatter, reporting a difference rather than writing one",
        command=(sys.executable, "-m", "ruff", "format", "--check", "."),
        cost="under a second",
    ),
    Leg(
        name="types",
        what="mypy in its strict setting, over the declared module set",
        command=(sys.executable, "-m", "mypy"),
        cost="a few seconds, longer on a cold cache",
    ),
    Leg(
        name="rows",
        what="every catalogue row in the canonical TOML form",
        command=(
            sys.executable,
            str(REPO_ROOT / "tools" / "check_catalogue_format.py"),
        ),
        cost="proportional to the number of rows, seconds",
    ),
    Leg(
        name="schema",
        what="every catalogue row against the published schema",
        command=(
            sys.executable,
            str(REPO_ROOT / "tools" / "check_catalogue_schema.py"),
        ),
        cost="proportional to the number of rows, seconds",
    ),
    Leg(
        name="symbolic-fast",
        what="every catalogue row against the symbolic criterion, the short way",
        command=(
            sys.executable,
            str(REPO_ROOT / "tools" / "verify_symbolic_fast.py"),
        ),
        cost="seconds over an empty catalogue, and it grows with the rows",
    ),
    Leg(
        name="numeric-fast",
        what="every catalogue row against the numeric criterion, the short way",
        command=(
            sys.executable,
            str(REPO_ROOT / "tools" / "verify_numeric_fast.py"),
        ),
        cost=(
            "seconds over an empty catalogue. This is the short leg that belongs "
            "on a pull request, and it is not the sweep below."
        ),
    ),
    Leg(
        name="fuzz-seeds",
        what="every committed seed replayed against the parser",
        command=(
            sys.executable,
            str(REPO_ROOT / "tools" / "fuzz_parser.py"),
        ),
        cost=(
            "seconds. This is the replay and not the search: the search derives "
            "inputs from the corpus and is asked for with --search N, which "
            "nothing here passes."
        ),
    ),
    Leg(
        name="invariants",
        what="this repository's greppable invariants, over the paths each declares",
        command=(
            sys.executable,
            str(REPO_ROOT / "tools" / "check_invariants.py"),
        ),
        cost="one pass over the source, well under a second",
    ),
    Leg(
        name="tests",
        what="the test suite",
        # Through tools/run_tests.py rather than by calling pytest here. The
        # runner's environment is part of the invocation and has one home; a
        # second spelling of it in this list would be the drift this whole file
        # exists against.
        command=(sys.executable, str(REPO_ROOT / "tools" / "run_tests.py")),
        cost="seconds today, and it grows with the suite",
    ),
    Leg(
        name="sweep",
        what="the full verification sweep over every row at raised precision",
        command=(sys.executable, str(SWEEP_ENTRY_POINT)),
        cost=(
            "every row integrated twice, once at the declared precision and once "
            "raised; minutes to hours rather than seconds, which is why it is not "
            "in the default run. Ask for it with --with-sweep."
        ),
        in_default_run=False,
        requires=SWEEP_ENTRY_POINT,
    ),
)


def run_leg(leg: Leg) -> tuple[int, float]:
    """Run one leg, letting its own output through to this process's streams."""
    started = time.monotonic()
    completed = subprocess.run(list(leg.command), cwd=REPO_ROOT, check=False)
    return completed.returncode, time.monotonic() - started


def selected(names: list[str] | None, with_sweep: bool) -> list[Leg]:
    if names:
        by_name = {leg.name: leg for leg in LEGS}
        unknown = [name for name in names if name not in by_name]
        if unknown:
            message = f"gate: no such leg: {', '.join(unknown)}"
            raise SystemExit(message)
        return [by_name[name] for name in names]
    return [leg for leg in LEGS if leg.in_default_run or with_sweep]


def report_not_run(legs: list[Leg], reason: str) -> None:
    for leg in legs:
        print(f"  {leg.name}: NOT RUN, {reason}")
        print(f"    what it is:   {leg.what}")
        print(f"    what it costs: {leg.cost}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the gate.")
    parser.add_argument("--list", action="store_true", help="print the leg names")
    parser.add_argument(
        "--leg",
        action="append",
        metavar="NAME",
        help="run only this leg; repeatable. This is what the workflow calls.",
    )
    parser.add_argument(
        "--with-sweep",
        action="store_true",
        help="also run the full verification sweep",
    )
    arguments = parser.parse_args(argv)

    if arguments.list:
        for leg in LEGS:
            default = "default" if leg.in_default_run else "on request"
            print(f"{leg.name}\t{default}\t{leg.what}")
        return 0

    asked_for = selected(arguments.leg, arguments.with_sweep)
    not_asked_for = [leg for leg in LEGS if leg not in asked_for]
    unavailable = [leg for leg in asked_for if not leg.is_available()]
    runnable = [leg for leg in asked_for if leg.is_available()]

    print(
        f"gate: {len(LEGS)} legs declared, {len(runnable)} about to run, "
        f"{len(not_asked_for) + len(unavailable)} not run",
        flush=True,
    )

    failed: Leg | None = None
    ran = 0
    for index, leg in enumerate(runnable, start=1):
        print(f"\n=== [{index}/{len(runnable)}] {leg.name}: {leg.what}", flush=True)
        code, seconds = run_leg(leg)
        ran += 1
        print(f"=== {leg.name}: exit={code} in {seconds:.1f}s", flush=True)
        if code != 0:
            failed = leg
            break

    stopped_early = runnable[ran:] if failed else []

    print(f"\ngate: {ran} leg(s) ran, {len(LEGS) - ran} did not")
    if not_asked_for:
        report_not_run(not_asked_for, "not asked for")
    if unavailable:
        report_not_run(unavailable, "asked for, but its harness is not in the tree")
    if stopped_early:
        report_not_run(stopped_early, "not reached, an earlier leg failed")

    if unavailable:
        names = ", ".join(leg.name for leg in unavailable)
        print(f"\ngate: REFUSED, asked for {names} and could not run it")
        return 1
    if failed is not None:
        print(f"\ngate: REFUSED by {failed.name}, whose own output is above")
        return 1
    print("\ngate: every leg that ran was clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
