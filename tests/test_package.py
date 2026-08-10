"""What can be decided about the packaging without building anything.

The three phases of `tools/package.py` all reach the package index, so none of
them runs here. What runs here is everything around them that a build would
otherwise be the only way to find out about: the three check names the workflow
declares, the leg the gate declares and keeps out of its default run, the
agreement between the probe and the report that reads it back, and the one
decision `install` makes on its own.

THE EXECUTED PROOF IS ELSEWHERE AND THAT IS SAID HERE SO IT IS NOT ASSUMED. That
the import check refuses an environment the wheel was not installed into, and
that the validation refuses a document missing a required field, are proven by

    python tools/package.py --selftest

which is the first step of the `package` and `SBOM` jobs and runs before either
verdict is taken. It is not a unit test because the second of its two rows needs
a CycloneDX document, and the writer that produces one is in the package set
rather than the gate set, so a unit test asserting it would either skip itself or
add a dependency to every run of the suite.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import contextlib
import io
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "package.yml"

sys.path.insert(0, str(REPO_ROOT / "tools"))

import gate  # noqa: E402
import package  # noqa: E402

# From #51, in the order that issue lists them. The workflow is measured against
# this tuple and not the other way round, for the reason test_check_names.py
# gives at length: a check name is an interface and #57 matches it literally.
CHECK_NAMES: tuple[str, ...] = ("build", "package", "SBOM")

JOB_NAME = re.compile(r"^    name: (?P<name>.+)$", re.MULTILINE)
RUN_LINE = re.compile(r"^\s+run: (?P<command>(?!\|).+)$", re.MULTILINE)

# What a probe prints when everything travelled. Written out rather than taken
# from a run, so the test below says what `install` does with an answer rather
# than what today's package happens to answer.
PROBE_OUTPUT = "\n".join(
    (
        "import-ok /somewhere/site-packages/findbuch/__init__.py",
        "schema True /somewhere/site-packages/findbuch/schema/row-1.0.schema.json",
        "structures True /somewhere/site-packages/findbuch/structures",
        "registry 3",
    )
)


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def reported(outcome: package.Outcome) -> tuple[int, str]:
    """Run the report and keep both what it decided and what it printed."""
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        code = package.report_probe(outcome)
    return code, captured.getvalue()


class TheWorkflowWasReadBeforeAnythingIsClaimedAboutIt(unittest.TestCase):
    def test_the_workflow_file_is_in_the_tree(self) -> None:
        self.assertTrue(WORKFLOW.is_file(), f"{WORKFLOW} is not a file")

    def test_the_reader_recovered_a_job_and_a_command(self) -> None:
        text = workflow_text()
        self.assertNotEqual(JOB_NAME.findall(text), [])
        self.assertNotEqual(RUN_LINE.findall(text), [])


class TheCheckNamesAreTheThreeThatWereDeclared(unittest.TestCase):
    def test_the_workflow_produces_exactly_these_names(self) -> None:
        produced = JOB_NAME.findall(workflow_text())
        self.assertEqual(sorted(set(produced)), sorted(set(CHECK_NAMES)))
        self.assertEqual(len(produced), len(CHECK_NAMES))

    def test_each_name_is_greppable_in_the_workflow(self) -> None:
        text = workflow_text()
        for name in CHECK_NAMES:
            with self.subTest(name=name):
                self.assertIn(f"name: {name}\n", text)


class EveryJobRunsTheToolAndSpellsNoStepOfItsOwn(unittest.TestCase):
    def test_every_command_names_the_tool(self) -> None:
        for command in RUN_LINE.findall(workflow_text()):
            with self.subTest(command=command):
                self.assertIn("tools/package.py", command)

    def test_the_workflow_names_neither_the_builder_nor_the_writer(self) -> None:
        # Over the whole file rather than over the inline commands, because a
        # second spelling of either procedure would be as much of a drift in a
        # block step as in a one-line one.
        text = workflow_text()
        for spelling in ("-m build", "cyclonedx", "pyproject.toml build"):
            with self.subTest(spelling=spelling):
                self.assertNotIn(spelling, text)


class TheGateDeclaresThePackageLegAndSaysWhatItCosts(unittest.TestCase):
    def leg(self) -> gate.Leg:
        found = [leg for leg in gate.LEGS if leg.name == "package"]
        self.assertEqual(len(found), 1, "tools/gate.py declares no `package` leg")
        return found[0]

    def test_the_leg_runs_this_tool(self) -> None:
        self.assertIn("package.py", " ".join(self.leg().command))

    def test_the_leg_is_out_of_the_default_run(self) -> None:
        # It builds, installs and resolves against the index, so a contributor
        # with no network still runs the whole default gate.
        self.assertFalse(self.leg().in_default_run)

    def test_asking_for_it_does_not_start_the_other_two_opt_ins(self) -> None:
        asked = {leg.name for leg in gate.selected(None, {"package"})}
        self.assertIn("package", asked)
        self.assertNotIn("sweep", asked)
        self.assertNotIn("supply-chain", asked)


class TheProbeAndTheReportAgreeOnWhatEachAnswerIsCalled(unittest.TestCase):
    """The report reads the probe's output back by key, so the two can drift.

    A key renamed on one side and not the other prints `not measured` for an
    answer the probe supplied, which reads as an unanswered question rather than
    as a broken test. This is what refuses that.
    """

    def test_every_measured_key_is_printed_by_the_probe(self) -> None:
        for key, _, _ in package.PACKAGE_DATA:
            with self.subTest(key=key):
                self.assertIn(f'print("{key} ', package.PROBE)

    def test_the_registry_count_is_printed_by_the_probe(self) -> None:
        self.assertIn('print("registry ', package.PROBE)


class TheReportRefusesOnTheImportAndOnlyOnTheImport(unittest.TestCase):
    def test_a_probe_that_failed_is_refused_by_name(self) -> None:
        code, printed = reported(package.Outcome(1, "ModuleNotFoundError: findbuch"))
        self.assertEqual(code, 1)
        self.assertIn("package.import-failed", printed)

    def test_a_probe_that_imported_is_not_refused(self) -> None:
        code, _ = reported(package.Outcome(0, PROBE_OUTPUT))
        self.assertEqual(code, 0)

    def test_the_measurement_reaches_the_output(self) -> None:
        _, printed = reported(package.Outcome(0, PROBE_OUTPUT))
        for _, description, name in package.PACKAGE_DATA:
            with self.subTest(name=name):
                self.assertIn(description, printed)
                self.assertIn(name, printed)
        self.assertIn("structures the registry loaded: 3", printed)

    def test_the_report_says_it_did_not_refuse_what_it_measured(self) -> None:
        # The line that stops a green tick on this leg from being read as
        # saying the package data travelled. #84 is what removes it.
        _, printed = reported(package.Outcome(0, PROBE_OUTPUT))
        self.assertIn("NOT REFUSED HERE", printed)
        self.assertIn("#84", printed)


if __name__ == "__main__":
    unittest.main()
