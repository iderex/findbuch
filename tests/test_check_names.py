"""The seven check names the gate workflow may produce, and nothing else.

A check name is an interface. #57 makes these required on the default branch and
the protection rule matches them literally, so a name that is renamed, dropped or
quietly added later removes or invents a required check with nothing saying so.
The failure is silent in the worst direction: the protection rule keeps naming a
check that no longer runs, and a pull request that would have been refused is
merged because the check it waited for never reported.

So the names live here as data, taken from #17, and this module reads the
workflow and compares. A job renamed in `.github/workflows/gate.yml` reddens this
suite before it can reach the default branch.

THE SECOND HALF IS THAT NO JOB SPELLS A STEP OF ITS OWN. #17 asks that each job
run one leg of the same runner a contributor uses rather than repeating its steps
inline, because two spellings of one procedure drift and the one that drifts is
the one nobody runs by hand. That is checked twice below: every job has to invoke
`tools/gate.py`, and no `run:` line anywhere in the workflow may name one of the
tools a leg already wraps.

THE THIRD HALF IS THE LEG THAT IS IN NO JOB. Comparing names against the
workflow catches a rename. It says nothing about a leg that exists in
`tools/gate.py` and reaches no job at all, which is the way this workflow stops
covering the gate without any name moving. So the legs are partitioned: run by a
job, or named in NOT_A_JOB below with the reason it is not one. A leg in neither
is refused.

Standard library `unittest`, for the reason given in test_package_tree.py. The
workflow is read with a small reader rather than a YAML parser because the tree
carries no YAML library and this file is not a reason to add one; the reader
asserts the shape it assumes before it reports anything, so a workflow it cannot
read is a failure rather than an empty result.
"""

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "gate.yml"

sys.path.insert(0, str(REPO_ROOT / "tools"))

import gate  # noqa: E402

# From #17, in the order that issue lists them. This tuple is the interface and
# the workflow is measured against it, not the other way round.
CHECK_NAMES: tuple[str, ...] = (
    "unit tests",
    "lint and format",
    "types",
    "catalogue schema",
    "symbolic verification (fast)",
    "numeric verification (fast)",
    "headless and unprivileged",
)

# The legs of tools/gate.py that this workflow deliberately does not run, and why
# each one is out. A reason per entry, because "excluded" without one is how a
# leg leaves the gate and nobody notices.
NOT_A_JOB: dict[str, str] = {
    "interpreter": (
        "every job pins the interpreter through setup-python and .python-version, "
        "so the pin is applied here rather than checked; the leg is what a "
        "contributor's own machine needs"
    ),
    "invariants": (
        "it has its own workflow and the check name `Enforce greppable "
        "invariants`, which already exists; moving it here would rename a check"
    ),
    "sweep": (
        "out of the default run by construction, and it lands with its own "
        "harness in #34"
    ),
    "supply-chain": (
        "it reaches the package index and the advisory database, so it is out of "
        "the default run and out of this workflow; it has its own workflow and "
        "the check name `locked install and vulnerability scan`, which #53 "
        "creates"
    ),
    "fuzz-seeds": (
        "it has its own workflow and the check name `parser fuzz seed replay`, "
        "which #56 creates; putting it here would add an eighth name to the "
        "seven this file is the interface for"
    ),
}

# Spellings a job may not contain. Each is a tool some leg already wraps, and
# writing it in the workflow is the second spelling of one procedure.
INLINE_SPELLINGS: tuple[str, ...] = (
    "ruff",
    "pytest",
    "mypy",
    "toml-sort",
    "toml_sort",
    "coverage",
)

JOB_START = re.compile(r"^  (?P<identifier>[A-Za-z0-9_-]+):$")
JOB_NAME = re.compile(r"^    name: (?P<name>.+)$")
RUN_INLINE = re.compile(r"^(?P<indent> +)run: (?P<command>(?!\|).+)$")
RUN_BLOCK = re.compile(r"^(?P<indent> +)run: \|\s*$")
LEG_ARGUMENT = re.compile(r"--leg\s+(?P<leg>[a-z][a-z-]*)")


class Job:
    """One job block of the workflow, as the reader below recovered it."""

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        self.name: str | None = None
        self.run_lines: list[str] = []


def read_jobs(text: str) -> list[Job]:
    """Recover the job blocks, their check names and their `run:` bodies.

    Only the two indentation levels this workflow actually uses are understood:
    a job identifier at two spaces and its `name:` at four. Anything else is not
    silently ignored, because the tests below would then report on a workflow
    they had not read. `read_jobs` returns what it found and the first test
    asserts that what it found is a whole workflow.
    """
    lines = text.splitlines()
    try:
        start = lines.index("jobs:")
    except ValueError:
        return []

    jobs: list[Job] = []
    inside_block: str | None = None
    for line in lines[start + 1 :]:
        if inside_block is not None:
            if line.strip() and not line.startswith(inside_block):
                inside_block = None
            else:
                if line.strip():
                    jobs[-1].run_lines.append(line.strip())
                continue

        job_start = JOB_START.match(line)
        if job_start:
            jobs.append(Job(job_start.group("identifier")))
            continue
        if not jobs:
            continue

        job_name = JOB_NAME.match(line)
        if job_name and jobs[-1].name is None:
            jobs[-1].name = job_name.group("name").strip()
            continue

        block = RUN_BLOCK.match(line)
        if block:
            inside_block = block.group("indent") + " "
            continue

        inline = RUN_INLINE.match(line)
        if inline:
            jobs[-1].run_lines.append(inline.group("command").strip())

    return jobs


def legs_invoked(job: Job) -> set[str]:
    return {
        match.group("leg")
        for line in job.run_lines
        if "tools/gate.py" in line
        for match in LEG_ARGUMENT.finditer(line)
    }


class TheWorkflowWasReadBeforeAnythingIsClaimedAboutIt(unittest.TestCase):
    """A reader that recovered nothing would make every test below vacuous."""

    def test_the_workflow_file_is_in_the_tree(self) -> None:
        self.assertTrue(WORKFLOW.is_file(), f"{WORKFLOW} is not a file")

    def test_every_job_block_yielded_a_name_and_a_command(self) -> None:
        jobs = read_jobs(WORKFLOW.read_text(encoding="utf-8"))
        self.assertNotEqual(jobs, [], "no job block was recovered from the workflow")
        for job in jobs:
            with self.subTest(job=job.identifier):
                self.assertIsNotNone(job.name, "job block carries no name:")
                self.assertNotEqual(job.run_lines, [], "job block carries no run:")


class TheCheckNamesAreTheSevenThatWereDeclared(unittest.TestCase):
    def test_the_workflow_produces_exactly_these_names(self) -> None:
        produced = [job.name for job in read_jobs(WORKFLOW.read_text(encoding="utf-8"))]
        # Sorted set equality on both sides, then the count, so that a rename, an
        # addition, a removal and a duplicate each fail here and each say which.
        self.assertEqual(sorted(set(produced)), sorted(set(CHECK_NAMES)))
        self.assertEqual(len(produced), len(CHECK_NAMES))

    def test_each_name_is_greppable_in_the_workflow(self) -> None:
        # #17 asks for the names in a form a reader can grep, which is a
        # different claim from the parse above: it says the literal string is
        # there to be found by somebody with no parser at all.
        text = WORKFLOW.read_text(encoding="utf-8")
        for name in CHECK_NAMES:
            with self.subTest(name=name):
                self.assertIn(f"name: {name}\n", text)


class EveryJobRunsALegAndSpellsNoStepOfItsOwn(unittest.TestCase):
    def test_every_job_invokes_the_gate(self) -> None:
        for job in read_jobs(WORKFLOW.read_text(encoding="utf-8")):
            with self.subTest(job=job.identifier):
                self.assertTrue(
                    any("tools/gate.py" in line for line in job.run_lines),
                    "this job runs something that is not a leg of tools/gate.py",
                )

    def test_no_job_names_a_tool_a_leg_already_wraps(self) -> None:
        for job in read_jobs(WORKFLOW.read_text(encoding="utf-8")):
            for line in job.run_lines:
                for spelling in INLINE_SPELLINGS:
                    with self.subTest(job=job.identifier, spelling=spelling):
                        # The install steps read the lock files by path and name
                        # no tool, so this reaches them without an exception.
                        self.assertNotIn(spelling, line)

    def test_every_leg_named_by_a_job_exists_in_the_gate(self) -> None:
        declared = {leg.name for leg in gate.LEGS}
        for job in read_jobs(WORKFLOW.read_text(encoding="utf-8")):
            with self.subTest(job=job.identifier):
                self.assertLessEqual(legs_invoked(job), declared)


class NoLegOfTheGateFallsOutOfTheWorkflowInSilence(unittest.TestCase):
    def test_the_legs_partition_into_run_here_and_named_as_not_run(self) -> None:
        jobs = read_jobs(WORKFLOW.read_text(encoding="utf-8"))
        run_here = set().union(*(legs_invoked(job) for job in jobs))
        declared = {leg.name for leg in gate.LEGS}
        self.assertEqual(
            sorted(run_here | set(NOT_A_JOB)),
            sorted(declared),
            "a leg of tools/gate.py is neither run by a job here nor named in "
            "NOT_A_JOB with the reason it is not one",
        )

    def test_nothing_is_both_run_here_and_named_as_not_run(self) -> None:
        jobs = read_jobs(WORKFLOW.read_text(encoding="utf-8"))
        run_here = set().union(*(legs_invoked(job) for job in jobs))
        self.assertEqual(sorted(run_here & set(NOT_A_JOB)), [])

    def test_every_exclusion_carries_a_reason(self) -> None:
        for leg, reason in NOT_A_JOB.items():
            with self.subTest(leg=leg):
                self.assertTrue(reason.strip())


if __name__ == "__main__":
    unittest.main()
