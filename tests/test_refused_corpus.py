"""The corpus of files that must be refused, asserted by identity.

#22. A parser is only as good as the inputs it was tested against, and a
directory of valid rows tests nothing about a boundary. So this is the other
directory: one file per plausible mistake and one per plausible attack, each
refused, each asserted against the refusal identifier it has to earn.

WHY IDENTITY AND NOT "SOMETHING WAS RAISED". A test that only requires a refusal
passes when the fixture has a typo in it, and then it is a test about the typo.
`Refusal.code` is the identity, it is asserted with set equality rather than
membership, and the fragment beside it ties the refusal to THIS file's mistake:
four of the twelve entries earn `expression.unknown-symbol`, and without the
fragment any one of them would pass while refusing somebody else's symbol.

WHY EVERY ENTRY IS A PAIR. `tests/fixtures/refused/trips/x.toml` must be
refused; `tests/fixtures/refused/neighbour/x.toml` is the same row with the
mistake corrected and must load. Without the neighbour a validator that refused
every input would pass this whole file. The two are one change apart and that is
checked here rather than trusted, because a pair that drifted apart proves the
difference between two rows instead of the mistake.

The two halves share a file name so that the identifier inside each row is the
same string, which leaves the mistake as the only difference between them. The
identifier has to match the file name, which is 0003, and that is the whole
reason for the directory-per-half layout.

WHAT IS DELIBERATELY NOT HERE. Grammar facts about strings, which live in
tests/test_expression_grammar.py, and the near-misses for the two numeric limits,
which live in tests/test_expression_bounds.py. A fixture is a file because a
formula is proofread against a paper and nobody proofreads an escaped string; a
fact about the shape of the language is not proofread against anything.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import difflib
import unittest
from dataclasses import dataclass
from pathlib import Path

from findbuch.validation import Refusal, StructureRegistry, validate_file

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CORPUS = FIXTURES / "refused"
TRIPS = CORPUS / "trips"
NEIGHBOUR = CORPUS / "neighbour"


@dataclass(frozen=True)
class Entry:
    """One file that must be refused, and what it must be refused for.

    `names` is a fragment the refusal has to carry. It is the offending token
    where the refusal is about a token, and the limit where the refusal is about
    a limit, because that is what the message has to say for the person reading
    it beside a nineteenth century paper.
    """

    name: str
    code: str
    names: str


# The twelve entries #22 asks for, in the order that issue lists them: the
# mistakes somebody makes, then the attacks somebody writes on purpose. Adding
# an entry means a pair of files and a line here, and the first test below
# refuses either half on its own.
CORPUS_ENTRIES: tuple[Entry, ...] = (
    Entry("parameter-misspelled-by-one-letter", "expression.unknown-symbol", "A11"),
    Entry("multiplication-sign-dropped", "expression.unparseable", "not an expression"),
    Entry("subscript-as-the-source-wrote-it", "expression.subscript", "M[1]"),
    Entry("comma-where-a-decimal-point-belongs", "expression.node-refused", "Tuple"),
    Entry(
        "integral-on-a-coordinate-the-structure-lacks",
        "expression.unknown-symbol",
        "N3",
    ),
    Entry(
        "conditional-with-no-constraints",
        "validity.constraints-missing",
        "conditional",
    ),
    Entry(
        "constraint-mentions-an-undeclared-symbol", "expression.unknown-symbol", "B1"
    ),
    Entry("attribute-access", "expression.attribute-access", "A1.numerator"),
    Entry("call-outside-the-allowlist", "expression.unknown-function", "abs"),
    Entry("name-from-the-host-language", "expression.unknown-symbol", "__builtins__"),
    Entry("nested-past-the-depth-limit", "expression.too-deep", "64"),
    Entry("expansion-past-the-size-limit", "expression.too-large", "4096"),
)


def registry() -> StructureRegistry:
    return StructureRegistry.from_directory(FIXTURES / "structures")


def codes(refusals: tuple[Refusal, ...]) -> set[str]:
    return {refusal.code for refusal in refusals}


class TheCorpusOnDiskAndTheCorpusDeclaredHereAreTheSame(unittest.TestCase):
    """Checked before either is used as evidence.

    A file with no entry is a file nothing asserts anything about, and an entry
    with no file is a claim about a refusal that never runs. Both look like a
    green corpus from outside, so both are refused here.
    """

    def test_every_declared_entry_has_both_halves(self) -> None:
        for entry in CORPUS_ENTRIES:
            with self.subTest(entry=entry.name):
                self.assertTrue((TRIPS / f"{entry.name}.toml").is_file())
                self.assertTrue((NEIGHBOUR / f"{entry.name}.toml").is_file())

    def test_every_file_on_disk_is_declared(self) -> None:
        declared = {entry.name for entry in CORPUS_ENTRIES}
        for directory in (TRIPS, NEIGHBOUR):
            with self.subTest(directory=directory.name):
                found = {path.stem for path in directory.glob("*.toml")}
                self.assertEqual(sorted(found - declared), [])

    def test_the_corpus_is_not_empty(self) -> None:
        # A directory scan over nothing passes every case below in silence.
        self.assertNotEqual(sorted(TRIPS.glob("*.toml")), [])


class EachPairIsOneChangeApart(unittest.TestCase):
    """The neighbour differs from the file it stands beside in one place.

    A pair that drifted apart still passes both halves of the test below while
    proving something else: that a row with four differences is refused and a row
    with none is not. One contiguous edit is what makes the refusal attributable
    to the mistake.
    """

    def test_exactly_one_stretch_of_lines_differs(self) -> None:
        for entry in CORPUS_ENTRIES:
            with self.subTest(entry=entry.name):
                refused = (TRIPS / f"{entry.name}.toml").read_text(encoding="utf-8")
                accepted = (NEIGHBOUR / f"{entry.name}.toml").read_text(
                    encoding="utf-8"
                )
                edits = [
                    opcode
                    for opcode in difflib.SequenceMatcher(
                        None, refused.splitlines(), accepted.splitlines()
                    ).get_opcodes()
                    if opcode[0] != "equal"
                ]
                self.assertEqual(
                    len(edits),
                    1,
                    f"{entry.name}: the pair differs in {len(edits)} places, so a "
                    f"refusal cannot be attributed to the mistake this entry is "
                    f"about",
                )


class EveryFileInTheCorpusIsRefusedByItsOwnIdentifier(unittest.TestCase):
    def test_each_one_earns_the_declared_refusal_and_no_other(self) -> None:
        for entry in CORPUS_ENTRIES:
            with self.subTest(entry=entry.name, expected=entry.code):
                result = validate_file(TRIPS / f"{entry.name}.toml", registry())
                self.assertFalse(result.valid)
                # Set equality: a file refused for two reasons would pass a
                # membership check while the reader was told one thing about it.
                self.assertEqual(codes(result.refusals), {entry.code})

    def test_each_refusal_names_what_this_entry_is_about(self) -> None:
        for entry in CORPUS_ENTRIES:
            with self.subTest(entry=entry.name, names=entry.names):
                result = validate_file(TRIPS / f"{entry.name}.toml", registry())
                stated = " ".join(str(refusal) for refusal in result.refusals)
                self.assertIn(entry.names, stated)

    def test_the_rule_that_reads_formulas_actually_ran_on_each_one(self) -> None:
        # Every entry names e3, which resolves and declares its coordinates. If
        # it stopped resolving, the expression rule would not run, every file
        # here would load, and the two cases above would report that as a
        # corpus that had stopped being refused rather than as a broken
        # registry. This is what says which of the two happened.
        for entry in CORPUS_ENTRIES:
            with self.subTest(entry=entry.name):
                result = validate_file(TRIPS / f"{entry.name}.toml", registry())
                self.assertTrue(result.expressions_rule_evaluated)


class EveryNeighbourLoads(unittest.TestCase):
    """Without this the corpus above is satisfied by refusing everything."""

    def test_the_corrected_file_carries_no_refusal_at_all(self) -> None:
        for entry in CORPUS_ENTRIES:
            with self.subTest(entry=entry.name):
                result = validate_file(NEIGHBOUR / f"{entry.name}.toml", registry())
                self.assertEqual(
                    [str(refusal) for refusal in result.refusals],
                    [],
                    f"{entry.name}: the neighbour is the file with the mistake "
                    f"corrected and it has to load",
                )
                self.assertTrue(result.valid)


if __name__ == "__main__":
    unittest.main()
