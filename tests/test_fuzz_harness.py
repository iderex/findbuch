"""The fuzz harness reports a finding, and only then is its silence worth anything.

#56. The job that replays the corpus is green when the parser held. That is the
same output a harness produces when its finding branch never runs, when its
corpus is not there, and when it decided that every identifier is a known one. So
each of those is made to happen here, on purpose, and required to be reported.

WHAT IS ASSERTED, in the order that matters:

1. The failure paths bite. A parser that raises an unhandled error, a parser that
   refuses with an identifier nobody declared, an absent corpus and an empty one
   are each turned into a finding or a refusal, and the identity of the finding
   is asserted rather than the fact that something was returned.
2. The declared identifier set matches what the parser raises. `REFUSALS` is a
   list beside the code, so it is compared against every identifier literal in
   that module's own source. A refusal added without adding it there would be
   reported by the harness as unknown, which reads as a defect in the parser.
3. The corpus is not empty and every seed in it is admitted. That is the same
   property the job replays, and it is here as well so a contributor running the
   suite finds it out before the job does.

Standard library `unittest`, for the reason given in test_package_tree.py. It is
run directly by the fuzz workflow as well as by pytest, so nothing here may use a
pytest feature.
"""

import re
import unittest
from pathlib import Path

import sympy

from findbuch.expression import REFUSALS, ExpressionRefused, SymbolTable
from findbuch.fuzz import (
    SEEDS,
    CorpusRefused,
    Seed,
    as_seed_file,
    read_corpus,
    read_seed,
    replay,
    replay_one,
    search,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PARSER_SOURCE = REPO_ROOT / "src" / "findbuch" / "expression.py"
IDENTIFIER = re.compile(r'"(expression\.[a-z-]+)"')

A_SEED = Seed("a-seed", "for the cases below", b"M1 + M2")


# Three parsers that misbehave in the three ways the harness exists to notice.
# The arguments are named for the signature they stand in for and neither is
# read, which is what the suppression is about; a stand-in that read them would
# be a fourth parser rather than a control.
def raises_unhandled(text: str, table: SymbolTable) -> sympy.Expr:  # noqa: ARG001
    raise ZeroDivisionError("an error the parser was never supposed to produce")


def refuses_with_an_undeclared_identifier(
    text: str,  # noqa: ARG001
    table: SymbolTable,  # noqa: ARG001
) -> sympy.Expr:
    raise ExpressionRefused("expression.invented-here", "an identifier nobody declared")


def admits_everything(text: str, table: SymbolTable) -> sympy.Expr:  # noqa: ARG001
    return sympy.Integer(0)


class TheHarnessReportsWhatItIsFor(unittest.TestCase):
    def test_an_unhandled_error_is_a_finding_naming_its_type(self) -> None:
        finding = replay_one(A_SEED, raises_unhandled)
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.kind, "unhandled-error")
        self.assertIn("ZeroDivisionError", finding.detail)
        self.assertEqual(finding.seed, A_SEED.name)

    def test_a_refusal_nobody_declared_is_a_finding_of_its_own_kind(self) -> None:
        # A different kind from the one above, because they are different
        # defects: one is a boundary that fell over and one is a boundary that
        # refused for a reason no test can assert on.
        finding = replay_one(A_SEED, refuses_with_an_undeclared_identifier)
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.kind, "unknown-identifier")
        self.assertIn("expression.invented-here", finding.detail)

    def test_a_finding_carries_the_bytes_that_produced_it(self) -> None:
        # Otherwise a finding from the search cannot be added to the corpus,
        # which is the half of #56 that stops the corpus growing only by hand.
        finding = replay_one(A_SEED, raises_unhandled)
        assert finding is not None
        self.assertEqual(finding.data, A_SEED.data)
        self.assertIn("TTEgKyBNMg==", as_seed_file(Seed("x", "y", finding.data)))

    def test_an_admitted_outcome_is_not_a_finding(self) -> None:
        # The other side of all three. Without it, a harness that reported
        # everything would pass every case above.
        self.assertIsNone(replay_one(A_SEED, admits_everything))


class TheCorpusItselfIsRefusedWhenItSaysNothing(unittest.TestCase):
    """Both empty answers, which #56 names as failures rather than passes."""

    def test_a_corpus_directory_that_is_not_there_is_refused(self) -> None:
        with self.assertRaises(CorpusRefused) as refused:
            read_corpus(REPO_ROOT / "tests" / "fixtures" / "fuzz" / "not-a-directory")
        self.assertIn("no corpus", str(refused.exception))

    def test_a_corpus_directory_that_holds_nothing_is_refused(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(CorpusRefused) as refused:
                read_corpus(Path(empty))
            self.assertIn("holds no seed", str(refused.exception))

    def test_a_seed_file_with_no_payload_line_is_refused(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "described-and-unfinished.b64"
            path.write_text("# a description and nothing else", encoding="utf-8")
            with self.assertRaises(CorpusRefused) as refused:
                read_seed(path)
            self.assertIn("carries no seed", str(refused.exception))

    def test_a_seed_of_no_bytes_is_a_seed_and_not_a_refusal(self) -> None:
        # The distinction the case above turns on. An empty input is an input.
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.b64"
            path.write_text("# nothing at all\n\n", encoding="utf-8")
            self.assertEqual(read_seed(path).data, b"")

    def test_a_payload_that_is_not_base64_is_refused(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrupt.b64"
            path.write_text("# corrupt\n!!!!not base64!!!!\n", encoding="utf-8")
            with self.assertRaises(CorpusRefused) as refused:
                read_seed(path)
            self.assertIn("not base64", str(refused.exception))


class TheDeclaredIdentifiersAreTheOnesTheParserRaises(unittest.TestCase):
    def test_the_set_beside_the_code_matches_the_code(self) -> None:
        source = PARSER_SOURCE.read_text(encoding="utf-8")
        # Every literal in the module, minus the declaration itself, which is
        # where all of them also appear.
        declaration = source.index("REFUSALS: frozenset[str]")
        after = source.index("class ExpressionRefused", declaration)
        raised = set(IDENTIFIER.findall(source[:declaration] + source[after:]))
        self.assertEqual(
            sorted(raised),
            sorted(REFUSALS),
            "REFUSALS in findbuch.expression and the identifiers that module "
            "raises have come apart; the fuzz harness would report the "
            "undeclared one as a defect in the parser",
        )

    def test_the_set_is_not_empty(self) -> None:
        # A declaration that had emptied out would make every refusal unknown,
        # and the case above compares two sets that could both be empty.
        self.assertNotEqual(sorted(REFUSALS), [])


class TheCommittedCorpusHoldsAndPasses(unittest.TestCase):
    def test_the_corpus_is_not_empty(self) -> None:
        self.assertGreater(len(read_corpus(SEEDS)), 1)

    def test_every_seed_produces_an_admitted_outcome(self) -> None:
        findings = replay(read_corpus(SEEDS))
        self.assertEqual([str(finding) for finding in findings], [])

    def test_every_seed_is_described(self) -> None:
        # A seed nobody described is a seed nobody can decide to remove, and a
        # corpus of undescribed bytes is where the ones that stopped meaning
        # anything accumulate.
        for seed in read_corpus(SEEDS):
            with self.subTest(seed=seed.name):
                self.assertNotEqual(seed.what.strip(), "")

    def test_the_search_derives_inputs_and_they_pass_as_well(self) -> None:
        # One round over the corpus, which is seconds. The deep search is out of
        # the suite for the same reason it is out of the gate.
        findings, tried = search(read_corpus(SEEDS), 1)
        self.assertGreater(tried, len(read_corpus(SEEDS)))
        self.assertEqual([str(finding) for finding in findings], [])


if __name__ == "__main__":
    unittest.main()
