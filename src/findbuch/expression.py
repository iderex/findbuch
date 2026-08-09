"""Turn a formula string into a symbolic object, without evaluating any of it.

This is the boundary. `docs/decisions/0004-expression-grammar.md` is where it was
decided and it says the thing worth repeating here: there is no sandbox behind
this module and none is claimed. The grammar IS the boundary.

A formula arrives as a string in a file a stranger may have written. Handing that
string to the computer algebra library's own parser is a path to arbitrary code
execution wearing the appearance of mathematics, so the string is never handed to
it. What happens instead is three steps, in this order and no other:

1. The string is parsed into a syntax tree by the standard library. Parsing is
   not executing: nothing in the tree runs, nothing is looked up, and a tree is
   produced for input that would be refused two steps later.
2. The tree is walked against the admitted grammar. A node kind the grammar does
   not admit is refused where it stands, with its own identifier.
3. The symbolic object is built node by node from the walk. Only nodes that
   survived step 2 reach this step, and each one is turned into the library
   construction that corresponds to it.

THE SYMBOL TABLE IS BUILT BEFORE THE PARSE, from the coordinates of the
structure the row names and the parameters the row declares, and from nothing
else. An identifier outside that table is refused by name and is never a new free
variable. This is the quieter half of 0004 and the half that will cost more if it
is missing: a mistyped parameter that becomes a free variable makes a bracket
vanish for a reason that has nothing to do with the case, and a row that passes
verification for the wrong reason is worse than one that fails.

WHAT `pi` AND `e` ARE HERE: nothing. The record says the table is built from two
sources and no others, so a row needing a mathematical constant declares it as a
parameter or the grammar is widened deliberately, in the record, by somebody
arguing for it. A constant admitted quietly here would be the first hole in the
rule that makes an undeclared identifier an error.

WHAT A NUMERIC LITERAL MAY BE. Integers. 0004 admits "numeric literals, integer
and rational", and a rational has no literal spelling in this syntax, so a
rational is written as one integer over another and is exact by construction. A
decimal literal is refused, naming itself, because `0.1` is not the number it
appears to be and a verdict resting on it is a verdict about the wrong quantity.

WHAT THIS MODULE DOES NOT DECIDE. Whether the formula is the right formula,
whether the symbols mean what the source meant, whether the expression is even
dimensionally sensible. It decides that the string is inside the grammar and that
every identifier in it was declared. The mathematics is the symbolic and numeric
checkers, and nothing here is evidence about it.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import sympy

# The named allowlist 0004 requires, with the arities each name accepts. A call
# to anything not in this mapping is refused by name rather than resolved
# against whatever the library happens to export, because the library exports
# hundreds of names and a row is not an invitation to reach any of them.
#
# It is short on purpose. Widening it is a change to this file with a reason
# attached, which is the point of an allowlist; the alternative is a boundary
# that moves whenever a dependency adds a function.
ADMITTED_FUNCTIONS: Mapping[str, tuple[object, tuple[int, ...]]] = {
    "sqrt": (sympy.sqrt, (1,)),
    "exp": (sympy.exp, (1,)),
    "log": (sympy.log, (1, 2)),
    "sin": (sympy.sin, (1,)),
    "cos": (sympy.cos, (1,)),
    "tan": (sympy.tan, (1,)),
    "sinh": (sympy.sinh, (1,)),
    "cosh": (sympy.cosh, (1,)),
    "tanh": (sympy.tanh, (1,)),
}

# The four operations 0004 admits, plus the power handled separately because its
# exponent carries a rule of its own.
BINARY_OPERATORS: Mapping[type[ast.operator], str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.Pow: "**",
}

UNARY_OPERATORS: Mapping[type[ast.unaryop], str] = {
    ast.UAdd: "+",
    ast.USub: "-",
}


class ExpressionRefused(Exception):  # noqa: N818
    """One reason a formula string was refused, with where it happened.

    The name carries no `Error` suffix, which is what the `noqa` above is
    for. A refusal is not an error in this repository's vocabulary: it is a
    verdict the boundary reached about a file, the same word `Refusal` in
    findbuch.validation carries, and renaming it here would leave one
    concept with two names across two modules that hand it to each other.

    `code` is the identity and is what a test asserts on. The message is for the
    contributor who is reading a nineteenth century paper with one hand and this
    refusal with the other, so it names the offending token and its position. A
    corpus of files that must be refused is only worth having if it asserts WHICH
    refusal fired: asserting that something was raised passes on a typo in the
    fixture, and a typo refuses for a reason the test was not written about.
    """

    def __init__(self, code: str, message: str, where: str = "") -> None:
        stated = f"{code} at {where}: {message}" if where else f"{code}: {message}"
        super().__init__(stated)
        self.code = code
        self.message = message
        self.where = where


@dataclass(frozen=True)
class SymbolTable:
    """Every identifier a formula in this row may use, and where each came from.

    The two sources are kept apart rather than merged into one set, because a
    refusal that can say "this is a coordinate of the structure and not a
    parameter you declared" is worth more than one that can only say the name is
    unknown.
    """

    coordinates: tuple[str, ...]
    parameters: tuple[str, ...]

    @classmethod
    def of(cls, coordinates: Iterable[str], parameters: Iterable[str]) -> SymbolTable:
        return cls(tuple(coordinates), tuple(parameters))

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self.coordinates) | frozenset(self.parameters)

    def symbol(self, name: str) -> sympy.Symbol:
        return sympy.Symbol(name)

    def describe(self) -> str:
        coordinates = ", ".join(self.coordinates) or "none"
        parameters = ", ".join(self.parameters) or "none"
        return f"coordinates: {coordinates}; declared parameters: {parameters}"


def _where(text: str, node: ast.AST) -> str:
    """The offending token and its position, for the person reading the refusal."""
    line = getattr(node, "lineno", 0)
    column = getattr(node, "col_offset", -1) + 1
    segment = ast.get_source_segment(text, node) if hasattr(node, "lineno") else None
    shown = f" '{segment}'" if segment else ""
    return f"line {line}, column {column}{shown}"


def _refuse(code: str, message: str, text: str, node: ast.AST) -> ExpressionRefused:
    return ExpressionRefused(code, message, _where(text, node))


def _integer_literal(value: object) -> bool:
    # `True` is an int in this language and is not an integer literal in any
    # formula, so the type is checked exactly rather than with isinstance.
    return type(value) is int


def _build(node: ast.expr, table: SymbolTable, text: str) -> sympy.Expr:
    """Step 3, and step 2 in the same walk: admit the node or refuse it."""
    if isinstance(node, ast.Constant):
        if _integer_literal(node.value):
            return sympy.Integer(node.value)
        if isinstance(node.value, float):
            raise _refuse(
                "expression.decimal-literal",
                "a decimal literal is not an exact number; write it as one "
                "integer over another, for instance 1/2 rather than 0.5",
                text,
                node,
            )
        raise _refuse(
            "expression.literal-refused",
            f"a literal of type {type(node.value).__name__} is not a number the "
            f"grammar admits",
            text,
            node,
        )

    if isinstance(node, ast.Name):
        if node.id in table.names:
            return table.symbol(node.id)
        if node.id in ADMITTED_FUNCTIONS:
            raise _refuse(
                "expression.function-not-called",
                f"'{node.id}' is a function on the allowlist and is used here as "
                f"a symbol; write '{node.id}(...)'",
                text,
                node,
            )
        raise _refuse(
            "expression.unknown-symbol",
            f"'{node.id}' is not a coordinate of the named structure and is not "
            f"a parameter this row declares, so it is an error and not a new "
            f"free variable. {table.describe()}",
            text,
            node,
        )

    if isinstance(node, ast.BinOp):
        return _binary(node, table, text)

    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in UNARY_OPERATORS:
            raise _refuse(
                "expression.operator-refused",
                f"the unary operator {type(node.op).__name__} is not one the "
                f"grammar admits",
                text,
                node,
            )
        operand = _build(node.operand, table, text)
        return -operand if isinstance(node.op, ast.USub) else operand

    if isinstance(node, ast.Call):
        return _call(node, table, text)

    if isinstance(node, ast.Attribute):
        raise _refuse(
            "expression.attribute-access",
            "attribute access is not part of the grammar; it is how a formula "
            "reaches out of itself and into the interpreter",
            text,
            node,
        )

    if isinstance(node, ast.Subscript):
        raise _refuse(
            "expression.subscript",
            "indexing is not part of the grammar",
            text,
            node,
        )

    raise _refuse(
        "expression.node-refused",
        f"{type(node).__name__} is not part of the grammar, which admits numbers, "
        f"declared symbols, + - * /, integer powers and calls to "
        f"{', '.join(sorted(ADMITTED_FUNCTIONS))}",
        text,
        node,
    )


def _binary(node: ast.BinOp, table: SymbolTable, text: str) -> sympy.Expr:
    if type(node.op) not in BINARY_OPERATORS:
        raise _refuse(
            "expression.operator-refused",
            f"the operator {type(node.op).__name__} is not one of the four "
            f"operations and the integer power that the grammar admits",
            text,
            node,
        )
    left = _build(node.left, table, text)
    right = _build(node.right, table, text)
    if isinstance(node.op, ast.Add):
        return left + right
    if isinstance(node.op, ast.Sub):
        return left - right
    if isinstance(node.op, ast.Mult):
        return left * right
    if isinstance(node.op, ast.Div):
        return left / right
    # Pow, whose exponent carries the rule 0004 states separately.
    if not isinstance(right, sympy.Integer):
        raise _refuse(
            "expression.non-integer-exponent",
            f"the exponent is '{right}', and the grammar admits integer "
            f"exponents only; a square root is written sqrt(...)",
            text,
            node.right,
        )
    return left**right


def _call(node: ast.Call, table: SymbolTable, text: str) -> sympy.Expr:
    if not isinstance(node.func, ast.Name):
        raise _refuse(
            "expression.call-not-a-name",
            "only a plain call to a name on the allowlist is admitted; anything "
            "else is a call to something the file computed",
            text,
            node,
        )
    if node.keywords:
        raise _refuse(
            "expression.keyword-argument",
            "keyword arguments are not part of the grammar",
            text,
            node,
        )
    if node.func.id not in ADMITTED_FUNCTIONS:
        raise _refuse(
            "expression.unknown-function",
            f"'{node.func.id}' is not on the allowlist, which is "
            f"{', '.join(sorted(ADMITTED_FUNCTIONS))}",
            text,
            node.func,
        )
    function, arities = ADMITTED_FUNCTIONS[node.func.id]
    for argument in node.args:
        if isinstance(argument, ast.Starred):
            raise _refuse(
                "expression.starred-argument",
                "a starred argument is not part of the grammar",
                text,
                argument,
            )
    if len(node.args) not in arities:
        wanted = " or ".join(str(count) for count in arities)
        raise _refuse(
            "expression.arity",
            f"'{node.func.id}' takes {wanted} argument(s) and is called with "
            f"{len(node.args)}",
            text,
            node,
        )
    built = [_build(argument, table, text) for argument in node.args]
    applied: sympy.Expr = function(*built)  # type: ignore[operator]
    return applied


def parse(text: str, table: SymbolTable) -> sympy.Expr:
    """The whole boundary, in one call. Refuses by raising ExpressionRefused."""
    if not text.strip():
        raise ExpressionRefused(
            "expression.empty",
            "the expression is empty, and an empty formula is not the number "
            "zero written another way",
        )
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as broken:
        position = f"line {broken.lineno or 1}, column {broken.offset or 1}"
        raise ExpressionRefused(
            "expression.unparseable",
            f"the string is not an expression at all: {broken.msg}",
            position,
        ) from broken
    return _build(tree.body, table, text)


def parse_all(
    texts: Sequence[str], table: SymbolTable
) -> tuple[list[sympy.Expr], list[ExpressionRefused]]:
    """Parse a list of formulas, collecting refusals rather than stopping.

    A contributor with three mistakes in a row wants three refusals, not one per
    push. The caller decides what to do with a non-empty refusal list.
    """
    built: list[sympy.Expr] = []
    refused: list[ExpressionRefused] = []
    for text in texts:
        try:
            built.append(parse(text, table))
        except ExpressionRefused as refusal:
            refused.append(refusal)
    return built, refused
