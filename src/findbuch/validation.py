"""Refuse a malformed row.

What this refuses is SHAPE. A row that passes every check here is well formed
and is not verified, and nothing in this module is evidence about the
mathematics. Whether the bracket vanishes, whether the domain excludes the poles
of a denominator, whether the parameter conditions are the ones the source
actually stated: none of that is decidable by a pattern match, and faking it here
would produce a green result that a reader would take for a checked one. Those
questions belong to the symbolic and numeric checkers.

The split matters enough to state twice, so it is stated in the schema document
as well as here.

Two halves, and they refuse different things.

The published schema, `src/findbuch/data/schema/row-1.0.schema.json`, carries
everything one document can decide about itself: which fields are required, the
identifier form, the three validity kinds, the three roles, at least one
provenance entry.

This module carries what a single document cannot decide about itself. Whether
the structure it names exists is a question about another file. Whether its
constraints are present exactly when its validity kind requires them is a
relation between two of its own fields that JSON Schema can express only as an
unreadable pile of conditionals. Both are here, each with an identifier that a
test can assert on rather than matching text.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

from findbuch.expression import SymbolTable, parse_all

PACKAGE_ROOT = Path(__file__).resolve().parent

# Addressed through the package and never through the repository root. The path
# used to be the source file's grandparent, which is the checkout in a working
# copy and a directory beside `site-packages` in an installed one, so the schema
# was unreadable everywhere the package was installed rather than checked out.
# It is data the package carries, so it sits under the package and the constant
# is one hop from `__file__`. #84 is where that was measured.
DATA_ROOT = PACKAGE_ROOT / "data"
SCHEMA_PATH = DATA_ROOT / "schema" / "row-1.0.schema.json"

# Identifier-shaped tokens that are not symbols of a row. This is deliberately
# short and deliberately crude: it exists for one shape rule below and it is NOT
# an expression parser. The parser and the fixed symbol table are #21, and when
# that lands the rule using this list should be re-expressed against it rather
# than kept in step by hand.
NOT_A_SYMBOL = frozenset(
    {"sin", "cos", "tan", "sqrt", "exp", "log", "cosh", "sinh", "tanh", "pi", "e"}
)

TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

KINDS_NEEDING_CONSTRAINTS = frozenset({"conditional", "invariant-relation"})

# The fields whose strings are formulas, and therefore the fields the parser
# in findbuch.expression is applied to.
#
# WHAT IS NOT ON THIS LIST, and why, because a reader will otherwise take a
# clean row as a row whose every string was parsed. `domain.phase_space` and
# `domain.parameter_space` hold inequalities, `A1 > 0` being the shape, and a
# comparison is not in the admitted grammar. Reducing against a domain is #27
# for the symbolic side and #31 for the numeric one, and whatever reads those
# strings is what will decide their form. Nothing here checks them at all.
EXPRESSION_FIELDS: tuple[str, ...] = (
    "hamiltonian",
    "integrals",
    "constraints",
    "conditions",
)


@dataclass(frozen=True)
class Refusal:
    """One reason a row was refused.

    `code` is what a test asserts on. The message is for a person and may be
    reworded; the code may not, because a corpus of files that must be refused
    is only worth having if it asserts WHICH refusal fired.
    """

    code: str
    message: str
    where: str = ""

    def __str__(self) -> str:
        location = f" at {self.where}" if self.where else ""
        return f"{self.code}{location}: {self.message}"


@dataclass(frozen=True)
class Structure:
    """As much of a Poisson structure as validation needs to resolve a row.

    The real thing, with its bracket table and its declared Casimirs, is #25.
    This is the identifier and the coordinate names, which is what a row has to
    be resolved against and no more.
    """

    identifier: str
    coordinates: tuple[str, ...]


class StructureRegistry:
    """The structures a row may name.

    `coordinates_known` is separate from "has no coordinates" on purpose. A
    structure file that does not declare its coordinates leaves one rule below
    unable to run, and a rule that could not run has to say so rather than pass.
    """

    def __init__(self, structures: Iterable[Structure]) -> None:
        self._by_id = {structure.identifier: structure for structure in structures}

    @classmethod
    def from_directory(cls, directory: Path) -> StructureRegistry:
        structures = []
        for path in sorted(directory.glob("*.toml")):
            with path.open("rb") as handle:
                document = tomllib.load(handle)
            declared = document.get("coordinates", [])
            coordinates = tuple(str(name) for name in declared)
            structures.append(Structure(path.stem, coordinates))
        return cls(structures)

    @property
    def identifiers(self) -> frozenset[str]:
        return frozenset(self._by_id)

    def knows(self, identifier: str) -> bool:
        return identifier in self._by_id

    def coordinates_known(self, identifier: str) -> bool:
        structure = self._by_id.get(identifier)
        return structure is not None and bool(structure.coordinates)

    def coordinates(self, identifier: str) -> tuple[str, ...]:
        return self._by_id[identifier].coordinates


def load_schema() -> dict[str, Any]:
    import json

    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        loaded: dict[str, Any] = json.load(handle)
    return loaded


def _pointer(error: jsonschema.ValidationError) -> str:
    return "/".join(str(part) for part in error.absolute_path) or "(row)"


def check_shape(document: Mapping[str, Any]) -> list[Refusal]:
    """Everything the published schema decides on its own."""
    validator = jsonschema.Draft202012Validator(load_schema())
    refusals = []
    for error in sorted(validator.iter_errors(document), key=str):
        if error.validator == "required":
            # The message has to name the field, because "this row is invalid"
            # sends a contributor back to read the whole schema.
            missing = re.findall(r"'([^']+)' is a required property", error.message)
            for field in missing:
                refusals.append(
                    Refusal(
                        "schema.missing-field",
                        f"the required field '{field}' is missing",
                        _pointer(error),
                    )
                )
            continue
        refusals.append(
            Refusal(f"schema.{error.validator}", error.message, _pointer(error))
        )
    return refusals


def _declared_symbols(document: Mapping[str, Any]) -> set[str]:
    return {
        str(parameter.get("symbol", ""))
        for parameter in document.get("parameters", [])
        if isinstance(parameter, Mapping)
    }


def check_structure_resolves(
    document: Mapping[str, Any], registry: StructureRegistry
) -> list[Refusal]:
    named = document.get("structure")
    if not isinstance(named, str) or registry.knows(named):
        return []
    known = ", ".join(sorted(registry.identifiers)) or "none, the registry is empty"
    return [
        Refusal(
            "structure.unknown",
            f"the structure '{named}' does not exist; known structures: {known}",
            "structure",
        )
    ]


def check_constraints_match_validity(document: Mapping[str, Any]) -> list[Refusal]:
    """0005: constraints are required exactly when the kind requires them.

    A general row carrying constraints is a row whose author meant conditional.
    A conditional row carrying none will be checked against the empty ideal,
    which is the general question wearing another name.
    """
    kind = document.get("validity")
    if not isinstance(kind, str):
        return []
    constraints = document.get("constraints") or []
    if kind in KINDS_NEEDING_CONSTRAINTS and not constraints:
        return [
            Refusal(
                "validity.constraints-missing",
                f"validity is '{kind}', which is a claim about a constraint, and "
                f"no constraints are declared",
                "constraints",
            )
        ]
    if kind == "general" and constraints:
        return [
            Refusal(
                "validity.constraints-refused",
                "validity is 'general', which claims the bracket vanishes "
                "everywhere, so declaring constraints contradicts the kind; the "
                "row probably means 'conditional'",
                "constraints",
            )
        ]
    return []


def check_integrals_match_validity(document: Mapping[str, Any]) -> list[Refusal]:
    kind = document.get("validity")
    if not isinstance(kind, str):
        return []
    integrals = document.get("integrals") or []
    if kind == "invariant-relation" and integrals:
        return [
            Refusal(
                "validity.integral-on-invariant-relation",
                "validity is 'invariant-relation', which claims there is no "
                "additional integral, and an integral is declared",
                "integrals",
            )
        ]
    if kind in {"general", "conditional"} and not integrals:
        return [
            Refusal(
                "validity.integral-missing",
                f"validity is '{kind}', which claims an additional integral, and "
                f"none is declared",
                "integrals",
            )
        ]
    return []


def check_parameters_declared(
    document: Mapping[str, Any], registry: StructureRegistry
) -> list[Refusal]:
    """The Hamiltonian mentions parameters, so the parameter list is not empty.

    Crude on purpose and bounded by what it can see. It splits the Hamiltonian
    into identifier-shaped tokens and removes the coordinates of the named
    structure and the handful of names in NOT_A_SYMBOL. What is left is treated
    as a parameter mention. It is not a parser, it does not know operator
    precedence, and it will call a function this project has not heard of a
    parameter. #21 is the parser.
    """
    named = document.get("structure")
    hamiltonian = document.get("hamiltonian")
    if not isinstance(named, str) or not isinstance(hamiltonian, str):
        return []
    if not registry.knows(named) or not registry.coordinates_known(named):
        return []
    coordinates = set(registry.coordinates(named))
    mentioned = {
        token
        for token in TOKEN.findall(hamiltonian)
        if token not in coordinates and token not in NOT_A_SYMBOL
    }
    if mentioned and not _declared_symbols(document):
        listed = ", ".join(sorted(mentioned))
        return [
            Refusal(
                "parameters.undeclared",
                f"the hamiltonian mentions {listed}, which is neither a "
                f"coordinate of '{named}' nor a declared parameter, and the "
                f"parameter list is empty",
                "parameters",
            )
        ]
    return []


def _formulas(document: Mapping[str, Any], field: str) -> list[tuple[str, str]]:
    """The formulas in one field, each with where in the row it sits."""
    value = document.get(field)
    if isinstance(value, str):
        return [(value, field)]
    if isinstance(value, list):
        return [
            (entry, f"{field}[{index}]")
            for index, entry in enumerate(value)
            if isinstance(entry, str)
        ]
    return []


def check_expressions_parse(
    document: Mapping[str, Any], registry: StructureRegistry
) -> list[Refusal]:
    """0004: every formula is inside the grammar and names only declared symbols.

    The symbol table is built first, from the coordinates of the named structure
    and the parameters this row declares, so an identifier outside it is an error
    naming the identifier rather than a new free variable. findbuch.expression
    holds the grammar and the argument for it.

    The rule does not run when the structure does not resolve or declares no
    coordinates, and that is why `RowResult.expressions_rule_evaluated` exists. A
    table missing its coordinates would refuse every coordinate in every formula,
    which is a pile of refusals about the structure file wearing the identifier
    of a refusal about the row.
    """
    named = document.get("structure")
    if not isinstance(named, str):
        return []
    if not registry.knows(named) or not registry.coordinates_known(named):
        return []
    table = SymbolTable.of(registry.coordinates(named), _declared_symbols(document))
    refusals: list[Refusal] = []
    for field in EXPRESSION_FIELDS:
        for text, where in _formulas(document, field):
            _, refused = parse_all([text], table)
            for refusal in refused:
                location = f"{where}, {refusal.where}" if refusal.where else where
                refusals.append(Refusal(refusal.code, refusal.message, location))
    return refusals


def check_identifier_matches_file(
    document: Mapping[str, Any], file_stem: str
) -> list[Refusal]:
    identifier = document.get("id")
    if not isinstance(identifier, str) or identifier == file_stem:
        return []
    return [
        Refusal(
            "id.mismatches-file-name",
            f"the row declares id '{identifier}' and lives in a file named "
            f"'{file_stem}'; 0003 makes the file name the identifier",
            "id",
        )
    ]


def check_supersession_points_somewhere(document: Mapping[str, Any]) -> list[Refusal]:
    if document.get("status") != "superseded":
        return []
    if document.get("superseded_by"):
        return []
    return [
        Refusal(
            "status.superseded-without-pointer",
            "the status is 'superseded' and no 'superseded_by' identifier is "
            "given, so a citation of this row resolves to a dead end",
            "superseded_by",
        )
    ]


def validate_row(
    document: Mapping[str, Any], *, file_stem: str, registry: StructureRegistry
) -> list[Refusal]:
    """Every refusal this row earns, shape first.

    The shape half runs first and short-circuits: the rules below it read fields
    by name, and reading a field out of a document that failed its own schema
    produces a second refusal about the first one's cause.
    """
    shape = check_shape(document)
    if shape:
        return shape
    refusals: list[Refusal] = []
    refusals.extend(check_identifier_matches_file(document, file_stem))
    refusals.extend(check_structure_resolves(document, registry))
    refusals.extend(check_constraints_match_validity(document))
    refusals.extend(check_integrals_match_validity(document))
    refusals.extend(check_parameters_declared(document, registry))
    refusals.extend(check_expressions_parse(document, registry))
    refusals.extend(check_supersession_points_somewhere(document))
    return refusals


@dataclass(frozen=True)
class RowResult:
    path: Path
    refusals: tuple[Refusal, ...]
    parameters_rule_evaluated: bool
    # Both flags answer the same question today, whether the named structure
    # resolved and declared its coordinates, and they are separate because they
    # are about two rules that happen to share a precondition. A run reporting
    # one of them as if it were the other is the shape this repository keeps
    # finding, so neither is derived from the other.
    expressions_rule_evaluated: bool = False

    @property
    def valid(self) -> bool:
        return not self.refusals


def validate_file(path: Path, registry: StructureRegistry) -> RowResult:
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except FileNotFoundError:
        # A refusal rather than an exception, because a caller validating a
        # list of rows has to be able to report a missing one beside the
        # malformed ones instead of stopping at it. The identifier is what
        # tests/test_refusal_shape.py asserts on; #15 built this one first
        # because it is the smallest refusal in the project and the shape it
        # demonstrates is what every later refusal test follows.
        return RowResult(
            path,
            (
                Refusal(
                    "file.missing",
                    f"no file at '{path}', so there is nothing to validate",
                    path.name,
                ),
            ),
            parameters_rule_evaluated=False,
        )
    except tomllib.TOMLDecodeError as error:
        return RowResult(
            path,
            (Refusal("toml.unparseable", str(error), path.name),),
            parameters_rule_evaluated=False,
        )
    named = document.get("structure")
    evaluated = (
        isinstance(named, str)
        and registry.knows(named)
        and registry.coordinates_known(named)
    )
    refusals = validate_row(document, file_stem=path.stem, registry=registry)
    return RowResult(
        path,
        tuple(refusals),
        parameters_rule_evaluated=evaluated,
        expressions_rule_evaluated=evaluated,
    )


def validate_catalogue(catalogue: Path, registry: StructureRegistry) -> list[RowResult]:
    rows = sorted(catalogue.glob("*.toml"))
    return [validate_file(path, registry) for path in rows]
