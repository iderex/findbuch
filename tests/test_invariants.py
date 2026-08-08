"""Every declared invariant refuses its own fixture, and only its own.

THE FIXTURE DIRECTORY IS THE AUTHORITY HERE, NOT THE INVARIANT LIST. One test is
generated per directory under `tests/fixtures/invariants/`, and it looks up the
invariant named by that directory. If the tests were generated from the list
instead, deleting an invariant would delete its test along with it and the suite
would stay green over a rule that had been removed. Generated from the
directories, deleting an invariant leaves its fixtures with nothing to refuse
them and exactly one test fails.

Each generated test asserts three things. That an invariant of that name exists.
That the tripping fixture is refused by exactly that invariant and no other,
scanned against the whole list rather than against its own rule, because a
fixture refused by two rules proves neither of them. And that the one-change
neighbour is refused by nothing, because a rule that refuses the corrected file
as well refuses the file rather than the mistake.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import re
import subprocess
import sys
import unittest
from collections.abc import Callable
from pathlib import Path

from findbuch.invariants import (
    INVARIANTS,
    invariant,
    scan_file,
    scan_tree,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "invariants"
RUNNER = REPO_ROOT / "tools" / "check_invariants.py"

TRIPS = "trips.py.txt"
NEIGHBOUR = "neighbour.py.txt"


def fixture_directories() -> list[Path]:
    return sorted(path for path in FIXTURES.iterdir() if path.is_dir())


def refused_by(path: Path) -> set[str]:
    return {violation.invariant for violation in scan_file(path, INVARIANTS, path.name)}


class EachFixtureIsRefusedByItsOwnInvariantAndNoOther(unittest.TestCase):
    """One generated method per fixture directory. See the module docstring."""


def _make_case(directory: Path) -> Callable[[unittest.TestCase], None]:
    name = directory.name

    def case(self: unittest.TestCase) -> None:
        rule = invariant(name)
        self.assertIsNotNone(
            rule,
            f"there are fixtures at {directory.relative_to(REPO_ROOT).as_posix()} "
            f"and no invariant named '{name}' to refuse them; either the "
            f"invariant was removed without its fixtures or the directory is "
            f"misnamed",
        )
        trips = directory / TRIPS
        neighbour = directory / NEIGHBOUR
        self.assertTrue(trips.is_file(), f"{trips} is missing")
        self.assertTrue(neighbour.is_file(), f"{neighbour} is missing")
        self.assertEqual(
            refused_by(trips),
            {name},
            "the tripping fixture must be refused by exactly this invariant; "
            "refused by none means the pattern has stopped biting, refused by "
            "two means neither of them is proved by it",
        )
        self.assertEqual(
            refused_by(neighbour),
            set(),
            "the one-change neighbour must be refused by nothing, or the rule "
            "is refusing the file rather than the mistake in it",
        )

    case.__doc__ = f"The fixtures for {name}."
    return case


for _directory in fixture_directories():
    setattr(
        EachFixtureIsRefusedByItsOwnInvariantAndNoOther,
        f"test_{_directory.name.replace('-', '_')}",
        _make_case(_directory),
    )


class EveryInvariantIsWellFormed(unittest.TestCase):
    def test_every_invariant_has_a_fixture_directory(self) -> None:
        # The other direction from the generated tests: this catches an
        # invariant added with no fixtures, which would be a pattern nothing
        # proves bites.
        named = {directory.name for directory in fixture_directories()}
        missing = sorted(
            rule.identifier for rule in INVARIANTS if rule.identifier not in named
        )
        self.assertEqual(missing, [])

    def test_every_invariant_names_the_issue_that_decided_it(self) -> None:
        for rule in INVARIANTS:
            with self.subTest(invariant=rule.identifier):
                self.assertRegex(rule.decided_in, r"^#\d+$")

    def test_every_invariant_carries_a_reason(self) -> None:
        for rule in INVARIANTS:
            with self.subTest(invariant=rule.identifier):
                self.assertGreater(len(rule.reason.strip()), 80)

    def test_identifiers_are_unique(self) -> None:
        identifiers = [rule.identifier for rule in INVARIANTS]
        self.assertEqual(sorted(identifiers), sorted(set(identifiers)))


class TheTreeItselfIsClean(unittest.TestCase):
    def test_no_invariant_refuses_anything_in_this_repository(self) -> None:
        result = scan_tree(REPO_ROOT)
        self.assertEqual([str(v) for v in result.violations], [])

    def test_every_invariant_actually_read_a_file(self) -> None:
        # A rule whose path set reaches nothing has not passed, it has not run.
        result = scan_tree(REPO_ROOT)
        self.assertEqual(result.not_evaluated, ())


class ARuleThatReadNothingIsRefusedRatherThanReportedClean(unittest.TestCase):
    def test_an_empty_path_set_refuses(self) -> None:
        empty = REPO_ROOT / "tests" / "fixtures"
        result = scan_tree(empty)
        self.assertTrue(result.clean, "the fixtures hold no tracked source")
        self.assertEqual(
            sorted(result.not_evaluated),
            sorted(rule.identifier for rule in INVARIANTS),
        )

    def test_the_runner_exits_non_zero_on_it(self) -> None:
        finished = subprocess.run(
            [sys.executable, str(RUNNER), "--root", str(REPO_ROOT / "tests")],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
        )
        self.assertNotEqual(finished.returncode, 0, finished.stdout)
        self.assertIn("did not run", finished.stdout)


class TheRunnerSaysWhatItExamined(unittest.TestCase):
    def test_it_passes_over_this_tree_and_prints_a_count_per_invariant(self) -> None:
        finished = subprocess.run(
            [sys.executable, str(RUNNER)],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
        )
        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        for rule in INVARIANTS:
            with self.subTest(invariant=rule.identifier):
                self.assertRegex(
                    finished.stdout,
                    rf"{re.escape(rule.identifier)} \({re.escape(rule.decided_in)}\): "
                    rf"[1-9]\d* file\(s\) examined",
                )

    def test_it_names_what_it_does_not_scan(self) -> None:
        finished = subprocess.run(
            [sys.executable, str(RUNNER)],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
        )
        self.assertIn("excluded from every scan", finished.stdout)


# A test asserting that the import rule does not fire on the word "socket" in a
# comment was written here and then removed, because it made dropping one
# invariant redden two tests, and the property that dropping one reddens exactly
# one is what says the rules are not propping each other up. What is left of it
# is in the fixture: the neighbour for that rule writes "opens a socket" into its
# docstring, and the neighbour assertion requires that file to be refused by
# nothing, so the prose case is asserted where the fixture is.
#
# That is not a claim about the other four. Three of them need a call or an
# import line to match, so prose is out of reach by the shape of the pattern
# rather than by anything asserted here. The tolerance rule is the exception and
# it is deliberate: it matches the bare words "tolerance" and "epsilon", so
# writing either into shipped source is refused whether it is code or a comment.
# That is wider than the record requires and it is the price of catching the
# constant that arrives under a name instead of as a literal.


if __name__ == "__main__":
    unittest.main()
