"""Advance a state on a Poisson structure at arbitrary working precision.

`docs/decisions/0007-numeric-criterion.md` decided that the verdict is a
comparison between two measured numbers: the drift of a candidate integral
against the drift of the declared Casimirs from the same run. That criterion is
worth nothing if the floor it measures against is set by the method rather than
by the arithmetic, so what the integrator is decides what the criterion can say.
This module is the integrator. It reaches no verdict about a row; the drift
comparison is #32 and the sweep that runs it over the catalogue is #34.

WHY AN IMPLICIT COLLOCATION METHOD AND NOT AN ADAPTIVE SOLVER. The Casimirs of
this family are quadratic, and a Gauss collocation method conserves every
quadratic first integral exactly, because its tableau satisfies
`b_i a_ij + b_j a_ji - b_i b_j = 0` for every pair. `symplecticity_failures`
below checks that of the tableau this module builds, so the property is decided
per run rather than remembered from a textbook. A general adaptive solver has no
such relation, its Casimir error grows with the run, and the floor rises until
it meets the signal. At that point the criterion stops telling a conserved
quantity from a well-behaved one, which is the one thing it exists to do.

WHY THE ORDER IS AN INPUT AND NOT A CONSTANT. The control run in #32 raises the
working precision and asks whether the drift falls. For a Casimir it falls,
because a Gauss method conserves it exactly and what is left is round-off. For a
candidate integral that is not a Casimir, backward error analysis bounds the
drift by the method's own error, which is of order `step ** (2 * stages)` and
does not move when the precision does. So a method of fixed order turns the
control run into a comparison of two identical numbers as soon as the precision
passes the discretisation error. The stage count is therefore chosen against the
precision by whoever asks for the run, it is recorded with the result, and it
has no default, for the same reason the step and the precision have none.

WHAT IS RECORDED WITH EVERY RESULT: the structure, the Hamiltonian as written,
the initial condition, the step, the number of steps, the working precision, the
stage count and the bound on the stage iteration. `Inputs.command` prints them
back as the argument list that reproduces the run. A number this module reports
that cannot be reproduced from what is printed beside it is a defect rather than
a detail.

THE INITIAL CONDITION AND THE STEP ARE WRITTEN AS TEXT, and a float is refused.
`0.1` in the source is not the number the author wrote, it is the nearest binary
double to it, and it enters the record as a different number from the one that
appears in the paper the row came from. A decimal string is read at the working
precision, so raising the precision reads the same written number more exactly
rather than reading a different one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import mpmath
import sympy

from findbuch.structures import PoissonStructure

# mpmath ships no type information, so every value that crosses its boundary is
# `Any` to the checker. The alias names that rather than leaving bare `Any`
# scattered through the signatures, and it is what a reader should read as "a
# number at the working precision".
Number = Any

# The bound on the stage iteration, which is a safety net and not a criterion.
# The iteration stops when its correction stops shrinking, which is where the
# arithmetic can do no better; this bound only decides how long a run that is
# not converging is allowed to look like one before it is refused.
MAXIMUM_ITERATIONS = 200

# Extra digits carried while the tableau is built, so that the nodes and the
# weights are already correct at the working precision rather than correct to
# within their own construction error. It buys accuracy in a constant computed
# once per run and nothing else depends on its value.
TABLEAU_GUARD_DIGITS = 10

# Extra digits used when a state is written back as text. A number held to n
# decimal digits does not read back as itself from n decimal digits, because the
# arithmetic underneath is binary and the two grids do not line up.
# `AStateSurvivesBeingWrittenDown` in tests/test_integrator.py is what decides
# that this many is enough, rather than this comment.
WRITE_BACK_DIGITS = 5


class IntegratorRefused(Exception):  # noqa: N818
    """One reason a run was refused.

    No `Error` suffix, for the reason given at `ExpressionRefused` in
    findbuch.expression: a refusal is a verdict this project reached, and it is
    one concept rather than two.
    """

    def __init__(self, code: str, message: str, where: str = "") -> None:
        stated = f"{code} at {where}: {message}" if where else f"{code}: {message}"
        super().__init__(stated)
        self.code = code
        self.message = message
        self.where = where


def _exact(value: object, name: str) -> str:
    """A number written as text, or an integer. A float is refused.

    The refusal is the point rather than an inconvenience. A binary float that
    reached here was written as a decimal somewhere and is no longer that
    decimal, and the record this module keeps would carry the wrong one.
    """
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise IntegratorRefused(
            "integrator.number-is-not-written-exactly",
            f"'{name}' arrived as {type(value).__name__}. Write it as a decimal "
            f"string or an integer: a binary float is not the decimal somebody "
            f"typed, and the record of this run would carry the number the "
            f"machine chose rather than the number the row states",
            name,
        )
    return str(value)


def _read(text: str, name: str) -> Number:
    """One written number, read at whatever precision is in force."""
    try:
        return mpmath.mpf(text)
    except (ValueError, TypeError) as reason:
        raise IntegratorRefused(
            "integrator.number-is-unreadable",
            f"'{name}' is written as {text!r}, which is not a number: {reason}",
            name,
        ) from reason


@dataclass(frozen=True)
class Inputs:
    """Everything a run rests on, in the form that reproduces it.

    Held as written text rather than as numbers, so the record is independent of
    the precision the run happened to use and a reader can raise the precision
    and read the same written numbers again.
    """

    structure: str
    hamiltonian: str
    coordinates: tuple[str, ...]
    state: tuple[str, ...]
    step: str
    steps: int
    precision: int
    stages: int
    iterations: int

    @property
    def length(self) -> str:
        return f"{self.steps} steps of {self.step}"

    def command(self) -> str:
        """The argument list that runs this again."""
        state = " ".join(self.state)
        return (
            f"python tools/casimir_drift.py"
            f" --structure {self.structure}"
            f" --hamiltonian '{self.hamiltonian}'"
            f" --state {state}"
            f" --step {self.step}"
            f" --steps {self.steps}"
            f" --precision {self.precision}"
            f" --stages {self.stages}"
        )


@dataclass(frozen=True)
class Method:
    """A Gauss collocation tableau at the working precision.

    `nodes` are on [0, 1] and ascending, `weights` integrate over the same
    interval, and `matrix[i][j]` integrates the j-th Lagrange basis polynomial
    from 0 to the i-th node. Nothing here is a table of digits copied out of a
    book: every entry is computed at the precision the run asked for, which is
    what lets the stage count move with the precision.
    """

    stages: int
    precision: int
    nodes: tuple[Number, ...]
    weights: tuple[Number, ...]
    matrix: tuple[tuple[Number, ...], ...]

    @property
    def order(self) -> int:
        return 2 * self.stages


def _legendre(degree: int, argument: Number) -> tuple[Number, Number]:
    """P_n and its derivative at one point, by the three-term recurrence.

    The recurrence is used rather than an expanded polynomial because the
    expanded coefficients of a Legendre polynomial of even modest degree cancel
    catastrophically, and a node computed from them is wrong in a way that
    nothing downstream would notice: the tableau would still look like a
    tableau, and the method would quietly lose its order.
    """
    previous = mpmath.mpf(1)
    current = argument
    for order in range(2, degree + 1):
        previous, current = (
            current,
            ((2 * order - 1) * argument * current - (order - 1) * previous) / order,
        )
    derivative = degree * (argument * current - previous) / (argument * argument - 1)
    return current, derivative


def _refine(guess: Number, degree: int) -> Number:
    """Newton on P_n from one starting point, until the correction stops falling."""
    previous_correction = None
    for _ in range(MAXIMUM_ITERATIONS):
        value, derivative = _legendre(degree, guess)
        correction = value / derivative
        guess = guess - correction
        size = abs(correction)
        if size == 0:
            return guess
        if previous_correction is not None and size >= previous_correction:
            return guess
        previous_correction = size
    return guess


def _nodes_and_weights(stages: int) -> tuple[list[Number], list[Number]]:
    """Gauss-Legendre nodes and weights on [0, 1], ascending."""
    nodes = []
    weights = []
    for index in range(stages, 0, -1):
        start = mpmath.cos(
            mpmath.pi * (index - mpmath.mpf(1) / 4) / (stages + mpmath.mpf(1) / 2)
        )
        root = _refine(start, stages)
        _, derivative = _legendre(stages, root)
        weight = 2 / ((1 - root * root) * derivative * derivative)
        nodes.append((1 + root) / 2)
        weights.append(weight / 2)
    return nodes, weights


def _basis_integral(nodes: Sequence[Number], chosen: int, upper: Number) -> Number:
    """The integral from 0 to `upper` of the Lagrange basis polynomial at `chosen`."""
    coefficients = [mpmath.mpf(1)]
    denominator = mpmath.mpf(1)
    for index, node in enumerate(nodes):
        if index == chosen:
            continue
        raised = [mpmath.mpf(0)] * (len(coefficients) + 1)
        for power, value in enumerate(coefficients):
            raised[power + 1] += value
            raised[power] -= value * node
        coefficients = raised
        denominator = denominator * (nodes[chosen] - node)
    total = mpmath.mpf(0)
    for power, value in enumerate(coefficients):
        total = total + value * upper ** (power + 1) / (power + 1)
    return total / denominator


def gauss(stages: int) -> Method:
    """The s-stage Gauss collocation tableau, built at the precision in force."""
    if stages < 1:
        raise IntegratorRefused(
            "integrator.stages-below-one",
            f"{stages} stages were asked for. A collocation method has at least "
            f"one stage, and the stage count is what sets the order the run "
            f"reaches",
            "stages",
        )
    with mpmath.workdps(mpmath.mp.dps + TABLEAU_GUARD_DIGITS):
        nodes, weights = _nodes_and_weights(stages)
        matrix = tuple(
            tuple(
                _basis_integral(nodes, column, nodes[row]) for column in range(stages)
            )
            for row in range(stages)
        )
    return Method(
        stages=stages,
        precision=mpmath.mp.dps,
        nodes=tuple(+node for node in nodes),
        weights=tuple(+weight for weight in weights),
        matrix=tuple(tuple(+entry for entry in row) for row in matrix),
    )


def symplecticity_failures(method: Method) -> list[str]:
    """The relation that makes a quadratic first integral exactly conserved.

    `b_i a_ij + b_j a_ji - b_i b_j = 0` on every pair. A method satisfying it
    conserves every quadratic invariant of every system it is applied to, which
    is where the Casimir floor of #32 comes from. It is checked rather than
    asserted, because the tableau is computed here rather than quoted, and a
    tableau that has gone wrong still looks like a tableau.

    The comparison is against the working precision rather than against zero:
    the entries are computed numbers and the relation holds exactly only in
    exact arithmetic. What is reported is the size of the residual, and the
    caller decides what to do with it.
    """
    failures = []
    with mpmath.workdps(method.precision):
        bound = mpmath.mpf(2) ** (4 - mpmath.mp.prec)
        for row in range(method.stages):
            for column in range(method.stages):
                left = method.weights[row] * method.matrix[row][column]
                right = method.weights[column] * method.matrix[column][row]
                product = method.weights[row] * method.weights[column]
                residual = abs(left + right - product)
                if residual > bound:
                    failures.append(
                        f"b{row} a{row}{column} + b{column} a{column}{row} - "
                        f"b{row} b{column} = {mpmath.nstr(residual, 8)}, and a "
                        f"quadratic invariant is conserved only where it is zero"
                    )
    return failures


def _refuse_a_stranger(
    expression: sympy.Expr, coordinates: Sequence[str], where: str
) -> None:
    """Every free symbol has to be a coordinate of the structure.

    Checked on the Hamiltonian before any bracket is taken as well as on each
    component afterwards, because a parameter can vanish from every component
    and still be in the Hamiltonian: the bracket of a constant is zero whatever
    the constant is made of.
    """
    stranger = sorted(
        str(name) for name in expression.free_symbols if str(name) not in coordinates
    )
    if stranger:
        raise IntegratorRefused(
            "integrator.expression-names-a-stranger",
            f"'{', '.join(stranger)}' is not a coordinate of this structure. "
            f"Parameters are substituted for numbers before a run, because a "
            f"trajectory is a statement about one point of the parameter space "
            f"and a free symbol in it is not a number anything can integrate",
            where,
        )


def _monomials(
    expression: sympy.Expr, coordinates: Sequence[str], where: str
) -> tuple[tuple[int, int, tuple[int, ...]], ...]:
    """One polynomial as exact rational monomials over the coordinates.

    Exact rather than evaluated, so the same expression can be read at any
    working precision without being read differently. A coefficient that is not
    rational is refused rather than rounded: rounding it here would put a number
    nobody wrote into the flow, and the run would report a drift partly caused
    by this module.
    """
    symbols = [sympy.Symbol(name) for name in coordinates]
    _refuse_a_stranger(expression, coordinates, where)
    try:
        polynomial = sympy.Poly(sympy.expand(expression), *symbols)
    except sympy.PolynomialError as reason:
        raise IntegratorRefused(
            "integrator.expression-is-not-polynomial",
            f"this expression is not a polynomial in the coordinates: {reason}",
            where,
        ) from reason
    built = []
    for exponents, value in polynomial.terms():
        if not value.is_Rational:
            raise IntegratorRefused(
                "integrator.coefficient-is-not-rational",
                f"the coefficient {value} is not a rational number. Every "
                f"coefficient is carried exactly so that raising the precision "
                f"reads the same expression more exactly rather than a "
                f"different one",
                where,
            )
        if value == 0:
            continue
        built.append((int(value.p), int(value.q), tuple(int(one) for one in exponents)))
    return tuple(built)


def _prepared(
    monomials: Sequence[tuple[int, int, tuple[int, ...]]],
) -> tuple[tuple[Number, tuple[tuple[int, int], ...]], ...]:
    """The same monomials with their coefficients read at the precision in force."""
    return tuple(
        (
            mpmath.mpf(numerator) / denominator,
            tuple((place, power) for place, power in enumerate(exponents) if power),
        )
        for numerator, denominator, exponents in monomials
    )


def _value(
    prepared: Sequence[tuple[Number, tuple[tuple[int, int], ...]]],
    state: Sequence[Number],
) -> Number:
    total = mpmath.mpf(0)
    for coefficient, powers in prepared:
        term = coefficient
        for place, power in powers:
            term = term * state[place] ** power
        total = total + term
    return total


@dataclass(frozen=True)
class Field:
    """The flow of one Hamiltonian on one structure, as exact monomials.

    One component per coordinate, each the bracket of that coordinate with the
    Hamiltonian. The bracket is `findbuch.structures`' rather than one written
    here: 0002 says the checker never contains a bracket, and an integrator with
    its own copy of the table is a checker with a bracket in it.
    """

    coordinates: tuple[str, ...]
    components: tuple[tuple[tuple[int, int, tuple[int, ...]], ...], ...]

    @classmethod
    def of(cls, structure: PoissonStructure, hamiltonian: sympy.Expr) -> Field:
        _refuse_a_stranger(hamiltonian, structure.coordinates, "the Hamiltonian")
        components = tuple(
            _monomials(
                structure.bracket(structure.generator(name), hamiltonian),
                structure.coordinates,
                f"d{name}/dt",
            )
            for name in structure.coordinates
        )
        return cls(coordinates=structure.coordinates, components=components)


@dataclass(frozen=True)
class Run:
    """A trajectory and what it took to produce it."""

    inputs: Inputs
    method: Method
    states: tuple[tuple[Number, ...], ...]
    settled: Number
    used: int

    @property
    def initial(self) -> tuple[Number, ...]:
        return self.states[0]

    @property
    def final(self) -> tuple[Number, ...]:
        return self.states[-1]

    def written(self, state: Sequence[Number]) -> tuple[str, ...]:
        """One state as decimal text that reads back as the same number.

        Text rather than a number, because text is what starts a run: the
        initial condition of every run is written, so a state handed from one
        run to the next has to survive being written down. The extra digits are
        what makes reading it back exact rather than nearly exact, and the
        equality is asserted in the suite rather than assumed here.
        """
        with mpmath.workdps(self.inputs.precision):
            return tuple(
                mpmath.nstr(value, self.inputs.precision + WRITE_BACK_DIGITS)
                for value in state
            )


def _solve_stages(
    field: Sequence[tuple[tuple[Number, tuple[tuple[int, int], ...]], ...]],
    method: Method,
    state: Sequence[Number],
    step: Number,
    iterations: int,
) -> tuple[list[list[Number]], int, Number]:
    """The stage values, by an iteration that stops where the arithmetic does.

    There is no number in this loop that anybody picked. The iteration stops
    when its correction reaches zero, which is what a fixed point looks like in
    finite precision, or when the correction stops falling, which is the same
    point reached one bit later. It is refused when the correction grows past
    its first value, because that is divergence rather than slow progress, and
    when the bound above is exhausted with the correction still falling, because
    a stage nobody solved is a state nobody computed.
    """
    width = len(state)
    stages = [list(state) for _ in range(method.stages)]
    first_correction = None
    previous_correction = None
    for used in range(1, iterations + 1):
        rates = [[_value(one, stage) for one in field] for stage in stages]
        correction = mpmath.mpf(0)
        following = []
        for row in range(method.stages):
            built = []
            for place in range(width):
                total = state[place]
                for column in range(method.stages):
                    entry = method.matrix[row][column]
                    if entry != 0:
                        total = total + step * entry * rates[column][place]
                built.append(total)
                moved = abs(built[place] - stages[row][place])
                if moved > correction:
                    correction = moved
            following.append(built)
        stages = following
        if correction == 0:
            return stages, used, correction
        if first_correction is None:
            first_correction = correction
        elif correction > first_correction:
            raise IntegratorRefused(
                "integrator.stage-iteration-diverges",
                f"the stage correction grew from {mpmath.nstr(first_correction, 8)} "
                f"to {mpmath.nstr(correction, 8)} in {used} passes. The step is "
                f"too long for this field: an implicit stage is a fixed point "
                f"and this one is being pushed away from",
                "step",
            )
        if (
            previous_correction is not None
            and correction >= previous_correction
            and correction < first_correction
        ):
            return stages, used, correction
        previous_correction = correction
    raise IntegratorRefused(
        "integrator.stage-iteration-did-not-settle",
        f"the stage correction was still falling after {iterations} passes. A "
        f"state advanced from stages nobody solved is a number with nothing "
        f"behind it, so the run is refused rather than reported",
        "iterations",
    )


def integrate(
    structure: PoissonStructure,
    hamiltonian: sympy.Expr,
    state: Sequence[object],
    step: object,
    steps: int,
    precision: int,
    stages: int,
    iterations: int = MAXIMUM_ITERATIONS,
) -> Run:
    """Advance a state on a structure, and give back the trajectory and its record.

    Every input is required. None of them has a default that a later verdict
    could rest on without anybody choosing it, which is what 0007 asks of the
    numeric leg, and the one argument that carries a default is the bound on the
    stage iteration, which decides nothing about the answer and only how long a
    run that is not converging may take to be refused.
    """
    if precision < 1:
        raise IntegratorRefused(
            "integrator.precision-below-one",
            f"a working precision of {precision} decimal digits was asked for",
            "precision",
        )
    if steps < 1:
        raise IntegratorRefused(
            "integrator.steps-below-one",
            f"{steps} steps were asked for, so there is no trajectory to produce",
            "steps",
        )
    if len(state) != len(structure.coordinates):
        raise IntegratorRefused(
            "integrator.state-does-not-match-the-structure",
            f"{len(state)} values were given for the {len(structure.coordinates)} "
            f"coordinates of {structure.identifier}, which are "
            f"{', '.join(structure.coordinates)}",
            "state",
        )
    written = tuple(
        _exact(value, structure.coordinates[place]) for place, value in enumerate(state)
    )
    written_step = _exact(step, "step")
    field = Field.of(structure, hamiltonian)
    inputs = Inputs(
        structure=structure.identifier,
        hamiltonian=str(hamiltonian),
        coordinates=structure.coordinates,
        state=written,
        step=written_step,
        steps=steps,
        precision=precision,
        stages=stages,
        iterations=iterations,
    )
    with mpmath.workdps(precision):
        method = gauss(stages)
        prepared = [_prepared(component) for component in field.components]
        current = [
            _read(text, structure.coordinates[place])
            for place, text in enumerate(written)
        ]
        size = _read(written_step, "step")
        if size == 0:
            raise IntegratorRefused(
                "integrator.step-is-zero",
                "a step of zero advances nothing, so the run would report the "
                "initial condition back as a trajectory",
                "step",
            )
        states = [tuple(current)]
        settled = mpmath.mpf(0)
        used = 0
        for _ in range(steps):
            solved, passes, correction = _solve_stages(
                prepared, method, current, size, iterations
            )
            rates = [[_value(one, stage) for one in prepared] for stage in solved]
            following = []
            for place in range(len(current)):
                total = current[place]
                for row in range(method.stages):
                    total = total + size * method.weights[row] * rates[row][place]
                following.append(total)
            current = following
            states.append(tuple(current))
            if correction > settled:
                settled = correction
            used = max(used, passes)
    return Run(
        inputs=inputs,
        method=method,
        states=tuple(states),
        settled=settled,
        used=used,
    )


@dataclass(frozen=True)
class Drift:
    """How far one declared quantity moved over a run."""

    name: str
    expression: str
    initial: Number
    largest: Number

    @property
    def relative(self) -> Number:
        if self.initial == 0:
            return self.largest
        return self.largest / abs(self.initial)


def drift_of(
    structure: PoissonStructure, run: Run, quantity: sympy.Expr, name: str
) -> Drift:
    """The largest departure of one quantity from its initial value over a run.

    A measurement and not a verdict. What counts as a drift small enough to be
    noise is decided by comparing it with the Casimir floor from the same run,
    which is #32 and is deliberately not here: a number this module produced and
    then judged for itself would be a leg marking its own work.
    """
    with mpmath.workdps(run.inputs.precision):
        prepared = _prepared(_monomials(quantity, structure.coordinates, name))
        initial = _value(prepared, run.initial)
        largest = mpmath.mpf(0)
        for state in run.states:
            moved = abs(_value(prepared, state) - initial)
            if moved > largest:
                largest = moved
    return Drift(name=name, expression=str(quantity), initial=initial, largest=largest)


def casimir_drift(structure: PoissonStructure, run: Run) -> tuple[Drift, ...]:
    """The drift of every declared Casimir of the structure over the run.

    This is the noise floor 0007 measures a candidate against. The Casimirs are
    the structure's own declaration, checked by `casimir_failures` in
    findbuch.structures before anything integrates against them, so a floor
    taken here rests on a quantity that was proven to be conserved by the
    bracket rather than on one that was asserted to be.
    """
    return tuple(
        drift_of(structure, run, casimir.built, casimir.name)
        for casimir in structure.casimirs
    )
