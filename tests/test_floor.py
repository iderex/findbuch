"""The floor is read from the declaration, and nothing holds a second copy of it.

A floor build against the wrong floor passes exactly like one against the right
floor, so the failure worth testing for here is not that the job runs. It is
that a version number has been written down twice and the two copies have moved
apart. That is what most of this file is about.

The rest is the reader itself, tested on the near misses somebody actually
writes: a bound spelled with the wrong comparison, a requirement with no bound
at all, and one carrying a marker the pin would silently drop.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "dependency-floor.yml"

sys.path.insert(0, str(REPO_ROOT / "tools"))

import floor  # noqa: E402
import gate  # noqa: E402


def declared() -> dict[str, object]:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        loaded = tomllib.load(handle)
    project = loaded["project"]
    assert isinstance(project, dict)
    return project


class TheBoundsAreReadFromTheDeclaration(unittest.TestCase):
    def test_every_declared_dependency_gets_a_pin_at_its_own_bound(self) -> None:
        requirements = declared()["dependencies"]
        assert isinstance(requirements, list)
        self.assertNotEqual(requirements, [])
        for requirement in requirements:
            written = str(requirement).replace(" ", "")
            with self.subTest(requirement=written):
                bound = floor.lower_bound(written)
                self.assertTrue(written.startswith(bound.name))
                self.assertIn(f">={bound.version}", written)
                self.assertEqual(bound.pin, f"{bound.name}=={bound.version}")

    def test_the_interpreter_floor_is_the_declared_lower_bound(self) -> None:
        written = str(declared()["requires-python"]).replace(" ", "")
        self.assertEqual(written, f">={floor.interpreter()}")


class ARequirementWithNoUsableBoundIsRefused(unittest.TestCase):
    def test_a_bound_is_read(self) -> None:
        bound = floor.lower_bound("sympy>=1.13")
        self.assertEqual((bound.name, bound.version), ("sympy", "1.13"))

    def test_a_strict_inequality_is_not_a_bound(self) -> None:
        # The one-character mistake: > where >= was meant. It names no version
        # the floor could install, and reading it as one would install whatever
        # came after 1.13 while reporting a run at 1.13.
        with self.assertRaises(SystemExit) as refused:
            floor.lower_bound("sympy>1.13")
        self.assertIn("declares no lower bound", str(refused.exception))

    def test_no_specifier_at_all_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as refused:
            floor.lower_bound("sympy")
        self.assertIn("declares no lower bound", str(refused.exception))

    def test_an_environment_marker_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as refused:
            floor.lower_bound('sympy>=1.13; python_version < "3.12"')
        self.assertIn("environment marker", str(refused.exception))

    def test_an_extra_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as refused:
            floor.lower_bound("sympy[cli]>=1.13")
        self.assertIn("extra", str(refused.exception))


class TheLegSetComesFromTheGate(unittest.TestCase):
    def test_every_dropped_leg_is_a_leg_the_gate_declares(self) -> None:
        # A dropped name that matches nothing drops nothing and reads as though
        # it did, which is the failure mode of every exclusion list.
        dangling = sorted(set(floor.NOT_ON_THE_FLOOR) - {leg.name for leg in gate.LEGS})
        self.assertEqual(dangling, [])

    def test_every_dropped_leg_carries_its_reason(self) -> None:
        for name, reason in floor.NOT_ON_THE_FLOOR.items():
            with self.subTest(leg=name):
                self.assertTrue(reason.strip())

    def test_the_suite_runs_and_the_interpreter_leg_does_not(self) -> None:
        legs = floor.floor_legs()
        self.assertIn("tests", legs)
        self.assertNotIn("interpreter", legs)

    def test_a_leg_added_to_the_default_run_arrives_here_by_itself(self) -> None:
        default = {leg.name for leg in gate.LEGS if leg.in_default_run}
        self.assertEqual(set(floor.floor_legs()), default - set(floor.NOT_ON_THE_FLOOR))


class TheWorkflowHoldsNoVersionOfItsOwn(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_the_workflow_asks_this_tool_for_every_number(self) -> None:
        for asked in ("--interpreter", "--pins", "--run", "--repairs"):
            with self.subTest(asked=asked):
                self.assertIn(f"tools/floor.py {asked}", self.text)

    def test_no_declared_version_is_written_in_the_workflow(self) -> None:
        numbers = [floor.interpreter()] + [bound.version for bound in floor.bounds()]
        for number in numbers:
            written = re.compile(rf"(?<![\w.]){re.escape(number)}(?![\w.])")
            with self.subTest(number=number):
                self.assertIsNone(
                    written.search(self.text),
                    f"{number} is declared in pyproject.toml and written again "
                    "here, so the two can move apart without anything saying so",
                )


class TheFailureSaysWhatToDoAboutIt(unittest.TestCase):
    def test_both_repairs_are_named(self) -> None:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "floor.py"), "--repairs"],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RAISE THE DECLARED BOUND", result.stdout)
        self.assertIn("STOP USING THE NEWER INTERFACE", result.stdout)


if __name__ == "__main__":
    unittest.main()
