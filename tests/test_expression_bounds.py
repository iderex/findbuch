"""The numbers the parser bounds an expression by, at their near-misses.

Two inputs have no clean refusal in the grammar. A deeply nested expression is
made of nodes the grammar admits, one per level, and an expression whose
expansion is enormous can be twenty characters long. Both are bounded instead,
by `MAXIMUM_DEPTH` and `MAXIMUM_TERMS` in findbuch.expression, and a bound is a
number somebody chose rather than a property of anything. `MAXIMUM_LENGTH` is
the third, and it is there because the depth cannot be measured until the
language's own parser has produced a tree, and that parser gives out first.

So each one is tested at its edge, with the admitted case beside the refused one.
A limit tested with an input a thousand times over it would pass with the limit
set anywhere, and would not notice the day somebody changes what is measured.

The corpus files that carry these refusals are in tests/test_refused_corpus.py.
What is here instead is the pair either side of each number, which is a fact
about the language rather than about a formula anybody transcribed.

WHAT THE LAST CLASS IS FOR. The numbers claim headroom over the rows this
project will hold, and headroom that nothing measures is headroom somebody
remembers. It measures every formula in every row in the tree against the two
limits an admitted formula can approach, so a row that starts to come near
either one reddens here rather than being refused on the day it is entered.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import tomllib
import unittest
from pathlib import Path

from findbuch.expression import (
    MAXIMUM_DEPTH,
    MAXIMUM_LENGTH,
    MAXIMUM_TERMS,
    SymbolTable,
    measure,
    parse,
    parse_all,
)
from findbuch.validation import EXPRESSION_FIELDS, StructureRegistry

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CATALOGUE = REPO_ROOT / "catalogue"
FIXTURE_ROWS = FIXTURES / "rows"

COORDINATES = ("M1", "M2", "M3", "g1", "g2", "g3")
PARAMETERS = ("A1", "A2", "A3")


def table() -> SymbolTable:
    return SymbolTable.of(COORDINATES, PARAMETERS)


def refusal_code(text: str) -> str:
    _, refused = parse_all([text], table())
    if not refused:
        raise AssertionError(
            f"{text[:40]!r} was admitted and this test is about refusal"
        )
    return refused[0].code


def nesting(count: int) -> str:
    """A string that nests `count` unary operators, and nothing else.

    Unary minus rather than parentheses. The language refuses a deep enough
    parenthesis nest itself, before this module measures anything, and a test
    built on that would pass with no limit here at all.
    """
    return "-" * count + "M1"


class TheDepthLimitRefusesAtItsEdge(unittest.TestCase):
    def setUp(self) -> None:
        # The shortest string this refuses, found rather than written down. The
        # syntax tree carries the operator as a child of the node it belongs to,
        # so the depth a string produces is a little more than the number of
        # characters that produced it, and hard-coding the difference would make
        # this test about that arithmetic instead of about the limit.
        self.edge = next(
            count
            for count in range(1, MAXIMUM_DEPTH * 2)
            if parse_all([nesting(count)], table())[1]
        )

    def test_the_edge_is_where_the_limit_is_and_not_somewhere_else(self) -> None:
        # Within two of the number, in either direction. The tree is a little
        # deeper than the string is long, because the node for an operator is a
        # child of the node it belongs to, and pinning the difference exactly
        # would make this a test about that arithmetic. What it has to rule out
        # is a refusal arriving from somewhere other than this limit, which
        # would sit nowhere near it.
        self.assertLessEqual(MAXIMUM_DEPTH - 2, self.edge)
        self.assertLessEqual(self.edge, MAXIMUM_DEPTH + 2)

    def test_one_level_past_the_limit_is_refused_as_too_deep(self) -> None:
        self.assertEqual(refusal_code(nesting(self.edge)), "expression.too-deep")

    def test_one_level_under_it_is_admitted(self) -> None:
        built = parse(nesting(self.edge - 1), table())
        self.assertEqual(built.free_symbols, set(parse("M1", table()).free_symbols))

    def test_a_string_far_past_the_limit_is_refused_and_not_walked(self) -> None:
        # The case the limit exists for: without it the recursive walk reaches
        # this before anything decides anything about it. Well inside the length
        # limit, so what refuses it is the depth and not the length.
        self.assertLess(len(nesting(400)), MAXIMUM_LENGTH)
        self.assertEqual(refusal_code(nesting(400)), "expression.too-deep")


class TheLengthLimitStandsInFrontOfTheParser(unittest.TestCase):
    """The third number, and the one that is about the input rather than the tree.

    The depth is measured on a tree, and the tree comes from the language's own
    parser, which has no limit of its own. So a string long enough to defeat that
    parser has to be refused before it reaches it.
    """

    def test_a_string_the_parser_cannot_survive_is_refused_rather_than_fatal(
        self,
    ) -> None:
        # Twenty thousand is measured rather than picked: `ast.parse` raises
        # MemoryError at that size on the pinned interpreter, and RecursionError
        # at four thousand on the floor one. Neither is a refusal, both are the
        # boundary falling over, and what stands in front of them is the length.
        self.assertEqual(refusal_code(nesting(20000)), "expression.too-long")

    def test_a_string_at_the_limit_is_parsed_and_not_survived(self) -> None:
        # THE CASE THE NUMBER IS CHOSEN FOR, and the reason it is a test rather
        # than a sentence: it decides whether the limit sits under the parser's
        # capacity, and that capacity differs between interpreters. This runs on
        # the floor as well as on the pin, so the floor is where it is settled.
        # A refusal here means the string reached this project's depth limit,
        # which means the language's parser built the tree first.
        at_the_limit = "-" * (MAXIMUM_LENGTH - 2) + "M1"
        self.assertEqual(len(at_the_limit), MAXIMUM_LENGTH)
        self.assertEqual(refusal_code(at_the_limit), "expression.too-deep")

    def test_the_length_limit_bites_before_the_depth_limit(self) -> None:
        # The near-miss, and it is a change of identifier rather than a change
        # from refused to admitted: both of these are refused, and which limit
        # does it moves at the edge.
        just_over = "-" * (MAXIMUM_LENGTH - 1) + "M1"
        just_under = "-" * (MAXIMUM_LENGTH - 2) + "M1"
        self.assertEqual(len(just_over), MAXIMUM_LENGTH + 1)
        self.assertEqual(refusal_code(just_over), "expression.too-long")
        self.assertEqual(refusal_code(just_under), "expression.too-deep")


class TheSizeLimitRefusesAtItsEdge(unittest.TestCase):
    """Two sites, because one number is applied in two places.

    An integer exponent before the power is taken, and the whole expression once
    it is built. The second is what catches everything that is large without
    being a power: a product of thirteen sums nests thirteen deep and expands to
    eight thousand terms.
    """

    def test_a_power_of_a_sum_at_the_limit_is_admitted(self) -> None:
        # Two terms to the twelfth is 4096 exactly, which is the limit.
        built = parse("(M1 + M2)**12", table())
        self.assertEqual(measure("(M1 + M2)**12", table()).terms, MAXIMUM_TERMS)
        self.assertEqual(built.args[1], 12)

    def test_a_power_of_a_sum_one_step_over_it_is_refused(self) -> None:
        self.assertEqual(refusal_code("(M1 + M2)**13"), "expression.too-large")

    def test_an_exponent_at_the_limit_is_admitted(self) -> None:
        # The base is one term, so nothing expands; what is bounded here is the
        # exponent itself, and the pair either side of it is the proof that the
        # magnitude is what did the refusing.
        self.assertEqual(measure(f"M1**{MAXIMUM_TERMS}", table()).terms, 1)

    def test_an_exponent_one_step_over_it_is_refused(self) -> None:
        self.assertEqual(
            refusal_code(f"M1**{MAXIMUM_TERMS + 1}"), "expression.too-large"
        )

    def test_a_power_tower_is_refused_before_the_power_is_taken(self) -> None:
        # `2**10**9` is legal arithmetic over one term, and evaluating it is the
        # thing that does not return. This is the case where computing the value
        # and then comparing it would be the wrong order.
        self.assertEqual(refusal_code("2**10**9"), "expression.too-large")

    def test_a_product_of_sums_at_the_limit_is_admitted(self) -> None:
        text = "*".join(["(M1 + M2)"] * 12)
        measured = measure(text, table())
        self.assertEqual(measured.terms, MAXIMUM_TERMS)
        self.assertLess(measured.depth, MAXIMUM_DEPTH)

    def test_a_product_of_sums_one_factor_over_it_is_refused(self) -> None:
        text = "*".join(["(M1 + M2)"] * 13)
        self.assertEqual(refusal_code(text), "expression.too-large")

    def test_a_sum_of_two_admitted_powers_is_refused_for_the_total(self) -> None:
        # Each half is exactly at the limit and passes on its own, and the sum
        # of them is not. This is the site that counts a sum, and it is reached
        # only by an expression whose parts were each admitted.
        self.assertEqual(
            refusal_code("(M1 + M2)**12 + (M3 + g1)**12"), "expression.too-large"
        )

    def test_a_product_of_two_admitted_powers_is_refused_for_the_total(self) -> None:
        self.assertEqual(
            refusal_code("(M1 + M2)**12 * (M3 + g1)**12"), "expression.too-large"
        )

    def test_the_same_product_of_single_symbols_is_admitted(self) -> None:
        # The one-change neighbour for the case above, and the one that says the
        # depth limit is not what refused it: same number of factors, same
        # nesting, one term instead of two in each.
        text = "*".join(["(M1)"] * 13)
        measured = measure(text, table())
        self.assertEqual(measured.terms, 1)
        self.assertLess(measured.depth, MAXIMUM_DEPTH)


class TheHeadroomOverThisTreeIsMeasured(unittest.TestCase):
    """Every formula in every row, against both numbers.

    The corpus under tests/fixtures/refused/ is deliberately outside this: it
    holds the files that exist to be past the limits.
    """

    def rows(self) -> list[Path]:
        return sorted(CATALOGUE.glob("*.toml")) + sorted(FIXTURE_ROWS.glob("*.toml"))

    def test_no_row_in_this_tree_comes_near_either_limit(self) -> None:
        registry = StructureRegistry.from_directory(FIXTURES / "structures")
        deepest = 0
        largest = 0
        for path in self.rows():
            with path.open("rb") as handle:
                document = tomllib.load(handle)
            named = document.get("structure")
            if not isinstance(named, str) or not registry.coordinates_known(named):
                continue
            symbols = SymbolTable.of(
                registry.coordinates(named),
                [
                    str(parameter.get("symbol", ""))
                    for parameter in document.get("parameters", [])
                ],
            )
            for field in EXPRESSION_FIELDS:
                value = document.get(field)
                texts = [value] if isinstance(value, str) else (value or [])
                for text in texts:
                    with self.subTest(row=path.name, field=field):
                        measured = measure(text, symbols)
                        deepest = max(deepest, measured.depth)
                        largest = max(largest, measured.terms)
        self.assertLess(
            deepest,
            MAXIMUM_DEPTH,
            f"the deepest formula in this tree measures {deepest} against a "
            f"limit of {MAXIMUM_DEPTH}",
        )
        self.assertLess(
            largest,
            MAXIMUM_TERMS,
            f"the largest expansion in this tree measures {largest} against a "
            f"limit of {MAXIMUM_TERMS}",
        )

    def test_the_measurement_ran_over_at_least_one_row(self) -> None:
        # A scan over no rows passes the case above and measures nothing.
        self.assertNotEqual(self.rows(), [])


if __name__ == "__main__":
    unittest.main()
