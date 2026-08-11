"""Report the drift of a structure's declared Casimirs over one run.

This is the noise floor of `docs/decisions/0007-numeric-criterion.md`, printed
on its own so that it can be read before anything is compared against it. It
reaches no verdict about a row and it is not a leg of `tools/gate.py`: the
comparison of a candidate integral's drift against this floor is #32, and the
sweep that runs it over the catalogue is #34.

WHY IT EXISTS SEPARATELY FROM THE SUITE. The suite decides that the floor is at
the working precision; a number is a different thing from a verdict, and #30
asks for the number with the command that produced it. Every run prints its own
reproducing command as its last line, so a number quoted anywhere else carries
the way to get it back.

The Hamiltonian arrives as a string and is read by `findbuch.expression`, the
same walk of a syntax tree every formula in every row goes through. Nothing here
hands a string to the library's parser, which is 0004's position and is refused
by name on this path.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import mpmath

from findbuch.expression import ExpressionRefused, SymbolTable, parse
from findbuch.integrator import IntegratorRefused, casimir_drift, integrate
from findbuch.structures import STRUCTURES, StructureRefused, load_all

# How many significant digits a reported number is printed to. It decides what
# a reader sees and nothing about what was computed; the run itself carries the
# working precision the caller asked for.
PRINTED_DIGITS = 8


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure the drift of the declared Casimirs over one run.",
    )
    parser.add_argument("--structures", type=Path, default=STRUCTURES)
    parser.add_argument("--structure", required=True)
    parser.add_argument("--hamiltonian", required=True)
    parser.add_argument("--state", required=True, nargs="+")
    parser.add_argument("--step", required=True)
    parser.add_argument("--steps", required=True, type=int)
    parser.add_argument("--precision", required=True, type=int)
    parser.add_argument("--stages", required=True, type=int)
    arguments = parser.parse_args(argv)

    try:
        loaded = load_all(arguments.structures)
    except StructureRefused as refused:
        print(f"drift: REFUSED, {refused}")
        return 1
    if arguments.structure not in loaded:
        print(
            f"drift: REFUSED, there is no structure '{arguments.structure}' in "
            f"{arguments.structures}. It holds: {', '.join(sorted(loaded))}"
        )
        return 1
    structure = loaded[arguments.structure]

    # No declared parameters. A trajectory is a statement about one point of the
    # parameter space, so the numbers are substituted before the run rather than
    # carried into it as symbols.
    symbols = SymbolTable.of(structure.coordinates, ())
    try:
        hamiltonian = parse(arguments.hamiltonian, symbols)
    except ExpressionRefused as refused:
        print(f"drift: REFUSED, {refused}")
        return 1

    try:
        run = integrate(
            structure,
            hamiltonian,
            arguments.state,
            arguments.step,
            arguments.steps,
            arguments.precision,
            arguments.stages,
        )
        drifts = casimir_drift(structure, run)
    except IntegratorRefused as refused:
        print(f"drift: REFUSED, {refused}")
        return 1

    print(f"drift: {structure.identifier}, {structure.name}")
    print(f"drift: H = {arguments.hamiltonian}")
    print(
        f"drift: {run.inputs.length}, {run.inputs.precision} digits, "
        f"{run.method.stages} stages, order {run.method.order}"
    )
    print(f"drift: from {' '.join(run.inputs.state)}")
    print(
        f"drift: the stage iteration settled at "
        f"{mpmath.nstr(run.settled, PRINTED_DIGITS)} after at most {run.used} passes"
    )
    for one in drifts:
        print(
            f"  {mpmath.nstr(one.largest, PRINTED_DIGITS):>18}  {one.name}"
            f"  (started at {mpmath.nstr(one.initial, PRINTED_DIGITS)},"
            f" relative {mpmath.nstr(one.relative, PRINTED_DIGITS)})"
        )
    print(
        "drift: these are measurements and not a verdict. What a drift this "
        "size means for a candidate integral is #32."
    )
    print(f"\n{run.inputs.command()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
