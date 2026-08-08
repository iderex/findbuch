"""The invariants of this repository that a pattern can decide, and their scan.

An invariant here is a property that is decided by reading the source rather
than by running it. That is a narrow class and it is worth being exact about
why any of it is in the tree.

Three of the properties below were decided in a record and then left standing on
memory. `docs/decisions/0004-expression-grammar.md` says the library's
convenience parser is not called from the loading path. `0006` says the general
simplification routine is not in the verdict path. `0007` says no absolute
tolerance appears in a verdict. Each of those is a sentence somebody has to
remember at the moment they are in a hurry, which is the moment they will not.
Making them greppable turns each one into a refusal.

WHAT A PATTERN CAN AND CANNOT DECIDE, because the difference decides how much
weight these carry. A pattern decides that a spelling is absent from a file. It
does not decide that the property holds. A call reached through an alias, an
attribute looked up by name, or a routine imported under another name passes
every rule here. So this is a floor: it catches the reintroduction somebody
writes in the obvious spelling, which is the one that actually gets written, and
it catches nothing clever. The proofs that reach further are named in the
records themselves and are not replaced by anything here. 0004's is a test that
patches the library parser to raise and requires the load to succeed; 0011's is
a suite run with outbound access blocked. Neither is this file's job and neither
is made redundant by it.

EVERY INVARIANT SHIPS WITH A FIXTURE THAT TRIPS IT AND A ONE-CHANGE NEIGHBOUR
THAT DOES NOT. A pattern that matches nothing refuses nothing and passes
silently forever, and a rule that has quietly stopped biting looks exactly like
a tree that never violates it. `tests/fixtures/invariants/` is where those live
and `tests/test_invariants.py` is what asserts them.

The fixtures are `.txt` rather than `.py` on purpose. A fixture exists to hold
source this repository's own rules refuse, and a tracked `.py` file is linted by
ruff, type checked by mypy under `strict`, and required to appear in the mypy
module list by `tests/test_type_check_coverage.py`. A fixture that had to
satisfy all three could not contain the thing it exists to contain. The scan
reads bytes and never imports, so the extension costs nothing.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent.parent

# This file holds the patterns, so every pattern's own spelling is written in
# it. Scanning it would refuse the declaration of the rule rather than a
# violation of it. It is the only exclusion, it is here rather than in a
# configuration file somewhere else, and anything else added to this tuple is a
# hole in the scan that somebody has to argue for in the same place they open
# it.
NOT_SCANNED: tuple[str, ...] = ("src/findbuch/invariants.py",)

# The path sets an invariant is declared over.
#
# `shipped` is everything this project ships that loads a file or decides
# anything about one. The loading path of 0004 and the verdict path of 0006 and
# 0007 are both subsets of it today, and applying their invariants to the whole
# set is deliberately WIDER than those records require. That is a choice and not
# an oversight: naming the verdict path by file name would mean naming files
# #26 and #30 have not written yet, and a glob aimed at a name nobody has chosen
# is a rule that silently matches nothing on the day it lands. 0006 does allow
# the simplification routine outside the verdict path, for presentation or for a
# message a contributor reads. A module that legitimately needs it therefore
# needs an entry in NOT_SCANNED above, with the reason written where the entry
# is, and that is the trade this width costs.
#
# `tests` is the suite. It is separate because the invariant over it is about
# tests specifically rather than about shipped code.
PATH_SETS: dict[str, tuple[str, ...]] = {
    "shipped": ("src/findbuch/*.py", "src/findbuch/**/*.py", "tools/*.py"),
    "tests": ("tests/test_*.py",),
}


@dataclass(frozen=True)
class Invariant:
    """One property a pattern can decide, with why it exists and who decided it.

    `identifier` is what a test asserts on and what a refusal names. The reason
    is for the person who has just been refused, and it is beside the pattern
    rather than in a document, because somebody who hits a refusal and cannot
    find out why deletes the rule.

    `decided_in` is the issue that decided the property. It is required on every
    invariant. A rule whose origin cannot be found is a rule that gets argued
    with and then removed.
    """

    identifier: str
    decided_in: str
    path_set: str
    pattern: re.Pattern[str]
    reason: str


@dataclass(frozen=True)
class Violation:
    invariant: str
    path: str
    line_number: int
    line: str

    def __str__(self) -> str:
        return f"{self.invariant}: {self.path}:{self.line_number}: {self.line.strip()}"


INVARIANTS: tuple[Invariant, ...] = (
    Invariant(
        identifier="library-parser-off-the-loading-path",
        decided_in="#5",
        path_set="shipped",
        pattern=re.compile(
            r"\b(?:sympify|parse_expr|parse_latex|parse_mathematica)\s*\("
            r"|\bsympy\s*\.\s*S\s*\("
            r"|\bS\s*\(\s*[\"']"
            r"|\b(?:eval|exec)\s*\("
            # re.compile is a regular expression, not a code path, and this rule
            # would otherwise refuse every pattern in this repository including
            # its own. The lookbehind is the whole exception and it is spelled
            # out here rather than left as an exclusion somewhere else.
            r"|(?<!re\.)\bcompile\s*\("
        ),
        reason=(
            "0004 decided that the library's convenience parser is not called "
            "from the loading path in any of its spellings, because that parser "
            "is a path to arbitrary code execution and the formula string comes "
            "out of a file a stranger wrote. eval, exec and compile are here for "
            "the same reason: they are the shorter spellings of the same thing. "
            "Parsing is a walk of a syntax tree against the admitted grammar and "
            "the object is built node by node."
        ),
    ),
    Invariant(
        identifier="general-simplification-off-the-verdict-path",
        decided_in="#7",
        path_set="shipped",
        pattern=re.compile(
            r"\b(?:simplify|nsimplify|trigsimp|radsimp|powsimp|signsimp|"
            r"logcombine|combsimp)\s*\("
        ),
        reason=(
            "0006 decided that the verdict is an exact polynomial identity and "
            "never a question asked of the library's general simplification "
            "routine. That routine is a heuristic: it returns an unsimplified "
            "expression for things that are zero, it can take unbounded time, "
            "and it changes between releases. A verdict resting on it fails in "
            "the safe-looking direction, so a correct row reads as a failed one "
            "and contributors learn to distrust the checker."
        ),
    ),
    Invariant(
        identifier="no-absolute-tolerance-in-a-verdict",
        decided_in="#8",
        path_set="shipped",
        pattern=re.compile(
            r"(?:[<>]=?|==|!=)\s*(?:\d+(?:\.\d*)?[eE]-\d+|0\.0*[1-9])"
            r"|\b(?:EPS|EPSILON|TOL|TOLERANCE|ATOL|RTOL|atol|rtol|epsilon|"
            r"tolerance)\b"
        ),
        reason=(
            "0007 decided that no constant anybody picked appears in a verdict. "
            "The criterion is a comparison between two measured numbers: the "
            "candidate integral's drift against the Casimir noise floor from the "
            "same run. An absolute epsilon decides every verdict instead, there "
            "is no principled way to choose it, and both of its failure modes "
            "look the same from outside, so it gets loosened until it stops "
            "complaining and the leg becomes decoration."
        ),
    ),
    Invariant(
        identifier="no-socket-opening-import-on-a-shipped-path",
        decided_in="#12",
        path_set="shipped",
        pattern=re.compile(
            r"^\s*(?:import|from)\s+"
            r"(?:socket|socketserver|ssl|http|urllib|urllib3|ftplib|smtplib|"
            r"poplib|imaplib|telnetlib|nntplib|xmlrpc|webbrowser|requests|"
            r"httpx|aiohttp)\b",
            re.MULTILINE,
        ),
        reason=(
            "0011 decided that nothing about a run leaves the host and that the "
            "tool makes no network connection of its own. An import-level rule "
            "catches the addition before anything calls it, which is the branch "
            "no fixture happens to reach. It is half of the pair 0011 names: the "
            "other half is #19's suite run with outbound access blocked, and "
            "neither replaces the other. asyncio is deliberately NOT in this "
            "list. It opens sockets only through APIs already named here, and "
            "listing it would refuse a module using it for concurrency alone."
        ),
    ),
    Invariant(
        identifier="no-test-skips-itself-on-a-display-or-a-privilege",
        decided_in="#19",
        path_set="tests",
        pattern=re.compile(
            r"(?:skipIf|skipUnless|SkipTest|skipTest|pytest\s*\.\s*skip)"
            r"[^\n]*(?:DISPLAY|WAYLAND|getuid|geteuid|IsUserAnAdmin|"
            r"administrator|privileg|elevat)"
            r"|(?:DISPLAY|WAYLAND|getuid|geteuid|IsUserAnAdmin)"
            r"[^\n]*(?:skipIf|skipUnless|SkipTest|skipTest|pytest\s*\.\s*skip)"
        ),
        reason=(
            "#19 requires every test to run without a display and without "
            "elevated privileges, as a birth requirement rather than something "
            "repaired after it breaks. A test that skips itself when a display "
            "or a privilege is absent reports success for a run that did "
            "nothing, and a suite of those is green on a machine where none of "
            "it executed. Work that genuinely cannot meet this gets its own "
            "harness with a name that says what it is, excluded from the default "
            "run by construction, and the run prints that it was not asked for."
        ),
    ),
)


def invariant(identifier: str) -> Invariant | None:
    for declared in INVARIANTS:
        if declared.identifier == identifier:
            return declared
    return None


def files_in(path_set: str, root: Path = REPO_ROOT) -> list[Path]:
    """Every file the named path set reaches, minus the declared exclusions."""
    excluded = {(root / name).resolve() for name in NOT_SCANNED}
    found: set[Path] = set()
    for glob in PATH_SETS[path_set]:
        for path in root.glob(glob):
            if path.is_file() and path.resolve() not in excluded:
                found.add(path)
    return sorted(found)


def scan_text(text: str, declared: Iterable[Invariant], where: str) -> list[Violation]:
    """Every violation in one piece of text, by line, for the given invariants."""
    violations = []
    for rule in declared:
        for number, line in enumerate(text.splitlines(), start=1):
            if rule.pattern.search(line):
                violations.append(Violation(rule.identifier, where, number, line))
    return violations


def scan_file(path: Path, declared: Iterable[Invariant], where: str) -> list[Violation]:
    return scan_text(path.read_text(encoding="utf-8"), declared, where)


@dataclass(frozen=True)
class ScanResult:
    """What a scan refused, and what it looked at while doing so.

    `examined` is per invariant rather than a single total, because two
    invariants over different path sets look at different files and one number
    would hide an invariant whose set was empty. `not_evaluated` is derived from
    it and is what the runner has to print: a rule with nothing to read has not
    passed, and a run that prints nothing about it says the opposite.
    """

    violations: tuple[Violation, ...]
    examined: dict[str, int]

    @property
    def not_evaluated(self) -> tuple[str, ...]:
        return tuple(sorted(name for name, count in self.examined.items() if not count))

    @property
    def clean(self) -> bool:
        return not self.violations


def scan_tree(
    root: Path = REPO_ROOT, declared: Sequence[Invariant] = INVARIANTS
) -> ScanResult:
    violations: list[Violation] = []
    examined: dict[str, int] = {}
    for rule in declared:
        paths = files_in(rule.path_set, root)
        examined[rule.identifier] = len(paths)
        for path in paths:
            relative = path.relative_to(root).as_posix()
            violations.extend(scan_file(path, [rule], relative))
    return ScanResult(tuple(violations), examined)
