"""The two fast verification legs refuse a row they cannot decide.

`symbolic verification (fast)` and `numeric verification (fast)` are check names
before they are criteria. #17 asks for the name to exist from the beginning so
the job can grow into it, and the danger in that is exact: a green check under
one of these names says the row was verified, and until #26 and #30 land nothing
verified it.

So the leg refuses any row it cannot decide, and this is the test of that
refusal. It is the guard that makes the empty name safe to create, and a guard
nobody proves is a guard that quietly stops biting. Delete either `return 1` in
`tools/verify_symbolic_fast.py` or `tools/verify_numeric_fast.py` and the case
below reddens.

THE PAIR, following the shape in test_refusal_shape.py. The tripping fixture is
`tests/fixtures/rows/`, a directory holding one row. The neighbour one change
away is `tests/fixtures/catalogue-with-no-rows/`, a directory holding no row.
Without the neighbour, a leg that refused every catalogue would pass the first
half and the check name would be red forever instead of honest.

WHAT IS ASSERTED IS THE IDENTITY OF THE REFUSAL rather than the fact of one.
These legs are processes rather than library calls, so the identity is the exit
code together with the marker the leg prints against the row it would not
decide. A leg that exited non-zero because its own argument parsing failed would
pass a returncode check alone and would say nothing about the guard.
"""

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

HOLDS_A_ROW = FIXTURES / "rows"
HOLDS_NO_ROW = FIXTURES / "catalogue-with-no-rows"

LEGS: dict[str, Path] = {
    "symbolic-fast": REPO_ROOT / "tools" / "verify_symbolic_fast.py",
    "numeric-fast": REPO_ROOT / "tools" / "verify_numeric_fast.py",
}


def run_leg(entry_point: Path, catalogue: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(entry_point), "--catalogue", str(catalogue)],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )


class TheFixturePairIsWhatItClaimsToBe(unittest.TestCase):
    """Both halves are checked before either is used as evidence."""

    def test_the_tripping_directory_holds_a_row(self) -> None:
        self.assertNotEqual(sorted(HOLDS_A_ROW.glob("*.toml")), [])

    def test_the_neighbour_holds_no_row_and_is_a_directory(self) -> None:
        self.assertTrue(HOLDS_NO_ROW.is_dir())
        self.assertEqual(sorted(HOLDS_NO_ROW.glob("*.toml")), [])


class ARowNothingVerifiedIsRefused(unittest.TestCase):
    def test_each_leg_refuses_and_names_the_row_it_could_not_decide(self) -> None:
        for leg, entry_point in LEGS.items():
            with self.subTest(leg=leg):
                result = run_leg(entry_point, HOLDS_A_ROW)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("NOT DECIDED", result.stdout)
                self.assertIn("euler.toml", result.stdout)
                self.assertIn("REFUSED", result.stdout)

    def test_each_leg_names_the_record_that_holds_the_criterion(self) -> None:
        # The refusal is only actionable if it says what would make the row
        # decidable, so the record and the issue are part of what is asserted.
        expected = {
            "symbolic-fast": ("docs/decisions/0006-symbolic-criterion.md", "#26"),
            "numeric-fast": ("docs/decisions/0007-numeric-criterion.md", "#30"),
        }
        for leg, entry_point in LEGS.items():
            with self.subTest(leg=leg):
                result = run_leg(entry_point, HOLDS_A_ROW)
                for reference in expected[leg]:
                    self.assertIn(reference, result.stdout)


class ACatalogueWithNoRowPasses(unittest.TestCase):
    def test_each_leg_passes_over_the_neighbour_and_says_what_it_examined(
        self,
    ) -> None:
        for leg, entry_point in LEGS.items():
            with self.subTest(leg=leg):
                result = run_leg(entry_point, HOLDS_NO_ROW)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("examined 0 row(s)", result.stdout)
                self.assertNotIn("REFUSED", result.stdout)

    def test_passing_is_not_reported_as_having_verified_anything(self) -> None:
        # A leg that printed nothing and exited zero would pass the case above.
        # What keeps the green check honest is that the run says no row has been
        # through it.
        for leg, entry_point in LEGS.items():
            with self.subTest(leg=leg):
                result = run_leg(entry_point, HOLDS_NO_ROW)
                self.assertIn("no row has been through this check yet", result.stdout)


class AMissingDirectoryReadsAsZeroRowsAndSaysWhereItLooked(unittest.TestCase):
    """What these legs do NOT refuse, asserted so it is not read as a gap.

    A catalogue path that does not exist yields no row and the leg exits zero,
    which is the same verdict `tools/check_catalogue_schema.py` gives and is
    deliberately not diverged from here. The protection against a catalogue
    deleted or mistyped into invisibility is that the run names the directory it
    looked in, and that is what this asserts. It is weaker than a refusal and it
    is not offered as one.
    """

    def test_a_missing_directory_is_reported_by_name(self) -> None:
        missing = FIXTURES / "catalogue-that-is-not-there"
        self.assertFalse(missing.exists())
        for leg, entry_point in LEGS.items():
            with self.subTest(leg=leg):
                result = run_leg(entry_point, missing)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(missing.name, result.stdout)


if __name__ == "__main__":
    unittest.main()
