# 0001. The language and the toolchain

Decided in #2.

## The problem

Nothing can be built until the language and the toolchain are chosen, and the
choice cannot be carried over from another project out of habit. A means that
suited a different artefact is an assumption about this one.

## What this project is actually made of

Three things, and they pull in different directions.

A data format that a human writes by hand and a machine reads exactly.

A symbolic engine that has to decide, exactly rather than probably, whether a
rational expression in several body parameters is identically zero.

A numeric engine that has to integrate a trajectory accurately enough that the
drift of the additional integral says something about the integral rather than
about the integrator, which means arbitrary precision.

## The options, and the reason each one was rejected

Proprietary computer algebra, meaning Mathematica or Maple. The strongest
symbolic engines by a distance. Rejected, and not on price. A catalogue whose
verification cannot be re-run by an arbitrary reader is a catalogue whose
verification has to be taken on trust, which is the exact thing this project
exists to stop doing. A verdict nobody can reproduce is a claim.

Sage. Free, and the strongest free symbolic stack. Rejected on installation
weight: it is a distribution rather than a library, it is awkward to pin, and it
turns a contribution into an afternoon of setup.

C++ with GiNaC, or Maxima. Fast, exact, mature. Rejected on the plumbing. Most
of the work here is reading files, validating them, reporting and exporting, and
both of these are poor at that, which would mean a second language for the
plumbing and a second toolchain to maintain.

Julia, with Symbolics.jl and DifferentialEquations.jl. The best numeric side of
any candidate, including Lie-Poisson and symplectic integrators as library code,
plus a real symbolic layer. Genuinely close, and rejected on two grounds. The
symbolic layer is younger and its exact zero test over rational function fields
is less settled than the alternative. And the reviewer pool for this kind of
work is smaller, which matters for a catalogue whose whole claim is that people
can check it.

Rust or Go. No mature computer algebra in either. Building one is not this
project.

## The decision

Python 3, with SymPy for the symbolic leg and mpmath for the numeric leg, and
NumPy only where a fast path is genuinely needed and never in the path that
decides a verdict.

The reasons, in order of weight.

The verification has to be reproducible by a stranger with no license and no
unusual machine, and this is the stack a stranger already has.

The two legs share one runtime, so a case file is parsed once and the same
expression object feeds both the bracket computation and the numeric evaluation.
Nothing is transcribed across a language boundary, and a language boundary is
another place a transcription error could enter, in a project whose subject is
transcription errors.

mpmath is arbitrary precision in the same process, which is what makes the
raised precision control run of the numeric criterion possible at all.

The data plumbing, schema validation, reporting and export is ordinary work in
this language rather than a fight.

## What this costs, stated rather than hidden

Python cannot refuse much before it runs. Nothing about a type annotation stops
a bad value at the boundary. This is paid for by putting the refusals where they
can be executed instead: the schema refuses a malformed row, the loader refuses
an expression outside the declared grammar, and every refusal has a test that
proves it fires on a fixture that trips it and stays quiet on a fixture that
does not.

SymPy's general simplification is a heuristic and cannot be trusted to decide
that an expression is zero. This is not paid for by hoping. The symbolic
criterion is defined so that the question never reaches the heuristic, which is
0006 and its own decision.

Performance is worse than the C++ and Julia options by a wide margin. This is
acceptable because the full sweep is a batch job rather than something in
anyone's edit loop, and because the fast legs work on a subset that is chosen to
stay fast.

## Consequences

The layout of the tree, the shape of the project file and the pinning of the
interpreter all follow from this record rather than from preference, and #14 is
where they land.

Changing this decision later is not a substitution of one library for another.
The symbolic criterion, the numeric criterion and the parser boundary are all
written against what this stack can and cannot be trusted to do, so the record
that replaces this one replaces those with it.
