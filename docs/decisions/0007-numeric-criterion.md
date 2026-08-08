# 0007. The numeric criterion, and why it carries no absolute tolerance

Decided in #8.

## The problem

The numeric leg is easy to write and easy to write uselessly.

The obvious implementation integrates a trajectory and checks that the
additional integral stays within some epsilon. The number chosen for epsilon
then decides every verdict, and there is no principled way to choose it. Too
loose and the leg passes a wrong row. Too tight and it fails a correct row on a
stiff parameter set. Worse, both failures look the same from outside, and the
leg ends up being loosened until it stops complaining, at which point it is
decoration.

There is a second problem underneath. An integrator that conserves quantities by
construction, which is what a symplectic or Lie-Poisson method is for, will keep
a wrong integral looking flat for a while too, because the error it makes is
bounded rather than absent. Flatness is evidence about the integrator as much as
about the integral.

## The decision

There is no absolute epsilon. No constant that somebody picked appears anywhere
in the verdict. The criterion is comparative and it is stated in two parts.

## The Casimir noise floor

First, the drift of the declared Casimirs is measured along the same trajectory.
They are conserved by construction on this structure, which is what the
structure test in 0002 establishes, so their drift is a direct measurement of
what the integrator is doing on this trajectory, at this precision, over this
length. That number is the noise floor for the run.

Second, the drift of the candidate integral is compared against that floor. A
row passes when the candidate's drift is of the same order as the floor. It
fails when the candidate drifts by orders of magnitude more, which means the
quantity is not conserved. That is a comparison between two measured numbers
rather than against a constant, and both numbers come out of the same run.

The floor is per run rather than per catalogue. A stiff parameter set raises the
floor and the comparison moves with it, which is the behaviour an absolute
tolerance cannot have.

## The raised precision control run

The comparison alone would still be arguable, so the answer is made honest by
running it twice.

The same trajectory, from the same initial condition, is integrated again at
raised working precision. A genuinely conserved quantity has its drift fall with
the precision, together with the floor, because what was being measured was the
integrator. A quantity that is not conserved has its drift stay where it was,
because the drift is real rather than numerical.

Reporting both runs is what separates the two, and reporting only one does not.
A single run that came out flat is consistent with a correct integral and with
an integrator that is quietly conserving the wrong thing, and nothing in that
run distinguishes them.

## What every reported number carries

Every number this leg reports carries the working precision, the step, the
length of the run, and the initial condition that produced it. Both runs are
reported, so the pair of precisions is visible rather than the conclusion drawn
from it.

That is the whole reproduction recipe: a reader with the row and those four
things gets the same number. A number reported without them is a claim about a
machine nobody else has.

## The integrator

An implicit method that respects the Lie-Poisson structure, at arbitrary
precision, rather than a general purpose adaptive solver.

The reason is the noise floor above. A method that does not respect the
structure lets the Casimirs wander, the floor rises to meet the signal, and the
comparison stops discriminating. At that point the leg passes everything and
looks like a leg that found nothing wrong.

Arbitrary precision rather than machine floats because the control run is the
second half of the criterion, and a fixed width has no second precision to raise
to.

## What proves it bites

A row with a deliberately wrong integral must fail this leg. A row whose
integral is correct but whose parameter conditions have been perturbed must also
fail, and that is the sharper of the two, because the formulas still look right.
Both are asserted as fixtures, and #33 is where they land, together with the
case that only the control run catches.

## Consequences

A verdict from this leg is not a proof. It is a measurement that failed to
contradict the row, at a stated precision over a stated length, and the report
says so in those words rather than reporting a passing row as verified. The
symbolic leg is where the exact statement is decided; this one catches what a
symbolic pass would not, and neither of them stands in for the other.
