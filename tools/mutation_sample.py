"""Change the code that decides a verdict, and ask whether any test notices.

A checker that has stopped refusing looks exactly like a checker with nothing to
refuse. The refusal corpora in the tree cover the mistakes somebody thought of.
This covers the ones nobody thought of, by changing the checker rather than the
data: one token at a time, then the whole suite, then the question of whether
anything went red. A mutant that survives is a readable sentence rather than a
score. This line can be broken and the suite stays green.

WHERE THE SURFACE COMES FROM. tools/coverage_bar.py holds it, in
VERDICT_SURFACE, with the reason each module is on it. This file imports that
list rather than writing a second copy, for the reason #54 gives for the bar
itself: the surface is small today, the checker of #26 and #32 is not written
yet, and two lists of the modules that decide a verdict move apart in the same
silence a stale coverage gate does.

WHAT A MUTANT IS HERE. One token, swapped for one other token, in a table this
file holds. A comparison loosened or tightened, a boolean flipped, an arithmetic
sign turned round, a constant negated. Every candidate is parsed before it is
admitted, so a swap that only produces a syntax error is not counted as a mutant
that nothing killed. `for x in y` widened to `for x not in y` is the common one
and there are eighty-six of them on this surface.

THE CANDIDATE IS PARSED AND NOT HANDED TO THE BYTECODE COMPILER.
`library-parser-off-the-loading-path` refuses that call on a shipped path, in
the same breath as `eval` and `exec`, and it refused the first draft of this
file. `ast.parse` answers the only question being asked, which is whether the
bytes are a Python file, and it is what src/findbuch/expression.py uses for the
same reason. The spelling itself is elided from this paragraph because the
pattern would refuse the sentence describing it, which the same rule has already
done once in this repository's history.

WHAT IS DELIBERATELY NOT MUTATED, so a green run is not read as more than it is.
String literals, including the refusal identifiers. A changed identifier is
refused by the corpus test at once, which makes it a mutant that dies for a
reason nobody had to think about, and a hundred of them would crowd out the
sample. Statement deletion, loop bounds and call arguments are not in the table
either; they need a rewriter rather than a token swap, and a token swap is what
this file can prove it does correctly.

WHAT A SAMPLE CANNOT SAY. It says nothing about the mutants it did not run, and
a green check whose sample was eight of a hundred and ninety-one is a statement
about eight.
Every run prints the population, the sample and the difference, and the
difference is the number that keeps a partial run from reading as a complete
one. The full run is `--all` and is not on a pull request, because a gate a
contributor cannot wait for is a gate that gets worked around.

WHAT A SURVIVOR IS NOT. It is not always a missing test. Some mutants are
equivalent to the code they replace and no test can kill them; that is a
property of mutation testing rather than of this suite. That is why a survivor
is either killed by a test or entered in ACCEPTED_SURVIVORS with the reason,
and why an accepted entry that stops surviving is refused as loudly as a
survivor that was never accepted. A register that only fails in one direction
accumulates entries nobody rechecks.

THE SEED REPRODUCES A RUN AGAINST ONE TREE. The population is derived from the
source, so the same seed over a changed surface is a different sample. Reproduce
a run at the commit it ran on, and the printed command says which that was.

This is not a leg of tools/gate.py, for the reason tools/coverage_bar.py is not
one: it runs the whole suite once per mutant, so a default gate carrying it
would make a contributor wait through the suite once for every mutant in the
sample. It is a job on a pull request and a command a contributor runs directly.
"""

from __future__ import annotations

import argparse
import ast
import io
import random
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO_ROOT / "tools"))

import coverage_bar  # noqa: E402

# One token for one token. Both directions are present where both are
# meaningful, because a table that only loosens comparisons tests only the
# guards that were written the tight way round.
#
# `is` and `in` widen to two tokens rather than swapping for one. That is still
# a single edit at a single position and the compile check below keeps the
# result honest.
SWAPS: dict[str, str] = {
    "<": "<=",
    "<=": "<",
    ">": ">=",
    ">=": ">",
    "==": "!=",
    "!=": "==",
    "+": "-",
    "-": "+",
    "*": "/",
    "/": "*",
    "//": "/",
    "%": "*",
    "+=": "-=",
    "-=": "+=",
    "*=": "/=",
    "and": "or",
    "or": "and",
    "True": "False",
    "False": "True",
    "is": "is not",
    "in": "not in",
}

# Survivors that are accepted rather than killed, each with the reason. The key
# is the module, the stripped text of the line the token sits on, and the swap,
# which is what stays put when a line moves. An entry is checked in both
# directions by the run below: one that no longer describes a mutant in the
# population is refused as dangling, and one whose mutant the sample killed is
# refused as stale.
ACCEPTED_SURVIVORS: dict[tuple[str, str, str, str], str] = {}

# How many mutants a run takes when nobody says.
#
# WHY THIS VALUE. A killed mutant costs a fraction of a suite run, because the
# suite stops at the first failure. A survivor costs a whole one. So the worst
# case for the job is the run with the most to report, and a size chosen off the
# average would time out exactly then.
#
# Measured rather than guessed, on the branch this landed on:
#
#     python tools/run_tests.py -q
#     279 passed, 805 subtests passed in 104.26s
#
# Eight survivors at that is about a quarter of an hour, inside the thirty
# minute job in .github/workflows/mutation.yml with the install ahead of it and
# room for a runner slower than the machine that number came from. Raising this
# is a change to this number with its own measurement beside it, and the
# workflow reads it from here rather than writing it down again.
SAMPLE = 8

# The seed, so that a run reproduces without anybody having to pass one. It is
# printed with every result and it is an argument, because a sample that can
# only ever be one sample stops finding anything after the first time it is run.
SEED = 55

# A mutant can turn a bounded loop into an unbounded one, and a suite that hangs
# reports nothing at all. This is the wall a hang meets. It is generous against
# the whole suite rather than tight, because a timeout that fires on a slow
# machine turns a survivor into a kill and reports the opposite of the truth.
TIMEOUT_SECONDS = 600

KILLED = "KILLED"
SURVIVED = "SURVIVED"
TIMED_OUT = "TIMED OUT"


@dataclass(frozen=True, order=True)
class Mutant:
    """One token swapped for one other, at one position in one module."""

    module: str
    line: int
    column: int
    before: str
    after: str
    line_text: str

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.module, self.line_text, self.before, self.after)

    def describe(self) -> str:
        return (
            f"{self.module}:{self.line}:{self.column + 1}  "
            f"{self.before!r} -> {self.after!r}\n      {self.line_text}"
        )


def spliced(source: str, mutant: Mutant) -> str:
    """The source with this one mutant in it and every other byte untouched."""
    lines = source.splitlines(keepends=True)
    line = lines[mutant.line - 1]
    start, stop = mutant.column, mutant.column + len(mutant.before)
    lines[mutant.line - 1] = line[:start] + mutant.after + line[stop:]
    return "".join(lines)


def mutants_in(source: str, module: str) -> list[Mutant]:
    """Every admissible one-token mutant of this source, in a fixed order.

    Tokenising rather than walking a syntax tree is what keeps the mutant a
    splice into the original bytes: everything the mutant does not touch stays
    byte for byte what it was, so a survivor's line is quotable as the line the
    author wrote. The cost is that a token carries no grammar with it, and it is
    paid by compiling every candidate before admitting it.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, SyntaxError):
        return []

    lines = source.splitlines()
    found: list[Mutant] = []
    for index, token in enumerate(tokens):
        if token.type not in (tokenize.OP, tokenize.NAME):
            continue
        after = SWAPS.get(token.string)
        if after is None:
            continue
        # `x is not y` tokenises as `is` then `not`, and `x not in y` as `not`
        # then `in`. Widening either half of a spelling that is already the
        # negative one produces a double negative that reads as a mutant and is
        # not the one the table names.
        following = tokens[index + 1].string if index + 1 < len(tokens) else ""
        preceding = tokens[index - 1].string if index else ""
        if token.string == "is" and following == "not":
            continue
        if token.string == "in" and preceding == "not":
            continue

        line, column = token.start
        found.append(
            Mutant(
                module=module,
                line=line,
                column=column,
                before=token.string,
                after=after,
                line_text=lines[line - 1].strip(),
            )
        )

    admitted: list[Mutant] = []
    for mutant in found:
        candidate = spliced(source, mutant)
        try:
            ast.parse(candidate, module)
        except SyntaxError:
            continue
        admitted.append(mutant)
    return sorted(admitted)


def population(root: Path, modules: list[str]) -> list[Mutant]:
    found: list[Mutant] = []
    for module in sorted(modules):
        path = root / module
        if not path.is_file():
            continue
        found.extend(mutants_in(path.read_text(encoding="utf-8"), module))
    return sorted(found)


def chosen(candidates: list[Mutant], seed: int, size: int | None) -> list[Mutant]:
    if size is None or size >= len(candidates):
        return list(candidates)
    return sorted(random.Random(seed).sample(candidates, size))


def run_one(
    root: Path, mutant: Mutant, suite: list[str], timeout: int
) -> tuple[str, str]:
    """Put the mutant in the tree, run the suite, and put the tree back.

    The module is written in place rather than into a copy, because the suite
    reads the checkout: it asks git which files are tracked, it imports the
    package that was installed from this tree, and it reads the workflow files
    by path. A copy would fail every one of those for reasons that have nothing
    to do with the mutant.

    The original bytes are held here and restored in a finally, and the caller
    checks the whole surface afterwards rather than trusting that this happened.
    """
    path = root / mutant.module
    original = path.read_bytes()
    outcome: str
    detail: str
    try:
        mutated = spliced(original.decode("utf-8"), mutant)
        path.write_bytes(mutated.encode("utf-8"))
        try:
            completed = subprocess.run(
                suite,
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return TIMED_OUT, f"the suite did not finish inside {timeout}s"
        if completed.returncode == 0:
            outcome, detail = SURVIVED, "the suite passed with this mutant in place"
        else:
            first = _first_failure(completed.stdout + completed.stderr)
            outcome, detail = KILLED, first
    finally:
        path.write_bytes(original)
    return outcome, detail


def _first_failure(output: str) -> str:
    """The name of the first test that went red, out of the suite's own summary.

    `SUBFAILED(` is in the list because a case that failed inside a subTest is
    reported under that spelling and not as `FAILED`, and a kill whose reason
    reads "named no failing test" is a kill nobody can act on. Three of this
    tree's own guards report through subtests.
    """
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith(("FAILED ", "ERROR ", "SUBFAILED(")):
            return stripped
    return "the suite exited non-zero and named no failing test"


def _modules_that_moved(root: Path, before: dict[str, bytes]) -> list[str]:
    return sorted(
        module
        for module, content in before.items()
        if (root / module).read_bytes() != content
    )


def report(
    results: list[tuple[Mutant, str, str]],
    total: int,
    seed: int,
) -> int:
    """Print every mutant that was run, then decide.

    The survivors are printed one by one rather than counted. A score with no
    list behind it is a number nobody can act on, and the list is the whole
    output of the exercise.
    """
    survivors = [(m, d) for m, outcome, d in results if outcome == SURVIVED]
    killed = [m for m, outcome, _ in results if outcome == KILLED]
    timed_out = [(m, d) for m, outcome, d in results if outcome == TIMED_OUT]

    print(f"\nmutation: {len(results)} of {total} mutant(s) run, seed {seed}")
    print(
        f"mutation: {total - len(results)} mutant(s) were NOT run, and this run "
        f"says nothing about them"
    )
    print(f"mutation: {len(killed)} killed, {len(survivors)} survived")

    accepted: list[tuple[Mutant, str]] = []
    unaccepted: list[tuple[Mutant, str]] = []
    for mutant, detail in survivors:
        reason = ACCEPTED_SURVIVORS.get(mutant.key)
        (accepted if reason is not None else unaccepted).append((mutant, detail))

    for mutant, _ in accepted:
        print(f"\n  ACCEPTED SURVIVOR  {mutant.describe()}")
        print(f"      {ACCEPTED_SURVIVORS[mutant.key]}")
    for mutant, detail in unaccepted:
        print(f"\n  SURVIVOR  {mutant.describe()}")
        print(f"      {detail}")
    for mutant, detail in timed_out:
        print(f"\n  TIMED OUT  {mutant.describe()}")
        print(f"      {detail}")

    # A register that only fails when something is missing from it fills up with
    # entries nobody rechecks. An accepted survivor the sample killed is a debt
    # that has been paid, and the entry has to go.
    stale = [m for m in killed if m.key in ACCEPTED_SURVIVORS]
    for mutant in stale:
        print(f"\n  STALE ACCEPTANCE  {mutant.describe()}")
        print("      a test kills this mutant now; remove it from ACCEPTED_SURVIVORS")

    if unaccepted or timed_out or stale:
        print(
            f"\nmutation: REFUSED. {len(unaccepted)} survivor(s) nothing killed, "
            f"{len(timed_out)} that never finished, {len(stale)} acceptance(s) "
            f"that no longer describe a survivor. Kill a survivor with a test, "
            f"or enter it in ACCEPTED_SURVIVORS in tools/mutation_sample.py with "
            f"the reason no test can."
        )
        return 1
    print("\nmutation: every mutant in this sample was killed by the suite")
    return 0


def dangling_acceptances(candidates: list[Mutant]) -> list[tuple[str, str, str, str]]:
    live = {mutant.key for mutant in candidates}
    return sorted(key for key in ACCEPTED_SURVIVORS if key not in live)


def run(
    root: Path,
    modules: list[str],
    suite: list[str],
    seed: int,
    size: int | None,
    timeout: int,
) -> int:
    candidates = population(root, modules)
    print(f"mutation: the surface is {len(modules)} module(s)")
    for module in sorted(modules):
        print(f"  {module}")

    # An empty population is the way this check stops checking without any name
    # moving: a surface that stopped being read and a surface with nothing to
    # mutate print the same zero, so neither is allowed to pass.
    if not candidates:
        print(
            "\nmutation: REFUSED, no mutant was derived from the surface. Either "
            "the modules were not read or the table in SWAPS matches nothing in "
            "them, and a run over no mutant is not a run that found nothing."
        )
        return 1

    dangling = dangling_acceptances(candidates)
    if dangling:
        for key in dangling:
            print(f"\n  DANGLING ACCEPTANCE  {key[0]}  {key[2]!r} -> {key[3]!r}")
            print(f"      {key[1]}")
        print(
            "\nmutation: REFUSED, an entry in ACCEPTED_SURVIVORS describes no "
            "mutant of this tree, so the register names code that is not here."
        )
        return 1

    running = chosen(candidates, seed, size)
    print(f"\nmutation: {len(candidates)} mutant(s) derived, running {len(running)}")

    before = {module: (root / module).read_bytes() for module in modules}
    results: list[tuple[Mutant, str, str]] = []
    for index, mutant in enumerate(running, start=1):
        print(f"\n[{index}/{len(running)}] {mutant.describe()}", flush=True)
        outcome, detail = run_one(root, mutant, suite, timeout)
        print(f"      {outcome}: {detail}", flush=True)
        results.append((mutant, outcome, detail))

    # Read back rather than assumed. The tool edits the tree it is checking, and
    # a restore that silently failed would leave a mutant on the branch and a
    # report saying it was killed.
    changed = _modules_that_moved(root, before)
    if changed:
        print(f"\nmutation: REFUSED, the surface was not restored: {changed}")
        return 1
    print("\nmutation: the surface was read back and is byte for byte what it was")

    return report(results, len(candidates), seed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mutate the verdict path and ask whether any test notices."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--module",
        action="append",
        metavar="PATH",
        help="mutate this module instead of the verdict path; repeatable",
    )
    parser.add_argument(
        "--suite",
        metavar="COMMAND",
        help="the command whose exit status decides a mutant, as one string",
    )
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--sample",
        type=int,
        default=SAMPLE,
        metavar="N",
        help=f"how many mutants to run; the default is {SAMPLE}",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="run every mutant; this is the on-demand run and it is slow",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the population and stop, without running anything",
    )
    parser.add_argument("--timeout", type=int, default=TIMEOUT_SECONDS)
    arguments = parser.parse_args(argv)

    modules = arguments.module or sorted(coverage_bar.VERDICT_SURFACE)
    suite = (
        arguments.suite.split()
        if arguments.suite
        else [sys.executable, "tools/run_tests.py", "-x", "-q"]
    )

    if arguments.list:
        candidates = population(arguments.root, modules)
        for mutant in candidates:
            print(mutant.describe())
        print(f"\nmutation: {len(candidates)} mutant(s)")
        return 0 if candidates else 1

    return run(
        root=arguments.root,
        modules=modules,
        suite=suite,
        seed=arguments.seed,
        size=None if arguments.all else arguments.sample,
        timeout=arguments.timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
