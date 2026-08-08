# Coverage, gated and reported

Written for #54. The bar is on the code that decides whether a row is verified,
and everything else this project ships is measured and reported here rather than
gated. Which module is on which side, and why, is `tools/coverage_bar.py`, where
each placement carries its reason. This document does not repeat that list,
because a list in a document drifts against the thing that decides it.

The whole-codebase number is here rather than in a job's output alone, so that a
decision to leave something uncovered is visible over time instead of being
re-discovered by whoever next opens the report.

Run it:

    python tools/coverage_bar.py

## Read back on 2026-08-08, at 7d8164e9ac2b10ba69e35cc3e1e04c2bf2d128fc

The gated surface:

    Name                         Stmts   Miss Branch BrPart  Cover
    src/findbuch/validation.py     152     10     36      4    93%

Everything shipped:

    Name                              Stmts   Miss Branch BrPart  Cover
    src/findbuch/__init__.py              2      0      0      0   100%
    src/findbuch/invariants.py           67      2     20      1    97%
    src/findbuch/validation.py          152     10     36      4    93%
    tools/check_catalogue_format.py      29     29      8      0     0%
    tools/check_catalogue_schema.py      34     34     14      0     0%
    tools/check_interpreter.py           23     23      6      0     0%
    tools/check_invariants.py            46     46     24      0     0%
    tools/coverage_bar.py                48     34     10      1    26%
    tools/floor.py                       84     29     24      5    59%
    tools/gate.py                        84     59     26      1    24%
    TOTAL                               569    266    168     12    50%

## What those zeros are, and what they are not

The four runners at zero are executed by the suite on every run. They are
executed as SUBPROCESSES, which this measurement does not follow, so a runner
that the suite drives end to end reads here as one nothing has ever run. Reading
those rows as untested code would be wrong in the one direction that matters,
and reading them as tested would be wrong in the other: what the suite asserts
about them is their exit status and their output, never which of their branches
ran.

That is also the plainest argument for where the bar is. A whole-codebase bar
over the number above would be a bar over how much of this project happens to be
measurable in-process, which is a fact about the measurement rather than about
the code.

## What is uncovered on the gated surface

Ten statements and four partial branches in `src/findbuch/validation.py`. Two of
them decide something about a row and are worth naming here rather than leaving
in a report:

The refusal of an unparseable file, `toml.unparseable`, is never reached by the
suite. Nothing in `tests/` hands the loader a file that is not TOML, so the one
refusal that stands between a corrupt file and everything downstream is carried
by reading rather than by a test. The corpus of files that must be refused is
#22, and this entry is the case for putting a malformed file in it.

`validate_catalogue`, the walk over the whole catalogue directory, is never
called by the suite. It is three lines over an empty directory today, and it
becomes the path every row travels once #23 lands rows.

The rest are early returns on a field of the wrong type and the string form of a
refusal, and none of them changes a verdict.

Neither of the two is repaired by the change that wrote this section. The bar is
one topic and the tests that would close those two gaps are another, and a bar
landed together with the tests that make it pass proves neither.
