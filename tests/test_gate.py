"""The gate's leg list is the only leg list.

Two procedures for one gate is the failure this whole command exists against, so
what is worth testing is not that ruff runs but that nothing can quietly hold a
second copy of the list, and that a leg which does not run says so.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / "tools" / "gate.py"

sys.path.insert(0, str(REPO_ROOT / "tools"))

import gate  # noqa: E402


def run_gate(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), *arguments],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )


class TheLegListIsDeclaredOnce(unittest.TestCase):
    def test_names_are_unique(self) -> None:
        names = [leg.name for leg in gate.LEGS]
        self.assertEqual(sorted(names), sorted(set(names)))

    def test_list_prints_every_leg(self) -> None:
        result = run_gate(["--list"])
        self.assertEqual(result.returncode, 0, result.stderr)
        printed = {line.split("\t")[0] for line in result.stdout.splitlines() if line}
        self.assertEqual(printed, {leg.name for leg in gate.LEGS})

    def test_every_leg_states_what_it_costs(self) -> None:
        for leg in gate.LEGS:
            with self.subTest(leg=leg.name):
                self.assertTrue(leg.cost.strip())
                self.assertTrue(leg.what.strip())


class ALegThatDidNotRunSaysSo(unittest.TestCase):
    def test_the_sweep_is_out_of_the_default_run_and_is_named(self) -> None:
        sweep = next(leg for leg in gate.LEGS if leg.name == "sweep")
        self.assertFalse(sweep.in_default_run)
        result = run_gate(["--leg", "interpreter"])
        self.assertIn("sweep: NOT RUN", result.stdout)
        self.assertIn(sweep.cost.splitlines()[0][:40], result.stdout)

    def test_an_unknown_leg_is_refused(self) -> None:
        result = run_gate(["--leg", "no-such-leg"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no such leg", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
