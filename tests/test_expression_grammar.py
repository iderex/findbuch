"""The grammar admits what 0004 admits, refuses the rest, and by identity.

`docs/decisions/0004-expression-grammar.md` decided this and #21 implements it.
The two properties worth testing are not the same one.

The first is that the string never reaches the computer algebra library's own
parser. That one is proved the way the record asks for it to be proved: the
library's convenience entry points are patched to raise and the full loader is
run over rows that exist, so a reintroduction of the convenience call reddens the
suite instead of passing quietly. It is at the bottom of this file and it is the
one that matters most.

The second is that an identifier nobody declared is an error rather than a new
free variable. That is the quieter half of 0004 and the half that costs more when
it is missing, so it has its own pair here: the mistyped parameter and the
one-change neighbour that spells it right.

WHAT THIS FILE IS NOT. It is not the negative corpus. That is #22: files under
`tests/fixtures/`, one per plausible mistake or plausible attack, each asserted
against its expected refusal identifier. The strings below are in the source
because they are about the grammar rather than about a formula, and nothing here
is offered as the corpus or reduces what #22 has to cover. What this file does
establish is the identifier per refusal that the corpus will assert against.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import unittest
from pathlib import Path
from unittest import mock

import sympy

from findbuch.expression import (
    ADMITTED_FUNCTIONS,
    ExpressionRefused,
    SymbolTable,
    parse,
    parse_all,
)
from findbuch.validation import StructureRegistry, validate_catalogue, validate_file

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CATALOGUE = REPO_ROOT / "catalogue"
FIXTURE_ROWS = FIXTURES / "rows"

# The table the Euler fixture row resolves against: the coordinates of e3 and
# the three parameters that row declares.
COORDINATES = ("M1", "M2", "M3", "g1", "g2", "g3")
PARAMETERS = ("A1", "A2", "A3")

# The convenience entry points 0004 forbids, in the spellings a careless
# implementation actually uses. Patching the top-level attributes reaches
# exactly those calls: a module inside the library that bound the function at
# import time is unaffected, which is why the library keeps working underneath
# while every `sympy.<name>(...)` call from this project's own source raises.
CONVENIENCE_PARSERS = (
    "sympy.sympify",
    "sympy.S",
    "sympy.parse_expr",
    "sympy.parsing.parse_expr",
    "sympy.parsing.sympy_parser.parse_expr",
)


def table() -> SymbolTable:
    return SymbolTable.of(COORDINATES, PARAMETERS)


def registry() -> StructureRegistry:
    return StructureRegistry.from_directory(FIXTURES / "structures")


def refusal_code(text: str) -> str:
    _, refused = parse_all([text], table())
    if not refused:
        raise AssertionError(f"{text!r} was admitted and this test is about refusal")
    return refused[0].code


class WhatTheGrammarAdmits(unittest.TestCase):
    def test_the_four_operations_and_an_integer_power(self) -> None:
        M1, M2, A1 = sympy.symbols("M1 M2 A1")  # noqa: N806
        self.assertEqual(parse("M1 + M2", table()), M1 + M2)
        self.assertEqual(parse("M1 - M2", table()), M1 - M2)
        self.assertEqual(parse("M1*M2", table()), M1 * M2)
        self.assertEqual(parse("M1/A1", table()), M1 / A1)
        self.assertEqual(parse("M1**2", table()), M1**2)
        self.assertEqual(parse("-M1", table()), -M1)

    def test_the_euler_hamiltonian_as_it_is_written_in_the_fixture_row(self) -> None:
        M1, M2, M3 = sympy.symbols("M1 M2 M3")  # noqa: N806
        A1, A2, A3 = sympy.symbols("A1 A2 A3")  # noqa: N806
        built = parse(
            "(M1*M1)/(2*A1) + (M2*M2)/(2*A2) + (M3*M3)/(2*A3)",
            table(),
        )
        expected = M1**2 / (2 * A1) + M2**2 / (2 * A2) + M3**2 / (2 * A3)
        self.assertEqual(sympy.expand(built - expected), 0)

    def test_a_rational_is_written_as_one_integer_over_another_and_stays_exact(
        self,
    ) -> None:
        built = parse("M1/3", table())
        self.assertEqual(built, sympy.Rational(1, 3) * sympy.Symbol("M1"))
        coefficient = built.as_coefficients_dict()[sympy.Symbol("M1")]
        self.assertIsInstance(coefficient, sympy.Rational)

    def test_every_function_on_the_allowlist_is_callable(self) -> None:
        for name in sorted(ADMITTED_FUNCTIONS):
            with self.subTest(function=name):
                built = parse(f"{name}(M1)", table())
                self.assertIn("M1", str(built))


class AnIdentifierNobodyDeclaredIsAnErrorAndNotAFreeVariable(unittest.TestCase):
    """The quieter half of 0004, with the pair the record's argument turns on."""

    def test_a_mistyped_parameter_is_refused_and_named(self) -> None:
        with self.assertRaises(ExpressionRefused) as refused:
            parse("M1/(2*A4)", table())
        self.assertEqual(refused.exception.code, "expression.unknown-symbol")
        self.assertIn("A4", str(refused.exception))
        # The refusal has to say where to look, so the message carries the table
        # rather than only the fact that the name is unknown.
        self.assertIn("A1", refused.exception.message)

    def test_the_one_change_neighbour_that_spells_it_right_is_admitted(self) -> None:
        built = parse("M1/(2*A3)", table())
        self.assertEqual(built.free_symbols, {sympy.Symbol("M1"), sympy.Symbol("A3")})

    def test_the_table_is_built_from_two_sources_and_no_others(self) -> None:
        # `pi` is the case somebody will hit first. It is not a coordinate and
        # not a declared parameter, so it is refused like any other undeclared
        # name; 0004 says the table has two sources and this is what that costs.
        self.assertEqual(refusal_code("M1 + pi"), "expression.unknown-symbol")


class WhatTheGrammarRefuses(unittest.TestCase):
    """One case per refusal identifier, each a plausible mistake or attack.

    Asserted by identifier and never by the fact that something was raised: a
    typo in the case below would raise too, and it would raise for a reason the
    test was not written about.
    """

    def test_each_case_is_refused_by_its_own_identifier(self) -> None:
        # A list of pairs rather than a mapping, because two refusal sites share
        # one identifier and a mapping would silently keep only the second.
        cases = (
            ("expression.unknown-symbol", "M1 + qq"),
            ("expression.unknown-function", "gamma(M1)"),
            ("expression.attribute-access", "M1.__class__"),
            ("expression.subscript", "M1[0]"),
            ("expression.node-refused", "M1 if M2 else M3"),
            ("expression.operator-refused", "M1 % M2"),
            ("expression.operator-refused", "~M1"),
            ("expression.non-integer-exponent", "M1**A1"),
            ("expression.decimal-literal", "0.5*M1"),
            ("expression.literal-refused", "M1 + 'two'"),
            ("expression.arity", "sqrt(M1, M2)"),
            ("expression.keyword-argument", "sqrt(M1, evaluate=False)"),
            ("expression.starred-argument", "sqrt(*M1)"),
            ("expression.call-not-a-name", "sqrt(M1)(M2)"),
            ("expression.function-not-called", "M1*sqrt"),
            ("expression.unparseable", "M1 +"),
            ("expression.empty", "   "),
        )
        for expected, text in cases:
            with self.subTest(refusal=expected, text=text):
                self.assertEqual(refusal_code(text), expected)

    def test_the_refusal_names_the_offending_token_and_its_position(self) -> None:
        _, refused = parse_all(["M1 + M2 + zz"], table())
        self.assertEqual(len(refused), 1)
        self.assertIn("zz", refused[0].where)
        self.assertIn("column 11", refused[0].where)

    def test_a_dunder_reach_is_refused_before_anything_is_looked_up(self) -> None:
        # The attack shape rather than the mistake shape. It is refused as
        # attribute access, at the attribute, and nothing resolves `M1` first.
        self.assertEqual(
            refusal_code("M1.__class__.__mro__"), "expression.attribute-access"
        )

    def test_a_power_tower_with_a_symbolic_exponent_is_refused(self) -> None:
        # The near-miss for the integer-exponent rule: an exponent that is a
        # declared symbol, which is one character away from a legal row.
        self.assertEqual(refusal_code("M1**A1"), "expression.non-integer-exponent")

    def test_an_exponent_that_reduces_to_an_integer_is_admitted(self) -> None:
        # The other side of the same rule, so it refuses non-integer exponents
        # rather than refusing arithmetic in the exponent.
        self.assertEqual(parse("M1**(4/2)", table()), sympy.Symbol("M1") ** 2)


class TheParserIsWhatTheLoaderUses(unittest.TestCase):
    def test_a_row_whose_hamiltonian_leaves_the_grammar_is_refused_by_the_loader(
        self,
    ) -> None:
        import copy
        import tomllib

        from findbuch.validation import validate_row

        with (FIXTURE_ROWS / "euler.toml").open("rb") as handle:
            document = copy.deepcopy(tomllib.load(handle))
        document["hamiltonian"] = "M1.__class__"
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertIn(
            "expression.attribute-access", {refusal.code for refusal in refusals}
        )

    def test_the_field_and_the_position_are_both_in_the_refusal(self) -> None:
        import copy
        import tomllib

        from findbuch.validation import validate_row

        with (FIXTURE_ROWS / "euler.toml").open("rb") as handle:
            document = copy.deepcopy(tomllib.load(handle))
        document["integrals"] = ["M1*M1 + zz"]
        refusals = validate_row(document, file_stem="euler", registry=registry())
        located = [r for r in refusals if r.code == "expression.unknown-symbol"]
        self.assertEqual(len(located), 1)
        self.assertIn("integrals[0]", located[0].where)

    def test_the_rule_says_when_it_did_not_run(self) -> None:
        # A structure with no coordinates leaves no table to parse against, and
        # a rule that could not run has to report that rather than pass.
        empty = StructureRegistry([])
        result = validate_file(FIXTURE_ROWS / "euler.toml", empty)
        self.assertFalse(result.expressions_rule_evaluated)

    def test_the_rule_did_run_on_the_fixture_row(self) -> None:
        # Otherwise every case above would be passing by not running.
        result = validate_file(FIXTURE_ROWS / "euler.toml", registry())
        self.assertTrue(result.expressions_rule_evaluated)
        self.assertEqual([str(refusal) for refusal in result.refusals], [])


class TheLibraryParserIsNotReachableFromTheLoadingPath(unittest.TestCase):
    """The proof 0004 asks for, and the one this issue turns on.

    Every convenience entry point is patched to raise, and the full loader runs.
    A load that succeeds under that patch is a load that called none of them. A
    load that fails names the call in its traceback.
    """

    def test_the_fixture_directory_holds_a_row_so_the_proof_is_not_vacuous(
        self,
    ) -> None:
        # A loader run over an empty directory calls no parser at all and would
        # pass the case below while proving nothing. This is what stops that.
        self.assertNotEqual(sorted(FIXTURE_ROWS.glob("*.toml")), [])

    def test_the_full_loader_runs_with_every_convenience_parser_patched_to_raise(
        self,
    ) -> None:
        def refuse_to_be_called(*_arguments: object, **_keywords: object) -> object:
            raise AssertionError(
                "the library's convenience parser was called from the loading "
                "path, which 0004 forbids; parsing is a walk of a syntax tree "
                "against the admitted grammar"
            )

        patches = [
            mock.patch(target, side_effect=refuse_to_be_called)
            for target in CONVENIENCE_PARSERS
        ]
        with self.subTest(patched=CONVENIENCE_PARSERS):
            for patched in patches:
                patched.start()
            try:
                results = validate_catalogue(FIXTURE_ROWS, registry())
                catalogue = validate_catalogue(CATALOGUE, registry())
            finally:
                for patched in patches:
                    patched.stop()

        self.assertNotEqual(results, [])
        for result in results:
            with self.subTest(row=result.path.name):
                self.assertEqual([str(r) for r in result.refusals], [])
        for result in catalogue:
            with self.subTest(row=result.path.name):
                self.assertEqual([str(r) for r in result.refusals], [])

    def test_the_patch_would_have_bitten_if_a_convenience_parser_were_called(
        self,
    ) -> None:
        # The patch itself is the instrument, so it is checked before the result
        # above is read as evidence. Without this, a patch that silently failed
        # to apply would leave the case above green and meaningless.
        with (
            mock.patch("sympy.sympify", side_effect=AssertionError("called")),
            self.assertRaises(AssertionError),
        ):
            sympy.sympify("1")


if __name__ == "__main__":
    unittest.main()
