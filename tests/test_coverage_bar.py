"""Every shipped module is on one side of the bar, and somebody put it there.

The bar is on a small surface today, because the code that decides a verdict is
mostly not written yet. So the failure this file is aimed at is not a number
that slipped: it is the checker landing in #21, #26 and #30 and joining the tree
on the ungated side without anybody noticing, after which the bar is green
forever over the one module that was already covered.

A shipped module therefore has to appear in exactly one of the two lists, and a
list entry has to name a file the tree actually tracks. Both directions fail
closed, which is the same shape `tests/test_type_check_coverage.py` uses over
the type checker's module set and for the same reason.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "coverage.yml"

sys.path.insert(0, str(REPO_ROOT / "tools"))

import coverage_bar  # noqa: E402


def shipped_modules() -> set[str]:
    listed = subprocess.run(
        ["git", "ls-files", "--", "src/*.py", "src/**/*.py", "tools/*.py"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    return {line for line in listed.stdout.splitlines() if line}


class EveryShippedModuleIsPlaced(unittest.TestCase):
    def setUp(self) -> None:
        self.gated = set(coverage_bar.VERDICT_SURFACE)
        self.reported = set(coverage_bar.REPORTED_ONLY)

    def test_the_tree_holds_shipped_modules_to_place(self) -> None:
        # A path set that reaches nothing places nothing and passes silently.
        self.assertNotEqual(shipped_modules(), set())

    def test_no_shipped_module_is_unplaced(self) -> None:
        unplaced = sorted(shipped_modules() - self.gated - self.reported)
        self.assertEqual(
            unplaced,
            [],
            "these modules are in neither VERDICT_SURFACE nor REPORTED_ONLY in "
            "tools/coverage_bar.py, so nothing has decided whether a regression "
            "in them can turn a wrong row green; put each one on a side, with "
            "the reason",
        )

    def test_no_entry_names_a_file_the_tree_does_not_have(self) -> None:
        dangling = sorted((self.gated | self.reported) - shipped_modules())
        self.assertEqual(
            dangling,
            [],
            "these entries name paths that are not tracked shipped modules, so "
            "the lists describe a tree that is not this one",
        )

    def test_no_module_is_on_both_sides(self) -> None:
        self.assertEqual(sorted(self.gated & self.reported), [])

    def test_the_gated_surface_is_not_empty(self) -> None:
        # An empty surface makes --fail-under pass over nothing at all.
        self.assertNotEqual(self.gated, set())

    def test_every_placement_carries_its_reason(self) -> None:
        placements = {**coverage_bar.VERDICT_SURFACE, **coverage_bar.REPORTED_ONLY}
        for module, reason in placements.items():
            with self.subTest(module=module):
                self.assertTrue(reason.strip())


class TheBarHasOneHome(unittest.TestCase):
    def test_the_bar_is_a_whole_number_percentage(self) -> None:
        self.assertIsInstance(coverage_bar.BAR, int)
        self.assertGreater(coverage_bar.BAR, 0)
        self.assertLessEqual(coverage_bar.BAR, 100)

    def test_the_tool_prints_the_bar(self) -> None:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "coverage_bar.py"), "--bar"],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(coverage_bar.BAR))

    def test_the_workflow_does_not_write_the_bar_down_again(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        written = re.compile(rf"(?<![\w.]){coverage_bar.BAR}(?![\w.])")
        self.assertIsNone(
            written.search(text),
            "the bar is declared in tools/coverage_bar.py with the reason for "
            "its value; a second copy here moves apart from it in silence",
        )

    def test_the_workflow_runs_the_tool(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tools/coverage_bar.py", text)


if __name__ == "__main__":
    unittest.main()
