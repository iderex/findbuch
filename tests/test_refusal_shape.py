"""The shape every later refusal test in this suite follows, on the smallest refusal.

THE SHAPE, in three parts, and the third is the one that gets skipped.

1. The test names the fixture that trips the refusal. A fixture is a file under
   tests/fixtures/, not a string in the source, because a formula is proofread
   against a paper and nobody proofreads an escaped string.

2. It names the fixture one change away that must NOT trip it. Without the
   neighbour, a validator that refused every input would pass.

3. It asserts on the IDENTITY of the refusal, not on the fact that something
   was refused. `Refusal.code` is the identity. Asserting that a call raised, or
   that a list of refusals is non-empty, is not evidence that the refusal fired
   for the stated reason: a typo in the fixture refuses too, and it refuses for a
   reason the test was not written about.

The refusal demonstrated here is deliberately the most trivial one in the
project, validating a path where no file exists. It is here so that the shape is
in the tree, exercised, before anything that matters uses it. The negative
corpus over the expression grammar is #22 and follows this shape over many
files; the checkers in milestones 4 and 5 follow it over mutated rows.

WHY THE TRIPPING FIXTURE IS A PATH AND NOT A FILE. This refusal is about a file
that is not there, so the fixture cannot be committed; what is committed is the
one-change neighbour beside it, and the test asserts the absence rather than
assuming it. If somebody later creates the missing name, the assertion below
reddens instead of the pair quietly becoming vacuous.

The suite runs under pytest, and the classes here are `unittest.TestCase`
subclasses because pytest collects them unchanged and the seventy-six tests that
predate this decision are written that way. What a later test may use, and what
`unittest` alone cannot express, is a parametrised case per fixture file, which
is what #22's corpus needs to report a refusal identifier per file rather than
one verdict for a directory.
"""

import unittest
from pathlib import Path

from findbuch.validation import Refusal, StructureRegistry, validate_file

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# The pair. One character apart in the suffix, which is the mistake somebody
# actually makes; a fixture that could not have been written by accident proves
# less than one that nearly was.
TRIPS = FIXTURES / "rows" / "euler.tml"
NEIGHBOUR = FIXTURES / "rows" / "euler.toml"


def registry() -> StructureRegistry:
    return StructureRegistry.from_directory(FIXTURES / "structures")


def codes(refusals: tuple[Refusal, ...]) -> set[str]:
    return {refusal.code for refusal in refusals}


class TheFixturePairIsWhatItClaimsToBe(unittest.TestCase):
    """Both halves of the pair are checked before either is used as evidence."""

    def test_the_tripping_path_holds_no_file(self) -> None:
        self.assertFalse(
            TRIPS.exists(),
            f"{TRIPS.name} exists, so the refusal below is no longer about a "
            "missing file and this pair proves nothing",
        )

    def test_the_neighbour_is_one_change_away_and_is_a_file(self) -> None:
        self.assertTrue(NEIGHBOUR.is_file())
        self.assertEqual(TRIPS.parent, NEIGHBOUR.parent)
        self.assertEqual(TRIPS.stem, NEIGHBOUR.stem)


class AMissingFileIsRefusedByIdentifier(unittest.TestCase):
    """One test, on purpose.

    The done-condition of #15 asks that removing the refusal from the source
    make EXACTLY ONE test fail. Two tests that both call `validate_file` on the
    missing path would both fail, and a mutation that reddens two tests says
    less about which one is the guard than a mutation that reddens one.
    """

    def test_the_refusal_is_file_missing_and_nothing_else(self) -> None:
        result = validate_file(TRIPS, registry())
        # Set equality rather than membership: a validator that refused this
        # path for two reasons would pass a membership check while telling the
        # reader something different from what this test claims.
        self.assertEqual(codes(result.refusals), {"file.missing"})
        self.assertFalse(result.valid)
        # The code is the identity and the message is for a person, so this
        # asserts that the message names the path and not how it is worded.
        self.assertIn(TRIPS.name, str(result.refusals[0]))
        # Nothing was read, so no rule ran over it. This is asserted here rather
        # than in a second test because of the paragraph above: it is one more
        # claim about the same call. A result that reported a rule as evaluated
        # on a file it never opened would be saying a check happened, and the
        # mutation sample found that the flag on this path could be flipped with
        # the whole suite green.
        self.assertFalse(result.parameters_rule_evaluated)
        self.assertFalse(result.expressions_rule_evaluated)


class TheNeighbourOneChangeAwayIsAccepted(unittest.TestCase):
    def test_the_file_that_exists_is_not_refused(self) -> None:
        result = validate_file(NEIGHBOUR, registry())
        self.assertEqual([str(refusal) for refusal in result.refusals], [])
        self.assertTrue(result.valid)


class ARefusalCarriesAStableIdentity(unittest.TestCase):
    """What a test is allowed to assert on, and what it is not."""

    def test_the_code_is_the_part_a_test_asserts_on(self) -> None:
        refusal = Refusal("file.missing", "a message that may be reworded", "x.toml")
        self.assertEqual(refusal.code, "file.missing")
        self.assertIn("file.missing", str(refusal))

    def test_two_refusals_with_one_code_are_one_identity(self) -> None:
        # Deduplication of verdicts elsewhere depends on this, so it is asserted
        # rather than assumed from the dataclass being frozen.
        first = Refusal("file.missing", "one wording", "a.toml")
        second = Refusal("file.missing", "another wording", "b.toml")
        self.assertEqual(codes((first, second)), {"file.missing"})


if __name__ == "__main__":
    unittest.main()
