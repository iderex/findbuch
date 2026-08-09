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

# The numbers an expression is bounded by, stated here and nowhere else.
#
# None of them is a rule of the grammar. They refuse strings the grammar admits,
# because the grammar has nothing to say about a formula that is well formed and
# enormous, and those are the two inputs that have no clean refusal in it: a
# deeply nested expression and one whose expansion is huge. They are bounded
# instead, and a bound is a number somebody chose, so the reason is beside it.
#
# There are three numbers for two attacks, and the third is here because the
# depth cannot be measured until the language's own parser has produced a tree,
# and that parser is itself defeated by a long enough string. So the length is
# bounded in front of it.
#
# MAXIMUM_DEPTH is how deeply the syntax tree may nest. The walk below is
# recursive, at least one frame per node, so a string nested past the
# interpreter's own recursion limit ends the process instead of refusing the
# file, and a boundary that the input side can crash is not a boundary. The
# depth is measured with an explicit stack, before the recursive walk starts,
# because a check that recurses to find out whether recursing is safe is not a
# check. 64 is far above anything transcription produces, and no formula in this
# tree comes near it; tests/test_expression_bounds.py measures that rather than
# asserting it, so a row that starts to approach the limit reddens.
MAXIMUM_DEPTH = 64

# MAXIMUM_TERMS is how many terms the expression may expand to. Depth alone does
# not bound that, and the case that shows why is three characters long:
# `(M1+M2+M3)**1000` nests four deep and expands to more terms than there are
# atoms in anything. So the count is bounded structurally, without expanding
# anything, and the bound is applied in two places, both of them below: to the
# magnitude of an integer exponent, before that power is taken, and to the whole
# expression once it is built.
#
# 4096 is above what the catalogue holds and below where an exact polynomial
# identity stops being quick, and the same test measures the tree against it.
# That there is headroom for the rows NOT YET ENTERED is a claim rather than a
# measurement, and it is named as one: Yehia's generalisations are the rows most
# likely to test it, and a row genuinely refused by this number is an argument
# for raising it here, with its own measurement, rather than anywhere else.
#
# WHAT THESE TWO DO NOT BOUND, stated rather than left to be discovered. They
# bound what this module builds and hands on. They say nothing about what a
# later checker does with it: an expression of 4000 terms reduced against an
# ideal can still take longer than anybody will wait, and that is the symbolic
# leg's bound to choose and not this one.
MAXIMUM_TERMS = 4096

# MAXIMUM_LENGTH is how long the string may be, and it is checked before the
# string is handed to anything. The depth above is measured on a tree, and the
# tree is built by the language's own parser, which has no such limit of its own
# and gives out on a long enough input. What it gives out with, and where,
# depends on the interpreter:
#
#     ast.parse('-'*20000 + 'M1', mode='eval')   MemoryError    3.14, the pin
#     ast.parse('-'*4095 + 'M1', mode='eval')    RecursionError 3.11, the floor
#
# Neither is a refusal. Both are the boundary falling over, which is what the
# depth limit exists to prevent, one step further out. Nothing catches them
# afterwards either: a catch around the parser would be a branch nothing in this
# tree can reach, and an unreachable branch is not a guard.
#
# So the number is not chosen for how long a formula might be. It is chosen so
# that NO string this module hands to that parser can reach its capacity on the
# lowest interpreter the project claims. One character can open at most one level
# of nesting, `-` being the character that does it, so a string of N characters
# nests at most N deep, and the tree is built by recursion bounded by the
# interpreter's own recursion limit, which is 1000 by default. 512 sits under
# that with room for the frames a caller has already used. It is not asserted
# from here: `tests/test_expression_bounds.py` parses a string at the limit, and
# that test runs on the floor interpreter as well as on the pinned one, so the
# floor is where the claim is actually decided.
#
# WHAT IT COSTS: a formula longer than 512 characters is refused before it is
# read, however legal it is. Nothing in the grammar makes such a formula
# impossible, and the longest in this tree is well inside it. If the catalogue
# ever holds one that is an argument for raising this number, and it is a real
# argument only together with a measurement of the parser it has to survive.
MAXIMUM_LENGTH = 512


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


def _depth(node: ast.AST) -> int:
    """How deeply the tree nests, measured with an explicit stack.

    Not recursive, and that is the whole point of it: this is the check that
    decides whether the recursive walk further down is safe to start, and a
    check that recurses to find out whether recursing is safe answers the
    question by falling over. It stops as soon as the limit is passed, so a
    pathological tree is not walked to the end to find out that it is one.
    """
    deepest = 0
    pending: list[tuple[ast.AST, int]] = [(node, 1)]
    while pending:
        current, depth = pending.pop()
        if depth > MAXIMUM_DEPTH:
            return depth
        deepest = max(deepest, depth)
        for child in ast.iter_child_nodes(current):
            pending.append((child, depth + 1))
    return deepest


def _bounded_power(base: int, exponent: int) -> int:
    """`base ** exponent`, abandoned as soon as it passes the limit.

    Computing the power and then comparing it is the obvious spelling and it is
    the one that hangs, because the string decides the exponent.
    """
    if base <= 1:
        return base
    # The base is two or more, so anything from here up is already past the
    # limit, and the multiplication that would demonstrate it is the one being
    # avoided.
    if exponent >= MAXIMUM_TERMS.bit_length():
        return MAXIMUM_TERMS + 1
    # Both callers pass a magnitude, so the exponent is not negative and the
    # power is a whole number. The conversion says so to the type checker, which
    # otherwise has to allow for the negative case and the fraction it returns.
    return int(base**exponent)


def _expansion_bound(expression: sympy.Expr) -> int:
    """An upper bound on how many terms this expands to, expanding nothing.

    Structural, so it costs one walk of an object that is already built and
    never the expansion itself. It is an upper bound rather than the count: a
    product of two sums is bounded by the product of their term counts, and
    cancellation only ever makes the real number smaller.
    """
    if expression.is_Atom:
        return 1
    if expression.is_Add:
        total = 0
        for term in expression.args:
            total += _expansion_bound(term)
            if total > MAXIMUM_TERMS:
                return MAXIMUM_TERMS + 1
        return total
    if expression.is_Mul:
        product = 1
        for factor in expression.args:
            product *= _expansion_bound(factor)
            if product > MAXIMUM_TERMS:
                return MAXIMUM_TERMS + 1
        return product
    if expression.is_Pow:
        base, exponent = expression.args
        bound = _expansion_bound(base)
        # A non-integer exponent reaches here only as the library's spelling of
        # a root, `sqrt(x)` being `x**(1/2)`, which expands to one term of
        # whatever is underneath it.
        if exponent.is_Integer:
            return _bounded_power(bound, abs(int(exponent)))
        return bound
    # A call on the allowlist. `sin(x + y)` is one term of its argument, so what
    # bounds it is the largest thing inside it.
    return max((_expansion_bound(argument) for argument in expression.args), default=1)


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
    exponent = abs(int(right))
    # The magnitude first, and before the power is taken. `2**10**9` is legal
    # arithmetic, expands to one term, and produces a number with a billion bits
    # if anything ever asks it to.
    if exponent > MAXIMUM_TERMS:
        raise _refuse(
            "expression.too-large",
            f"the exponent is {exponent} and the limit is {MAXIMUM_TERMS}; a "
            f"formula in this catalogue does not need a power that large, and "
            f"one that does is an argument for raising the limit where it is "
            f"stated",
            text,
            node.right,
        )
    # What a power of a SUM expands to is not checked here, and the omission is
    # deliberate. It was written, and then removed because disabling it left the
    # suite green: raising a sum to a power builds an object and expands
    # nothing, so the count at the bottom of `parse` reaches the same verdict
    # with the same identifier. A guard whose deletion nothing notices is not a
    # guard, and keeping it would have meant one more branch nothing proves.
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
    if len(text) > MAXIMUM_LENGTH:
        raise ExpressionRefused(
            "expression.too-long",
            f"the string is {len(text)} characters and the limit is "
            f"{MAXIMUM_LENGTH}; this is checked before the string is parsed, "
            f"because the parser is what a long enough string defeats",
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
    # The position rather than the offending token, in this refusal and the one
    # at the bottom: the token here is the whole string, and a message that
    # quotes a hundred nested parentheses back at somebody says nothing.
    position = f"line {tree.body.lineno}, column {tree.body.col_offset + 1}"
    if _depth(tree.body) > MAXIMUM_DEPTH:
        raise ExpressionRefused(
            "expression.too-deep",
            f"the expression nests more than {MAXIMUM_DEPTH} deep, which is the "
            f"limit; the walk that builds it is recursive and a string can "
            f"otherwise end the process rather than be refused by it",
            position,
        )
    built = _build(tree.body, table, text)
    # Last, because it is about the whole expression rather than any one node.
    # A long product of sums nests no deeper than the number of factors and
    # expands to the product of their term counts, so nothing above catches it.
    if _expansion_bound(built) > MAXIMUM_TERMS:
        raise ExpressionRefused(
            "expression.too-large",
            f"the expression expands to more than {MAXIMUM_TERMS} terms, which "
            f"is the limit",
            position,
        )
    return built


@dataclass(frozen=True)
class Measured:
    """What the two limits are about, for one string the grammar admits."""

    depth: int
    terms: int


def measure(text: str, table: SymbolTable) -> Measured:
    """Both quantities, for a string that is inside the grammar.

    It exists so that the headroom under the two limits can be measured rather
    than asserted. A string outside the grammar is refused here as it is
    anywhere else, because a measurement of something that would never be parsed
    is not a measurement of anything.
    """
    built = parse(text, table)
    return Measured(_depth(ast.parse(text, mode="eval").body), _expansion_bound(built))


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
