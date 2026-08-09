"""The integrator is correct, decided separately from any question about a row.

#30 asks for three properties and this file is all three, each stated over every
structure in `structures/` rather than over one of them. A method that is right
on e(3) and wrong on so(4) is a plausible thing to write, because the two differ
in one coefficient of the bracket and nothing in an integrator mentions that
coefficient.

WHAT MAKES THE CLOSED-FORM TEST BITE. The case is the flow of `g3`, whose
solution is known on all three structures and is a DIFFERENT function on each:
straight lines where kappa is zero, circles where it is one, hyperbolae where it
is minus one. So the test refuses a trajectory computed against the wrong
bracket, and `TheClosedFormTellsTheThreeStructuresApart` runs exactly that,
because a comparison that would pass against any of the three would be proving
that the integrator moves rather than that it moves correctly.

WHAT "TO THE WORKING PRECISION" MEANS HERE, since a fixed-order method cannot
reach it and this one is not fixed-order. A Gauss collocation method of s stages
has order 2s, so the stage count is chosen against the precision until the
method error is below the last digit and what is left is round-off. The
closed-form case below runs eight stages, order sixteen, over eight steps at
thirty digits, and the agreement is the working precision less the round-off
this suite reports as `AGREEMENT_GIVEN_UP_TO_ROUND_OFF`. That number is a
property of accumulated arithmetic and not a threshold anybody chose to be
comfortable with; the runs print their own worst departure and it is orders
below what is asserted.
"""

import unittest

import mpmath
import sympy

from findbuch import integrator
from findbuch.structures import STRUCTURES, PoissonStructure, load_all

STRUCTURE = load_all(STRUCTURES)

NAMES = ("M1", "M2", "M3", "g1", "g2", "g3")
M1, M2, M3, G1, G2, G3 = sympy.symbols(NAMES)

# A heavy body with three distinct moments and a gravity term: a genuinely
# nonlinear flow, and not the linear case the closed form below is about.
HEAVY = M1**2 / 2 + M2**2 / 3 + M3**2 / 5 + G1

# Nothing symmetric, nothing zero, nothing equal to anything else. A state with a
# zero in it passes a bracket that has dropped a term.
START = ("0.3", "-0.7", "1.1", "0.5", "0.2", "-0.9")

# How many digits of the working precision a run is asked to agree to. The gap
# is accumulated round-off over the run and the stage iteration, and the runs
# report their own departure, which is smaller than this by several orders.
AGREEMENT_GIVEN_UP_TO_ROUND_OFF = 4


def departure(precision: int, digits: int) -> mpmath.mpf:
    return mpmath.mpf(10) ** -(precision - digits)


def closed_form(
    structure: PoissonStructure, start: list[mpmath.mpf], time: mpmath.mpf
) -> tuple[mpmath.mpf, ...]:
    """The flow of `g3`, solved by hand, on whichever member of the family this is.

    dM1/dt = -g2, dM2/dt = g1, dg1/dt = -kappa M2, dg2/dt = kappa M1, with M3
    and g3 constant. Writing u = M1 + i M2 and v = g1 + i g2 turns it into
    u' = i v and v' = i kappa u, so u'' = -kappa u, and the three members of the
    family give the three solutions of that equation.
    """
    m1, m2, m3, x1, x2, x3 = start
    kappa = structure.parameter_value
    if kappa == 0:
        return (m1 - x2 * time, m2 + x1 * time, m3, x1, x2, x3)
    if kappa == 1:
        turn, rise = mpmath.cos(time), mpmath.sin(time)
        sign = 1
    else:
        turn, rise = mpmath.cosh(time), mpmath.sinh(time)
        sign = -1
    return (
        m1 * turn - x2 * rise,
        m2 * turn + x1 * rise,
        m3,
        x1 * turn - sign * m2 * rise,
        x2 * turn + sign * m1 * rise,
        x3,
    )


def worst(left: tuple[mpmath.mpf, ...], right: tuple[mpmath.mpf, ...]) -> mpmath.mpf:
    return max(abs(one - other) for one, other in zip(left, right, strict=True))


class TheStructuresUnderTestAreTheOnesInTheTree(unittest.TestCase):
    """The three properties are stated over every structure, so count them here."""

    def test_three_structures_are_loaded_and_they_differ_in_the_parameter(self) -> None:
        self.assertEqual(sorted(STRUCTURE), ["e3", "so31", "so4"])
        self.assertEqual(
            sorted(one.parameter_value for one in STRUCTURE.values()), [-1, 0, 1]
        )


class TheTableauIsBuiltRatherThanQuoted(unittest.TestCase):
    """Every property the method rests on, decided on the tableau it computed."""

    def test_the_quadrature_is_exact_to_twice_the_stage_count(self) -> None:
        for stages in (1, 2, 3, 5, 8):
            with mpmath.workdps(30), self.subTest(stages=stages):
                method = integrator.gauss(stages)
                self.assertEqual(method.order, 2 * stages)
                for power in range(1, method.order + 1):
                    total = sum(
                        weight * node ** (power - 1)
                        for weight, node in zip(
                            method.weights, method.nodes, strict=True
                        )
                    )
                    self.assertLess(
                        abs(total - mpmath.mpf(1) / power),
                        departure(30, AGREEMENT_GIVEN_UP_TO_ROUND_OFF),
                        f"the quadrature is not exact on x^{power - 1}, so this "
                        f"tableau is not the {stages}-stage Gauss one",
                    )

    def test_the_relation_that_conserves_a_quadratic_invariant_holds(self) -> None:
        for stages in (1, 2, 3, 5, 8):
            with mpmath.workdps(30), self.subTest(stages=stages):
                self.assertEqual(
                    integrator.symplecticity_failures(integrator.gauss(stages)), []
                )

    def test_one_perturbed_entry_is_reported_by_that_same_relation(self) -> None:
        """The guard, deleted. A relation nothing can fail decides nothing."""
        with mpmath.workdps(30):
            method = integrator.gauss(3)
            rows = [list(row) for row in method.matrix]
            rows[0][1] = rows[0][1] + mpmath.mpf(1) / 1000
            perturbed = integrator.Method(
                stages=method.stages,
                precision=method.precision,
                nodes=method.nodes,
                weights=method.weights,
                matrix=tuple(tuple(row) for row in rows),
            )
            failures = integrator.symplecticity_failures(perturbed)
        self.assertNotEqual(failures, [])
        self.assertIn("b0 a01 + b1 a10 - b0 b1", failures[0])

    def test_a_method_with_no_stage_is_refused_by_identifier(self) -> None:
        with self.assertRaises(integrator.IntegratorRefused) as refused:
            integrator.gauss(0)
        self.assertEqual(refused.exception.code, "integrator.stages-below-one")


class TheTrajectoryMatchesAKnownClosedForm(unittest.TestCase):
    """Property one of #30, on every structure."""

    precision = 30
    stages = 8
    step = "0.125"
    steps = 8

    def run_it(self, structure: PoissonStructure) -> integrator.Run:
        return integrator.integrate(
            structure, G3, START, self.step, self.steps, self.precision, self.stages
        )

    def test_every_structure_reproduces_its_own_solution(self) -> None:
        for identifier, structure in sorted(STRUCTURE.items()):
            with self.subTest(structure=identifier):
                produced = self.run_it(structure)
                with mpmath.workdps(self.precision):
                    start = [mpmath.mpf(text) for text in START]
                    hand = closed_form(structure, start, mpmath.mpf(1))
                    departed = worst(produced.final, hand)
                self.assertLess(
                    departed,
                    departure(self.precision, AGREEMENT_GIVEN_UP_TO_ROUND_OFF),
                    f"{identifier} departed from its closed form by {departed}",
                )


class TheClosedFormTellsTheThreeStructuresApart(unittest.TestCase):
    """The neighbour half. Without it the comparison above proves nothing."""

    def test_a_trajectory_from_one_structure_fails_the_others_closed_form(self) -> None:
        precision = 30
        run = integrator.integrate(STRUCTURE["e3"], G3, START, "0.125", 8, precision, 8)
        for identifier in ("so4", "so31"):
            with self.subTest(against=identifier):
                with mpmath.workdps(precision):
                    start = [mpmath.mpf(text) for text in START]
                    hand = closed_form(STRUCTURE[identifier], start, mpmath.mpf(1))
                    departed = worst(run.final, hand)
                self.assertGreater(
                    departed,
                    departure(precision, AGREEMENT_GIVEN_UP_TO_ROUND_OFF),
                    f"the e3 trajectory satisfies {identifier}'s closed form, so "
                    f"the comparison is not reading the bracket at all",
                )


class TheDeclaredCasimirsStayPutOverALongRun(unittest.TestCase):
    """Property two of #30, and the floor 0007 measures a candidate against."""

    precision = 25
    stages = 2
    step = "0.125"
    steps = 100

    def test_every_casimir_of_every_structure_holds_to_the_working_precision(
        self,
    ) -> None:
        for identifier, structure in sorted(STRUCTURE.items()):
            with self.subTest(structure=identifier):
                run = integrator.integrate(
                    structure,
                    HEAVY,
                    START,
                    self.step,
                    self.steps,
                    self.precision,
                    self.stages,
                )
                drifts = integrator.casimir_drift(structure, run)
                self.assertEqual(len(drifts), len(structure.casimirs))
                for one in drifts:
                    self.assertLess(
                        one.largest,
                        departure(self.precision, AGREEMENT_GIVEN_UP_TO_ROUND_OFF),
                        f"{identifier}: '{one.name}' moved by {one.largest} over "
                        f"{self.steps} steps, so the noise floor is being set by "
                        f"the method rather than by the arithmetic",
                    )

    def test_a_quantity_that_is_not_conserved_moves_and_is_measured_moving(
        self,
    ) -> None:
        """The neighbour. A drift measurement that returns zero for everything
        would pass the assertion above and mean nothing."""
        structure = STRUCTURE["e3"]
        run = integrator.integrate(
            structure, HEAVY, START, self.step, self.steps, self.precision, self.stages
        )
        moving = integrator.drift_of(structure, run, M1, "M1 on its own")
        self.assertGreater(moving.largest, departure(self.precision, 20))


class ReversingTheStepReturnsToTheInitialCondition(unittest.TestCase):
    """Property three of #30, which #30 names as the one the other two miss."""

    precision = 25
    stages = 3
    steps = 40

    def test_forward_then_backward_returns_to_where_it_started(self) -> None:
        for identifier, structure in sorted(STRUCTURE.items()):
            with self.subTest(structure=identifier):
                forward = integrator.integrate(
                    structure,
                    HEAVY,
                    START,
                    "0.125",
                    self.steps,
                    self.precision,
                    self.stages,
                )
                backward = integrator.integrate(
                    structure,
                    HEAVY,
                    forward.written(forward.final),
                    "-0.125",
                    self.steps,
                    self.precision,
                    self.stages,
                )
                with mpmath.workdps(self.precision):
                    start = tuple(mpmath.mpf(text) for text in START)
                    departed = worst(backward.final, start)
                self.assertLess(
                    departed,
                    departure(self.precision, AGREEMENT_GIVEN_UP_TO_ROUND_OFF),
                    f"{identifier} came back {departed} away from where it began",
                )

    def test_the_forward_run_went_somewhere_first(self) -> None:
        """Otherwise a method that never moves passes the reversal above."""
        structure = STRUCTURE["e3"]
        forward = integrator.integrate(
            structure, HEAVY, START, "0.125", self.steps, self.precision, self.stages
        )
        with mpmath.workdps(self.precision):
            start = tuple(mpmath.mpf(text) for text in START)
            self.assertGreater(worst(forward.final, start), mpmath.mpf(1) / 10)


class TheDriftFallsWhenThePrecisionIsRaised(unittest.TestCase):
    """What makes the control run of #32 able to say anything at all.

    A Gauss method conserves a quadratic Casimir exactly, so what is left is
    round-off, and round-off is what moves when the precision moves. If it did
    not move, the raised-precision run would be a second copy of the first and
    the control could not tell a conserved quantity from a well-behaved one.
    """

    def largest(self, precision: int) -> mpmath.mpf:
        structure = STRUCTURE["so31"]
        run = integrator.integrate(structure, HEAVY, START, "0.125", 50, precision, 2)
        return max(one.largest for one in integrator.casimir_drift(structure, run))

    def test_fifteen_more_digits_lower_the_floor(self) -> None:
        lower = self.largest(25)
        raised = self.largest(40)
        self.assertLess(
            raised,
            lower,
            f"the Casimir drift did not fall when the precision rose: {lower} "
            f"at 25 digits and {raised} at 40",
        )
        self.assertLess(raised, departure(40, AGREEMENT_GIVEN_UP_TO_ROUND_OFF))


class AStateSurvivesBeingWrittenDown(unittest.TestCase):
    """The record is text, so text has to read back as the same number."""

    def test_the_written_state_reads_back_unchanged(self) -> None:
        structure = STRUCTURE["so4"]
        run = integrator.integrate(structure, HEAVY, START, "0.125", 3, 25, 2)
        written = run.written(run.final)
        with mpmath.workdps(25):
            self.assertEqual(tuple(mpmath.mpf(text) for text in written), run.final)

    def test_the_record_prints_the_command_that_reproduces_the_run(self) -> None:
        structure = STRUCTURE["e3"]
        run = integrator.integrate(structure, HEAVY, START, "0.125", 2, 20, 2)
        printed = run.inputs.command()
        for part in ("--structure e3", "--step 0.125", "--precision 20", "--stages 2"):
            self.assertIn(part, printed)
        self.assertEqual(run.inputs.length, "2 steps of 0.125")


class ARunIsRefusedByIdentifierRatherThanReportedWrong(unittest.TestCase):
    """Each refusal with the identifier it carries, and its one-change neighbour."""

    def refusal(self, **changed: object) -> str:
        asked: dict[str, object] = {
            "structure": STRUCTURE["e3"],
            "hamiltonian": HEAVY,
            "state": START,
            "step": "0.125",
            "steps": 2,
            "precision": 20,
            "stages": 2,
        }
        asked.update(changed)
        with self.assertRaises(integrator.IntegratorRefused) as refused:
            integrator.integrate(**asked)  # type: ignore[arg-type]
        return refused.exception.code

    def test_the_neighbour_every_case_below_is_one_change_from_is_accepted(
        self,
    ) -> None:
        run = integrator.integrate(STRUCTURE["e3"], HEAVY, START, "0.125", 2, 20, 2)
        self.assertEqual(len(run.states), 3)

    def test_a_float_step_is_refused_because_it_is_not_what_was_written(self) -> None:
        self.assertEqual(
            self.refusal(step=0.125), "integrator.number-is-not-written-exactly"
        )

    def test_a_float_in_the_state_is_refused_the_same_way(self) -> None:
        self.assertEqual(
            self.refusal(state=("0.3", "-0.7", "1.1", "0.5", "0.2", -0.9)),
            "integrator.number-is-not-written-exactly",
        )

    def test_text_that_is_not_a_number_is_refused(self) -> None:
        self.assertEqual(
            self.refusal(step="an eighth"), "integrator.number-is-unreadable"
        )

    def test_a_step_of_zero_is_refused(self) -> None:
        self.assertEqual(self.refusal(step="0"), "integrator.step-is-zero")

    def test_a_state_of_the_wrong_width_is_refused(self) -> None:
        self.assertEqual(
            self.refusal(state=("0.3", "-0.7", "1.1")),
            "integrator.state-does-not-match-the-structure",
        )

    def test_a_precision_below_one_digit_is_refused(self) -> None:
        self.assertEqual(self.refusal(precision=0), "integrator.precision-below-one")

    def test_a_run_of_no_steps_is_refused(self) -> None:
        self.assertEqual(self.refusal(steps=0), "integrator.steps-below-one")

    def test_a_hamiltonian_naming_a_parameter_is_refused(self) -> None:
        self.assertEqual(
            self.refusal(hamiltonian=sympy.Symbol("A") * M1**2),
            "integrator.expression-names-a-stranger",
        )

    def test_a_hamiltonian_that_is_only_a_parameter_is_refused_as_well(self) -> None:
        """Its brackets are all zero, so nothing downstream would have noticed."""
        self.assertEqual(
            self.refusal(hamiltonian=sympy.Symbol("A")),
            "integrator.expression-names-a-stranger",
        )

    def test_a_hamiltonian_that_is_not_a_polynomial_is_refused(self) -> None:
        self.assertEqual(
            self.refusal(hamiltonian=1 / M1), "integrator.expression-is-not-polynomial"
        )

    def test_a_coefficient_that_is_not_rational_is_refused(self) -> None:
        self.assertEqual(
            self.refusal(hamiltonian=sympy.sqrt(2) * M1**2),
            "integrator.coefficient-is-not-rational",
        )

    def test_a_step_too_long_for_the_field_is_refused_as_diverging(self) -> None:
        self.assertEqual(self.refusal(step="40"), "integrator.stage-iteration-diverges")

    def test_an_iteration_cut_short_is_refused_rather_than_reported(self) -> None:
        with self.assertRaises(integrator.IntegratorRefused) as refused:
            integrator.integrate(
                STRUCTURE["e3"],
                HEAVY,
                START,
                "0.125",
                2,
                20,
                2,
                iterations=1,
            )
        self.assertEqual(
            refused.exception.code, "integrator.stage-iteration-did-not-settle"
        )


class ADriftMeasurementRefusesAQuantityItCannotRead(unittest.TestCase):
    """The measurement takes an expression too, so it refuses on the same terms."""

    def test_a_quantity_naming_a_stranger_is_refused(self) -> None:
        structure = STRUCTURE["e3"]
        run = integrator.integrate(structure, HEAVY, START, "0.125", 2, 20, 2)
        with self.assertRaises(integrator.IntegratorRefused) as refused:
            integrator.drift_of(structure, run, sympy.Symbol("A") * M1, "a stranger")
        self.assertEqual(
            refused.exception.code, "integrator.expression-names-a-stranger"
        )

    def test_a_casimir_that_starts_at_zero_reports_its_absolute_movement(self) -> None:
        structure = STRUCTURE["e3"]
        start = ("1", "0", "0", "0", "1", "0")
        run = integrator.integrate(structure, HEAVY, start, "0.125", 4, 20, 2)
        measured = integrator.drift_of(structure, run, M1 * G1 + M2 * G2 + M3 * G3, "z")
        self.assertEqual(measured.initial, 0)
        self.assertEqual(measured.relative, measured.largest)

    def test_a_quantity_that_starts_somewhere_reports_movement_against_it(self) -> None:
        structure = STRUCTURE["e3"]
        run = integrator.integrate(structure, HEAVY, START, "0.125", 4, 20, 2)
        measured = integrator.drift_of(structure, run, M1, "M1 on its own")
        with mpmath.workdps(20):
            self.assertEqual(
                measured.relative, measured.largest / abs(measured.initial)
            )


if __name__ == "__main__":
    unittest.main()
