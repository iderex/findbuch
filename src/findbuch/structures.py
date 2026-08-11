"""Read a Poisson structure from data, and give back a bracket that can be evaluated.

`docs/decisions/0002-poisson-structures.md` decided that the structure is data
rather than code, and the reason is not tidiness. A checker with one bracket
written into it silently verifies the wrong statement about half the catalogue:
the heavy body lives on e(3), several of the Kirchhoff cases are stated on so(4)
or so(3,1), and a row transcribed from a Kirchhoff paper and checked against e(3)
either fails or passes for the wrong reason. Neither outcome tells a reader
anything.

So the bracket table lives in `src/findbuch/data/structures/`, this module reads
it, and adding a structure is adding a file. Nothing here knows what e(3) is.

WHAT IS DECLARED AND WHAT IS DERIVED. The table between generators is declared,
every ordered pair of it, and a missing pair is refused rather than defaulting to
zero: an undeclared pair is a bracket entry nobody wrote and nobody can find, and
zero is a legal value that the identity tests below pass over happily. The
bracket of two arbitrary functions IS derived, from the table by the Leibniz
rule, because that is one formula rather than a second thing to keep in step.

THE CASIMIRS ARE DECLARED AND CHECKED. 0002 argues both halves: deriving them is
a second piece of mathematics to get right, and they are load-bearing, because
the numeric leg measures drift against them. A declaration standing on its own
would be dangerous, so `casimir_failures` brackets each one with every generator
and requires identically zero. A structure whose Casimir is wrong is refused at
test time rather than producing a noise floor that quietly means nothing.

WHAT THIS IS NOT. It is not the symbolic checker. It computes brackets and it
reaches no verdict about a row; deciding the general case by exact polynomial
identity is #26 and the conditional cases are #27, both on top of this. The
exactness that makes those verdicts possible starts here: every value is built by
`findbuch.expression` out of integers and declared symbols, so nothing in a
bracket is a floating point number and no comparison in this module is anything
but a polynomial being identically zero.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import sympy

from findbuch.expression import SymbolTable, parse

PACKAGE_ROOT = Path(__file__).resolve().parent

# Under the package, for the reason given at the same constant in
# findbuch.validation. The directory is `data/structures` rather than
# `structures` beside this module, because a directory named after a module that
# sits next to it is resolved by the import system in an order nobody should
# have to know.
DATA_ROOT = PACKAGE_ROOT / "data"
STRUCTURES = DATA_ROOT / "structures"
FAMILIES = "family"


class StructureRefused(Exception):  # noqa: N818
    """One reason a structure or a family file was refused.

    No `Error` suffix, for the reason given at `ExpressionRefused` in
    findbuch.expression: a refusal is a verdict this project reached about a
    file, and it is one concept rather than two.
    """

    def __init__(self, code: str, message: str, where: str = "") -> None:
        stated = f"{code} at {where}: {message}" if where else f"{code}: {message}"
        super().__init__(stated)
        self.code = code
        self.message = message
        self.where = where


@dataclass(frozen=True)
class Casimir:
    """A declared Casimir, with the expression it was declared as."""

    name: str
    expression: str
    built: sympy.Expr


@dataclass(frozen=True)
class PoissonStructure:
    """One structure: the coordinates, the table between them, and the Casimirs.

    `table` is keyed by ORDERED pairs. Both directions are read from the file
    rather than one being derived from the other, which is what leaves
    `antisymmetry_failures` something to decide. A table built by negating one
    half would satisfy antisymmetry by construction and the test over it would
    be decoration.
    """

    identifier: str
    name: str
    coordinates: tuple[str, ...]
    parameter: str
    parameter_value: int
    table: Mapping[tuple[str, str], sympy.Expr]
    casimirs: tuple[Casimir, ...]

    def generator(self, name: str) -> sympy.Symbol:
        return sympy.Symbol(name)

    def entry(self, left: str, right: str) -> sympy.Expr:
        return self.table[(left, right)]

    def bracket(self, first: sympy.Expr, second: sympy.Expr) -> sympy.Expr:
        """The Poisson bracket of two functions, by the Leibniz rule.

        Expanded rather than simplified. 0006 keeps the library's general
        simplification routine out of anything that decides, and expansion of a
        polynomial is exact and terminates, which is the whole reason a verdict
        can rest on it.
        """
        total: sympy.Expr = sympy.Integer(0)
        for left in self.coordinates:
            first_derivative = sympy.diff(first, self.generator(left))
            if first_derivative == 0:
                continue
            for right in self.coordinates:
                value = self.entry(left, right)
                if value == 0:
                    continue
                second_derivative = sympy.diff(second, self.generator(right))
                if second_derivative == 0:
                    continue
                total = total + first_derivative * value * second_derivative
        return sympy.expand(total)


def _document(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise StructureRefused(
            "structure.file-missing",
            f"no file at '{path}'",
            path.name,
        )
    with path.open("rb") as handle:
        loaded: dict[str, Any] = tomllib.load(handle)
    return loaded


def _required(document: Mapping[str, Any], field: str, where: str) -> Any:
    if field not in document:
        raise StructureRefused(
            "structure.missing-field",
            f"the required field '{field}' is missing",
            where,
        )
    return document[field]


def _table_from(
    entries: Sequence[Mapping[str, Any]],
    coordinates: Sequence[str],
    symbols: SymbolTable,
    where: str,
) -> dict[tuple[str, str], sympy.Expr]:
    """Every ordered pair, declared. A pair left out is refused, not defaulted."""
    built: dict[tuple[str, str], sympy.Expr] = {}
    for entry in entries:
        left = str(entry.get("left", ""))
        right = str(entry.get("right", ""))
        if left not in coordinates or right not in coordinates:
            raise StructureRefused(
                "structure.bracket-names-a-stranger",
                f"the entry ({left}, {right}) names something that is not a "
                f"coordinate of this family, which are {', '.join(coordinates)}",
                where,
            )
        if (left, right) in built:
            raise StructureRefused(
                "structure.bracket-declared-twice",
                f"the pair ({left}, {right}) is declared more than once, so which "
                f"of the two values the bracket has depends on file order",
                where,
            )
        built[(left, right)] = parse(str(entry.get("value", "")), symbols)

    missing = [
        (left, right)
        for left in coordinates
        for right in coordinates
        if (left, right) not in built
    ]
    if missing:
        listed = ", ".join(f"({left}, {right})" for left, right in missing)
        raise StructureRefused(
            "structure.bracket-incomplete",
            f"these ordered pairs are not declared: {listed}. A pair left out "
            f"would default to zero, which is a legal value and an entry nobody "
            f"wrote",
            where,
        )
    return built


@dataclass(frozen=True)
class Family:
    """The parametrised table three structures share, before the parameter is fixed."""

    identifier: str
    name: str
    parameter: str
    coordinates: tuple[str, ...]
    table: Mapping[tuple[str, str], sympy.Expr]
    casimirs: tuple[Casimir, ...]


def load_family(path: Path) -> Family:
    document = _document(path)
    where = path.name
    identifier = str(_required(document, "id", where))
    parameter = str(_required(document, "parameter", where))
    coordinates = tuple(str(name) for name in _required(document, "coordinates", where))
    # The symbol table is the coordinates and the parameter, and nothing else, so
    # a mistyped coordinate in the table below is refused by name rather than
    # becoming a free variable that makes a bracket entry look harmless.
    symbols = SymbolTable.of(coordinates, (parameter,))
    table = _table_from(
        _required(document, "bracket", where), coordinates, symbols, where
    )
    casimirs = tuple(
        Casimir(
            name=str(declared.get("name", "")),
            expression=str(declared.get("expression", "")),
            built=parse(str(declared.get("expression", "")), symbols),
        )
        for declared in _required(document, "casimirs", where)
    )
    if not casimirs:
        raise StructureRefused(
            "structure.no-casimir",
            "the family declares no Casimir, and the numeric leg measures drift "
            "against them",
            where,
        )
    return Family(
        identifier=identifier,
        name=str(document.get("name", identifier)),
        parameter=parameter,
        coordinates=coordinates,
        table=table,
        casimirs=casimirs,
    )


def load_structure(path: Path, families: Path) -> PoissonStructure:
    document = _document(path)
    where = path.name
    identifier = str(_required(document, "id", where))
    family_name = str(_required(document, "family", where))
    family_path = families / f"{family_name}.toml"
    if not family_path.is_file():
        raise StructureRefused(
            "structure.family-unknown",
            f"this structure names the family '{family_name}' and there is no "
            f"file at '{family_path}'",
            where,
        )
    family = load_family(family_path)
    value = _required(document, family.parameter, where)
    if not isinstance(value, int) or isinstance(value, bool):
        raise StructureRefused(
            "structure.parameter-not-an-integer",
            f"'{family.parameter}' is declared as {value!r}; the three members of "
            f"this family are one integer apart and a fixed parameter that is not "
            f"an integer would make every bracket entry inexact",
            where,
        )
    declared = tuple(str(name) for name in _required(document, "coordinates", where))
    if declared != family.coordinates:
        raise StructureRefused(
            "structure.coordinates-disagree-with-the-family",
            f"this structure declares {declared} and the family declares "
            f"{family.coordinates}; a row resolved against one and bracketed "
            f"against the other is checked against neither",
            where,
        )
    fixed = {family.parameter: sympy.Integer(value)}
    table = {
        pair: sympy.expand(entry.subs(fixed)) for pair, entry in family.table.items()
    }
    casimirs = tuple(
        Casimir(
            name=casimir.name,
            expression=casimir.expression,
            built=sympy.expand(casimir.built.subs(fixed)),
        )
        for casimir in family.casimirs
    )
    return PoissonStructure(
        identifier=identifier,
        name=str(document.get("name", identifier)),
        coordinates=family.coordinates,
        parameter=family.parameter,
        parameter_value=value,
        table=table,
        casimirs=casimirs,
    )


def load_all(directory: Path = STRUCTURES) -> dict[str, PoissonStructure]:
    """Every structure in the directory, keyed by identifier.

    The families live in a subdirectory rather than beside the structures, so a
    family file is not itself loadable as a structure. A family with its
    parameter still free has no bracket a checker can evaluate.
    """
    if not directory.is_dir():
        return {}
    families = directory / FAMILIES
    loaded = {}
    for path in sorted(directory.glob("*.toml")):
        structure = load_structure(path, families)
        if structure.identifier in loaded:
            raise StructureRefused(
                "structure.identifier-declared-twice",
                f"'{structure.identifier}' is declared by two files, so a row "
                f"naming it is resolved against whichever was read last",
                path.name,
            )
        loaded[structure.identifier] = structure
    return loaded


def antisymmetry_failures(structure: PoissonStructure) -> list[str]:
    """Every ordered pair, including a coordinate against itself."""
    failures = []
    for left in structure.coordinates:
        for right in structure.coordinates:
            total = sympy.expand(
                structure.entry(left, right) + structure.entry(right, left)
            )
            if total != 0:
                failures.append(
                    f"{{{left}, {right}}} + {{{right}, {left}}} = {total}, and "
                    f"antisymmetry requires it to be zero"
                )
    return failures


def jacobi_failures(structure: PoissonStructure) -> list[str]:
    """The identity on every triple of distinct generators.

    Distinct is enough and it is worth saying why rather than leaving it to be
    trusted. The cyclic sum is totally antisymmetric in its three arguments, so a
    triple with two coordinates the same reduces to a difference of two equal
    terms plus a bracket of a coordinate with itself, and both vanish given the
    antisymmetry checked above. Running the repeats as well would cost ten times
    the triples to re-derive a consequence of a property the suite already
    decides on its own.
    """
    failures = []
    for first, second, third in combinations(structure.coordinates, 3):
        cyclic = (
            structure.bracket(
                structure.generator(first), structure.entry(second, third)
            )
            + structure.bracket(
                structure.generator(second), structure.entry(third, first)
            )
            + structure.bracket(
                structure.generator(third), structure.entry(first, second)
            )
        )
        total = sympy.expand(cyclic)
        if total != 0:
            failures.append(
                f"the cyclic sum over ({first}, {second}, {third}) is {total}, "
                f"and the Jacobi identity requires it to be zero"
            )
    return failures


def casimir_failures(structure: PoissonStructure) -> list[str]:
    """Each declared Casimir against each generator."""
    failures = []
    for casimir in structure.casimirs:
        for name in structure.coordinates:
            total = structure.bracket(casimir.built, structure.generator(name))
            if total != 0:
                failures.append(
                    f"{{{casimir.name}, {name}}} = {total}, so '{casimir.name}' "
                    f"is not a Casimir of {structure.identifier} and anything "
                    f"measuring drift against it is measuring nothing"
                )
    return failures


def every_failure(structures: Iterable[PoissonStructure]) -> list[str]:
    failures = []
    for structure in structures:
        for failure in (
            *antisymmetry_failures(structure),
            *jacobi_failures(structure),
            *casimir_failures(structure),
        ):
            failures.append(f"{structure.identifier}: {failure}")
    return failures
