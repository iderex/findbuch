"""Resolve the dependency set at the declared floor, and run against that.

Every other route in this tree measures the project against `requirements.lock`,
which pins versions newer than anything `pyproject.toml` declares. So the gate
is a measurement of one resolution, and the project claims to work with a much
larger set than the one it was measured on. An interface that exists only in the
pinned version gets used, everything stays green, and the first person who
installs at the declared bounds gets an error nobody here has seen. That is what
this exists against, and it is #52.

THE NUMBERS ARE NOT WRITTEN HERE. `pyproject.toml` declares them once, as lower
bounds, and this reads them. A second copy of a bound in a workflow file drifts
against the declaration the day somebody raises one, and it drifts silently: a
floor build against the wrong floor is green in exactly the same way as one
against the right floor. The workflow therefore holds no version at all and asks
this file for every number it needs, which `tests/test_floor.py` asserts by
refusing a version literal in that file.

ONLY THE DECLARED BOUNDS ARE PINNED. Whatever those packages pull in behind them
resolves to whatever the index offers on the day. So this is a floor over the
set the project names and never over the transitive graph, and a break that
arrives through a transitive dependency is not a break this run can see.

WHICH LEGS THE FLOOR RUN ANSWERS FOR is derived from the gate's own leg list
rather than restated beside it, so a verification leg added later is picked up
here without anybody remembering to. What it drops, and why, is `NOT_ON_THE_FLOOR`
below, written with the reason at each entry.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import gate

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
GATE = REPO_ROOT / "tools" / "gate.py"

# A requirement is read as a distribution name followed by its specifiers. This
# is not a specifier parser and it is not trying to be one: it reads the one
# form this project's declarations take, and refuses anything else rather than
# guessing. `packaging` would parse the general case and would be a dependency
# the tree does not carry, added for a file whose whole job is to read three
# lines it already controls.
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")
LOWER_BOUND = re.compile(r">=\s*([0-9][0-9A-Za-z.*+!-]*)")

# The legs a floor run does not answer for, with the reason at each one. A leg
# is dropped here or it runs; there is no third state, and a leg dropped without
# a reason beside it is what this dictionary exists to make impossible.
NOT_ON_THE_FLOOR: dict[str, str] = {
    "interpreter": (
        "this run is deliberately on an interpreter other than the one "
        ".python-version pins, and that leg refuses exactly that difference"
    ),
    "lint": (
        "style is measured once, on the pinned interpreter, and a second "
        "verdict from an older linter resolution would be a second answer to a "
        "question that already has one"
    ),
    "format": (
        "the same reason as lint: the formatter's output is a property of the "
        "formatter's version, and the version that decides it is the pinned one"
    ),
    "types": (
        "mypy is a gate tool rather than a runtime dependency, so it is not in "
        "the set this run floors, and running it here would measure the pinned "
        "type checker against the floor's libraries and report neither"
    ),
}

REPAIRS = """\
floor: the run above failed at the declared floor, and the repair is a choice
rather than a reflex. Two directions, and they cost different people.

  RAISE THE DECLARED BOUND in pyproject.toml. The code keeps the newer
  interface, and the project stops claiming to work with the older version.
  That cost falls on every user who is pinned below the new bound and who now
  has no supported version to install.

  STOP USING THE NEWER INTERFACE. The bound stays where it is and the users
  below it keep working. That cost is whatever clarity or speed the newer
  interface was bought with, paid in this repository rather than by them.

Regenerate requirements.lock after either one; the command is in pyproject.toml
beside the bounds. Do not pin this run to something newer than the declaration
to make it pass, because this run IS the measurement of the declaration.\
"""


@dataclass(frozen=True)
class Bound:
    """One declared lower bound, and the pin a floor run installs for it."""

    name: str
    version: str

    @property
    def pin(self) -> str:
        return f"{self.name}=={self.version}"


def document() -> dict[str, object]:
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


def _project(loaded: dict[str, object]) -> dict[str, object]:
    project = loaded["project"]
    if not isinstance(project, dict):
        raise SystemExit("floor: REFUSED, [project] is not a table")
    return project


def lower_bound(requirement: str) -> Bound:
    """Read one declared requirement, or refuse it.

    Refusing is the point. A requirement this reader cannot resolve to a single
    lower bound has no floor to build against, and installing it unpinned would
    put the newest release into a run whose whole claim is that it used the
    oldest one.
    """
    written = requirement.strip()
    name_match = NAME.match(written)
    if name_match is None:
        raise SystemExit(f"floor: REFUSED, this is not a requirement: {requirement!r}")
    name = name_match.group(0)
    if ";" in written or "[" in written:
        raise SystemExit(
            f"floor: REFUSED, {name} carries an environment marker or an extra, "
            "and this reader does not carry either into the pin; a pin that "
            "silently dropped one would install a different set from the "
            "declaration it claims to be measuring"
        )
    bound_match = LOWER_BOUND.search(written)
    if bound_match is None:
        raise SystemExit(
            f"floor: REFUSED, {name} declares no lower bound, so there is no "
            "floor to build it against; give it one in pyproject.toml"
        )
    return Bound(name, bound_match.group(1))


def bounds() -> list[Bound]:
    declared = _project(document())["dependencies"]
    if not isinstance(declared, list):
        raise SystemExit("floor: REFUSED, project.dependencies is not a list")
    return [lower_bound(str(requirement)) for requirement in declared]


def interpreter() -> str:
    """The lowest interpreter the project claims to work with.

    Not the pin. `.python-version` names the interpreter the gate is measured
    on, and `tools/check_interpreter.py` says so where it refuses anything else.
    """
    declared = _project(document())["requires-python"]
    match = LOWER_BOUND.search(str(declared))
    if match is None:
        raise SystemExit(
            "floor: REFUSED, requires-python declares no lower bound, so there "
            "is no interpreter floor to run against"
        )
    return match.group(1)


def floor_legs() -> list[str]:
    return [
        leg.name
        for leg in gate.LEGS
        if leg.in_default_run and leg.name not in NOT_ON_THE_FLOOR
    ]


def run() -> int:
    """Run the legs a floor run answers for, through the gate that declares them."""
    command = [sys.executable, str(GATE)]
    for name in floor_legs():
        command += ["--leg", name]
    print(f"floor: {' '.join(command[1:])}", flush=True)
    completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build against the declared floor.")
    asked = parser.add_mutually_exclusive_group(required=True)
    asked.add_argument(
        "--pins",
        action="store_true",
        help="print the declared set pinned to its lower bounds, one per line",
    )
    asked.add_argument(
        "--interpreter",
        action="store_true",
        help="print the lowest interpreter version the project claims",
    )
    asked.add_argument(
        "--run",
        action="store_true",
        help="run the gate legs a floor run answers for",
    )
    asked.add_argument(
        "--repairs",
        action="store_true",
        help="print what to do about a failed floor run, in both directions",
    )
    arguments = parser.parse_args(argv)

    if arguments.pins:
        for bound in bounds():
            print(bound.pin)
        return 0
    if arguments.interpreter:
        print(interpreter())
        return 0
    if arguments.repairs:
        print(REPAIRS)
        return 0
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
