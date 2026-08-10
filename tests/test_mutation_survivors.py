"""The cases that exist because a mutant of the verdict path survived.

Every case below was written after `python tools/mutation_sample.py` changed one
token of a gated module and the whole suite stayed green. Each one names the
mutant it kills, so that a reader can put the mutant back and watch this file go
red rather than take the sentence on trust:

    python tools/mutation_sample.py --list

They are collected here rather than filed beside the limits they pin, because
what they have in common is not a subject but a provenance: nobody thought of
them, and a run that changes the checker found them. A case that came from a
mutant reads differently from one that came from a requirement, and the
difference is worth keeping where somebody deciding whether to delete it will
see it.

WHAT EACH KIND OF SURVIVOR SAID.

The depth limit was tested at an edge the test discovered for itself, so
loosening the comparison moved the edge and the assertions moved with it. A
bound tested relative to where it currently bites cannot notice the bound
moving; it has to be pinned against the number somebody chose.

The position in a refusal was never asserted at all. #21 asks that a refusal
name the offending token and its position, because a contributor debugging a
formula against a nineteenth century paper has enough to do, and three separate
mutants could make every refusal point at line 1 column 1 or at column minus one
with nothing noticing.

The verdict objects are frozen and nothing said so. Thirteen mutants on this
surface turn `frozen=True` into `frozen=False`, which hands a caller a verdict it
can rewrite after it was reached and takes the class out of every set and
dictionary it could be put in. One property kills all thirteen.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import dataclasses
import importlib
import sys
import unittest
from pathlib import Path
from types import ModuleType

from findbuch.expression import (
    MAXIMUM_DEPTH,
    ExpressionRefused,
    SymbolTable,
    measure,
    parse,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO_ROOT / "tools"))

import coverage_bar  # noqa: E402

COORDINATES = ("M1", "M2", "M3", "g1", "g2", "g3")
PARAMETERS = ("A1", "A2", "A3")


def table() -> SymbolTable:
    return SymbolTable.of(COORDINATES, PARAMETERS)


def nesting(count: int) -> str:
    """A string that nests `count` unary operators, and nothing else.

    The same shape tests/test_expression_bounds.py builds, and deliberately its
    own copy: this file has to be able to fail on its own when a mutant is put
    back, without a helper somewhere else deciding what it measures.
    """
    return "-" * count + "M1"


def admitted(text: str) -> bool:
    try:
        parse(text, table())
    except ExpressionRefused:
        return False
    return True


def refusal(text: str) -> ExpressionRefused:
    try:
        parse(text, table())
    except ExpressionRefused as refused:
        return refused
    raise AssertionError(f"{text[:40]!r} was admitted and this case is about refusal")


class TheDepthLimitIsPinnedToItsNumberRatherThanToWhereItBites(unittest.TestCase):
    """Kills `src/findbuch/expression.py` `'>' -> '>='` in the depth guard.

        if _depth(tree.body) > MAXIMUM_DEPTH:

    Under that mutant a tree exactly at the limit is refused. The edge moves one
    level down, and a case that looks for the edge before asserting anything
    about it moves with it, which is why this one measures instead.
    """

    def setUp(self) -> None:
        self.deepest = max(
            count for count in range(1, MAXIMUM_DEPTH * 2) if admitted(nesting(count))
        )

    def test_the_deepest_admitted_string_nests_exactly_to_the_limit(self) -> None:
        # The whole case, in one number. A tree of MAXIMUM_DEPTH is inside the
        # limit and a checker that refuses it is refusing what it says it
        # admits.
        self.assertEqual(measure(nesting(self.deepest), table()).depth, MAXIMUM_DEPTH)

    def test_one_level_further_is_refused_for_being_too_deep(self) -> None:
        # The other side, so that the case above cannot be satisfied by a guard
        # that admits everything.
        self.assertEqual(refusal(nesting(self.deepest + 1)).code, "expression.too-deep")


class ARefusalNamesWhereItHappenedAndNotAlwaysTheFirstCharacter(unittest.TestCase):
    """Kills three mutants in `src/findbuch/expression.py`.

        position = f"line {broken.lineno or 1}, column {broken.offset or 1}"
        position = f"line {tree.body.lineno}, column {tree.body.col_offset + 1}"

    `or` swapped for `and` in either of the first line's two fallbacks makes
    every unparseable string report line 1 or column 1 whatever the parser said,
    and `+` swapped for `-` in the second makes every bounded string report
    column minus one. All three survived the suite as it stood, because the
    refusal identifier was asserted everywhere and the position nowhere.
    """

    def test_the_reported_line_is_the_line_the_parser_named(self) -> None:
        # Two lines, with the error on the second. A single-line formula cannot
        # tell `lineno or 1` from `lineno and 1`, since both are 1.
        self.assertEqual(refusal("M1 +\nM2 )").where, "line 2, column 4")

    def test_the_reported_column_is_the_column_the_parser_named(self) -> None:
        self.assertEqual(refusal("M1 ) ").where, "line 1, column 4")

    def test_a_bounded_string_reports_the_column_counted_from_one(self) -> None:
        # The syntax tree counts columns from zero and a person counts from one,
        # so this is the one place the offset is adjusted. Minus one instead of
        # plus one is a position that cannot exist.
        self.assertEqual(refusal(nesting(400)).where, "line 1, column 1")

    def test_the_three_cases_above_are_about_three_different_positions(
        self,
    ) -> None:
        # A guard on the guard. If the parser's own positions ever collapse to
        # one value, the cases above would pass while asserting nothing, and
        # this is what says so.
        reported = {
            refusal("M1 +\nM2 )").where,
            refusal("M1 ) ").where,
            refusal(nesting(400)).where,
        }
        self.assertEqual(len(reported), 3, reported)


def surface_modules() -> list[ModuleType]:
    """Every gated module, imported, with the list read from the bar."""
    imported = []
    for path in sorted(coverage_bar.VERDICT_SURFACE):
        name = Path(path).with_suffix("").as_posix().removeprefix("src/")
        imported.append(importlib.import_module(name.replace("/", ".")))
    return imported


class EveryVerdictObjectOnTheSurfaceIsFrozen(unittest.TestCase):
    """Kills thirteen `frozen=True -> frozen=False` mutants on the surface.

    A record of what a checker decided, handed to a caller who can then write to
    it, is a verdict that changes after it was reached and nothing downstream
    can tell. The same switch also removes the class's hash, which takes it out
    of every set and dictionary it could be put in, and that is the half a
    reader can observe without arguing about intent.
    """

    def declared_dataclasses(self) -> list[type]:
        found = []
        for module in surface_modules():
            for value in vars(module).values():
                if (
                    isinstance(value, type)
                    and dataclasses.is_dataclass(value)
                    and value.__module__ == module.__name__
                ):
                    found.append(value)
        return found

    def test_the_surface_declares_dataclasses_to_look_at(self) -> None:
        # An enumeration that reached nothing would make the case below pass
        # over an empty list, which is the way this stops checking.
        self.assertNotEqual(self.declared_dataclasses(), [])

    def test_every_gated_module_declares_at_least_one(self) -> None:
        for module in surface_modules():
            with self.subTest(module=module.__name__):
                declared = [
                    value
                    for value in vars(module).values()
                    if isinstance(value, type)
                    and dataclasses.is_dataclass(value)
                    and value.__module__ == module.__name__
                ]
                self.assertNotEqual(declared, [])

    def test_none_of_them_can_be_written_to_after_it_is_built(self) -> None:
        for declared in self.declared_dataclasses():
            with self.subTest(declared=f"{declared.__module__}.{declared.__name__}"):
                # A frozen dataclass is given a `__setattr__` of its own, and
                # that method is what refuses the write. A mutable one is given
                # none and inherits the one that accepts it.
                self.assertIn("__setattr__", vars(declared))

    def test_none_of_them_lost_its_hash(self) -> None:
        for declared in self.declared_dataclasses():
            with self.subTest(declared=f"{declared.__module__}.{declared.__name__}"):
                self.assertIsNotNone(declared.__hash__)


if __name__ == "__main__":
    unittest.main()
