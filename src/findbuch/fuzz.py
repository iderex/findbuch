"""Feed bytes to the parser and require the outcome to be one of two things.

#56. The parser is the only place in this project where hostile input meets
code: it reads a formula out of a file a stranger wrote and produces an object
everything downstream computes with, and `docs/decisions/0004-expression-grammar.md`
says the grammar is the boundary and there is no sandbox behind it. A boundary
is worth what it does on the input nobody anticipated.

THE PROPERTY, and it is one sentence. Every input produces either a built object
or a refusal carrying an identifier the parser declares. Anything else is a
finding: an unhandled error of any type, a refusal with an identifier nobody
declared, and a seed that takes long enough to be a denial of service.

WHY THAT IS THE PROPERTY AND NOT "IT DOES NOT CRASH". An unhandled error out of
this module reaches whatever called it, and the callers are a loader walking a
catalogue and a structure file being read at import. A traceback there is a
refusal that named no file, told the contributor nothing, and stopped the run
over the rows after it. The identifier is the difference between a boundary and
an accident.

WHAT THE BYTES BECOME. They are decoded as UTF-8 with `surrogateescape`, which
is total: no byte string is turned away by this harness before it reaches the
parser. That matters more than it looks. The obvious alternative, decoding
strictly and skipping what fails, is a harness that quietly stops testing the
inputs most likely to break something, and the first finding this harness
produced was exactly such an input.

WHAT THIS DOES NOT REACH, stated rather than left to a reader of a green job.
A row arrives through `tomllib`, which refuses a file that is not valid UTF-8,
so some seeds here cannot arrive through a row today. They are kept because this
module is a boundary in its own right, called from more than one place, and
because what `tomllib` admits is not this project's decision to make.

A HANG IS NOT DETECTED, IT IS TIMED. The replay runs in one process and takes no
step to interrupt a seed that never returns; a seed that hangs stops the job and
the job's own timeout is what reports it. What is measured here is duration, so
a seed that got slow rather than stuck is named with its number. The depth,
length and size limits from #22 are what make the hang unreachable, and the
seeds that would reach it without them are in the corpus.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import sympy

from findbuch.expression import REFUSALS, ExpressionRefused, SymbolTable, parse

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent.parent
SEEDS = REPO_ROOT / "tests" / "fixtures" / "fuzz" / "seeds"

# How long one seed may take before it is reported. It is not a verdict about a
# formula and nothing about a row depends on it: it is the number that separates
# "the limits held" from "the limits held eventually". Generous, because a
# loaded machine is not a finding, and finite, because the alternative is a
# harness that reports a denial of service as a pass.
SECONDS_PER_SEED = 5

# The table a seed is parsed against. A fixed one, and a small one, because the
# harness is about the grammar rather than about any row: a table that grew with
# the catalogue would change what the corpus means between runs.
COORDINATES: tuple[str, ...] = ("M1", "M2", "M3", "g1", "g2", "g3")
PARAMETERS: tuple[str, ...] = ("A1", "A2", "A3")

ParseFunction = Callable[[str, SymbolTable], sympy.Expr]


def table() -> SymbolTable:
    return SymbolTable.of(COORDINATES, PARAMETERS)


@dataclass(frozen=True)
class Seed:
    """One input, with where it came from and what it is.

    The bytes are stored base64 in the file rather than raw. A raw seed would be
    normalised by whatever line-ending translation a clone happens to have on,
    which would silently delete the carriage return a seed exists to carry, and
    the seed would go on passing while testing something else.
    """

    name: str
    what: str
    data: bytes


@dataclass(frozen=True)
class Finding:
    """One seed whose outcome was neither of the two admitted ones.

    It carries the bytes as well as the name, because a finding from the search
    is an input nothing committed and the corpus is where it belongs. A finding
    that reported only a name would have to be reconstructed by hand from a
    description, which is how a corpus stops growing.
    """

    seed: str
    kind: str
    detail: str
    data: bytes

    def __str__(self) -> str:
        return f"{self.kind}: {self.seed}: {self.detail}"


class CorpusRefused(Exception):  # noqa: N818
    """The corpus itself, rather than anything it says about the parser."""


def read_seed(path: Path) -> Seed:
    """One seed file: comment lines, then the base64 of the bytes.

    THE EMPTY SEED IS A SEED. A file whose payload decodes to no bytes at all is
    the input that is nothing, and the parser has a refusal for it. What is
    refused here is a file carrying no payload LINE, which is a file somebody
    described and then did not finish. The two look the same in a directory
    listing and they are not the same thing.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    described = [line[1:].strip() for line in lines if line.startswith("#")]
    payload = [line for line in lines if not line.startswith("#")]
    if not payload:
        raise CorpusRefused(f"{path.name} carries no seed, only description")
    encoded = "".join(line.strip() for line in payload)
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError as broken:
        raise CorpusRefused(f"{path.name} is not base64: {broken}") from broken
    return Seed(path.stem, " ".join(described), data)


def read_corpus(directory: Path = SEEDS) -> list[Seed]:
    """Every seed in the directory, in a fixed order.

    BOTH EMPTY ANSWERS ARE REFUSED HERE rather than returned as an empty list. A
    corpus directory that stopped being checked out and a corpus that happens to
    hold nothing produce the same green job otherwise, and that job would say
    the parser had been replayed against everything known to break it.
    """
    if not directory.is_dir():
        raise CorpusRefused(
            f"there is no corpus at '{directory}', so nothing was replayed and "
            f"a run that reports success here reports it about nothing"
        )
    seeds = [read_seed(path) for path in sorted(directory.glob("*.b64"))]
    if not seeds:
        raise CorpusRefused(
            f"the corpus at '{directory}' holds no seed, and a replay of no "
            f"seeds is not a replay"
        )
    return seeds


def replay_one(seed: Seed, parse_function: ParseFunction = parse) -> Finding | None:
    """The property, on one seed. `None` means the outcome was an admitted one.

    `parse_function` is an argument so that the branch below can be reached by a
    test with a function that misbehaves on purpose. A harness whose failure
    path nothing executes reports success for a reason nobody has checked.
    """
    text = seed.data.decode("utf-8", errors="surrogateescape")
    started = time.monotonic()
    try:
        parse_function(text, table())
    except ExpressionRefused as refusal:
        if refusal.code not in REFUSALS:
            return Finding(
                seed.name,
                "unknown-identifier",
                f"refused as '{refusal.code}', which the parser does not declare",
                seed.data,
            )
    except BaseException as escaped:
        # Every type, including the ones a narrower clause would let through.
        # What this harness is for is the error nobody predicted, so predicting
        # its base class would be the same mistake one level up.
        return Finding(
            seed.name,
            "unhandled-error",
            f"{type(escaped).__name__}: {escaped}",
            seed.data,
        )
    spent = time.monotonic() - started
    if spent > SECONDS_PER_SEED:
        return Finding(
            seed.name,
            "too-slow",
            f"took {spent:.1f}s, and the budget for one seed is {SECONDS_PER_SEED}s",
            seed.data,
        )
    return None


def replay(
    seeds: Iterable[Seed], parse_function: ParseFunction = parse
) -> list[Finding]:
    found = [replay_one(seed, parse_function) for seed in seeds]
    return [finding for finding in found if finding is not None]


def mutations(seed: Seed, rounds: int) -> list[Seed]:
    """Inputs derived from one seed, by rules rather than by chance.

    NOT COVERAGE GUIDED, and not offered as though it were. A coverage-guided
    engine is a dependency this project does not carry and #56's split puts that
    run outside the gate anyway; what is here is a deterministic derivation, so
    a search that finds something finds it again on the next machine. What it
    gives up is the thing coverage guidance is for: it will not find its way
    into a branch nothing in the corpus already approaches.
    """
    data = seed.data
    derived: list[Seed] = []
    for round_number in range(rounds):
        position = round_number % max(len(data), 1)
        for name, changed in (
            ("truncated", data[:position]),
            ("doubled", data[:position] + data[position:] * 2),
            ("bracketed", b"(" * (round_number + 1) + data),
            ("powered", data + b"**" + str(round_number + 1).encode("ascii")),
            ("joined", data + b"+" + data),
        ):
            derived.append(
                Seed(
                    f"{seed.name}-{name}-{round_number}",
                    "derived from a committed seed by the search",
                    changed,
                )
            )
    return derived


def search(seeds: Sequence[Seed], rounds: int) -> tuple[list[Finding], int]:
    """Derive inputs from the corpus and replay each one. Returns what it tried."""
    derived: list[Seed] = []
    for seed in seeds:
        derived.extend(mutations(seed, rounds))
    return replay(derived), len(derived)


def as_seed_file(seed: Seed) -> str:
    """The committed form of a seed, so a finding can be added to the corpus."""
    encoded = base64.b64encode(seed.data).decode("ascii")
    return f"# {seed.what}\n{encoded}\n"
