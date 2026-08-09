"""Install from the lockfile in a failing mode, and scan the resolved set.

#53. Two obligations that look like one and are not.

THE FIRST IS THAT THE LOCKFILE BINDS. Every other route in this tree installs
with `pip install --require-hashes --requirement requirements.lock`, and an
archive whose bytes are not the bytes that were resolved is refused before
anything imports it. Two things about that turned out to be different from how
it reads, and both were measured rather than supposed:

    python tools/supply_chain.py --selftest

The flag is not what puts pip in that mode. pip enters it BY ITSELF as soon as
any requirement in the file carries a hash, so against the lockfile as it stands,
deleting `--require-hashes` from the command changes nothing. The one case the
flag decides is a file with no hash left anywhere, which is why that case is a
row of the self-test: without it the flag could be deleted and every other row
would stay green.

And a hash binds the ARCHIVE rather than the RESOLUTION. A pin loosened from
`==` to `>=` is accepted whenever the version it still resolves to carries one
of the listed hashes, so `check_pinned` below refuses that case here instead.
The two together are the failing mode: pip refuses an archive that was swapped,
and this file refuses a lockfile that stopped naming exactly one archive per
requirement.

WHAT NEITHER OF THEM CHECKS, said here rather than left to be assumed. Whether
the lockfile still matches what `pyproject.toml` declares is a third question and
nothing in this file asks it. Regenerating the lock is a command in
`pyproject.toml` beside the bounds it reads, and a bound raised without that
command leaves a lock that is internally consistent, fully hashed, and behind the
declaration. A route that re-resolves and compares would answer it; there is none
here and none is claimed.

THE SECOND IS THAT SOMETHING READS THE ADVISORIES. The scan runs over the
lockfiles by path rather than over an installed environment, so what is reported
is always something this project pins and never something the scanner dragged in
behind itself.

EXIT STATUS COMES FROM THE PROCESS THAT DECIDED, AND FROM NOTHING ELSE. Every
subprocess here is a list handed to `subprocess.run`, captured, and read back
through its own `returncode`. There is no shell, so there is no pipe, so there is
no last-command-in-the-pipe to report success on behalf of a scanner that
refused. That mistake leaves a check looking exactly like one that works, which
is why the shape is written down here rather than left to the reader.

Run the checks:

    python tools/supply_chain.py --check

Run the proof that both halves bite:

    python tools/supply_chain.py --selftest

Both reach the network. That is why this is not in the gate's default run.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCKFILES: tuple[Path, ...] = (
    REPO_ROOT / "requirements.lock",
    REPO_ROOT / "requirements-dev.lock",
)
EXCEPTIONS = REPO_ROOT / "security" / "vulnerability-exceptions.toml"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "supply-chain"

# A requirement line in a compiled lockfile: the name, then the specifier, then
# an optional line continuation. Continuation lines and comments are indented,
# so a line at column zero that is not blank and not a comment is one of these.
REQUIREMENT = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)\s*(?P<specifier>[^\s;]*)")
HASH = re.compile(r"--hash=sha256:[0-9a-f]{64}")


@dataclass(frozen=True)
class Refusal:
    """One reason a subject was refused.

    `code` is what a test asserts on, for the reason `findbuch.validation` gives
    at length: a corpus of things that must be refused is only worth having if it
    says WHICH refusal fired.
    """

    code: str
    message: str
    where: str = ""

    def __str__(self) -> str:
        location = f" at {self.where}" if self.where else ""
        return f"{self.code}{location}: {self.message}"


@dataclass(frozen=True)
class Outcome:
    """What one subprocess did, kept whole so a caller can print it."""

    returncode: int
    output: str

    @property
    def refused(self) -> bool:
        return self.returncode != 0


def _run(command: Sequence[str]) -> Outcome:
    """Run a command as a list, capture both streams, keep its own status.

    No `shell=True` and no pipe anywhere, which is the point made in the module
    docstring: the status read below is the status of the process that decided.
    """
    done = subprocess.run(
        list(command), capture_output=True, text=True, check=False, cwd=REPO_ROOT
    )
    return Outcome(done.returncode, done.stdout + done.stderr)


def requirements_in(text: str) -> list[tuple[int, str, str, int]]:
    """Every requirement of a compiled lockfile, with its hash count.

    Returns the line number, the name, the specifier and how many sha256 hashes
    the entry carries across its continuation lines.
    """
    found: list[tuple[int, str, str, int]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        if not line or line.startswith((" ", "\t", "#")):
            continue
        match = REQUIREMENT.match(line)
        if match is None:
            continue
        hashes = len(HASH.findall(line))
        for following in lines[index:]:
            if following and not following.startswith((" ", "\t")):
                break
            hashes += len(HASH.findall(following))
        found.append((index, match.group("name"), match.group("specifier"), hashes))
    return found


def check_pinned(text: str, where: str) -> list[Refusal]:
    """Every requirement names one version and carries at least one hash.

    This is the half pip does not do. `--require-hashes` binds the ARCHIVE and
    not the RESOLUTION: a requirement loosened to a range is accepted whenever
    the version it still resolves to happens to carry one of the listed hashes,
    and then the lockfile has stopped deciding which version is installed while
    looking exactly as it did before.
    """
    refusals: list[Refusal] = []
    for line, name, specifier, hashes in requirements_in(text):
        if not specifier.startswith("==") or len(specifier) < 3:
            refusals.append(
                Refusal(
                    "lock.unpinned",
                    f"'{name}' is written as '{name}{specifier}', which is not a "
                    f"single version; a lockfile that admits a range has stopped "
                    f"deciding what gets installed",
                    f"{where}:{line}",
                )
            )
        if hashes == 0:
            refusals.append(
                Refusal(
                    "lock.unhashed",
                    f"'{name}' carries no sha256 hash, so nothing checks that the "
                    f"archive installed is the archive that was resolved",
                    f"{where}:{line}",
                )
            )
    return refusals


def locked_install(requirements: Path) -> Outcome:
    """Resolve the lockfile in the mode that refuses a swapped archive.

    `--dry-run` because what is being decided is whether pip accepts the file,
    not whether this machine ends up with the packages on it. pip still fetches
    and hashes under that flag, which is what makes the refusal real; the
    `hashes-altered` case of the self-test is what says so rather than the
    sentence.
    """
    return _run(locked_install_command(requirements))


def locked_install_command(requirements: Path) -> list[str]:
    """The argument vector, apart from running it, so a test can read it."""
    return [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--dry-run",
        "--ignore-installed",
        "--require-hashes",
        "--requirement",
        str(requirements),
    ]


@dataclass(frozen=True)
class Waiver:
    """One advisory this project has decided it cannot act on yet."""

    identifier: str
    reason: str
    expires: dt.date


def read_exceptions(path: Path, today: dt.date) -> tuple[list[Waiver], list[Refusal]]:
    """The live exceptions, and a refusal for every one that has run out.

    An expired entry is a refusal rather than a silently dropped line. Dropping
    it would put the advisory back in front of the scan on the day it expired,
    which is right, and would say nothing about the register still carrying a
    row nobody revisited, which is the thing an expiry is for.
    """
    if not path.is_file():
        return [], []
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    live: list[Waiver] = []
    refusals: list[Refusal] = []
    for index, entry in enumerate(document.get("exception", [])):
        identifier = str(entry.get("id", ""))
        reason = str(entry.get("reason", ""))
        raw = entry.get("expires")
        where = f"{path.name}[{index}]"
        if not identifier or not reason:
            refusals.append(
                Refusal(
                    "exception.incomplete",
                    "an exception carries no advisory identifier or no reason, and "
                    "an acceptance nobody wrote a reason for cannot be reviewed",
                    where,
                )
            )
            continue
        if not isinstance(raw, dt.date):
            refusals.append(
                Refusal(
                    "exception.no-expiry",
                    f"'{identifier}' has no expiry date; an acceptance with no "
                    f"expiry is a permanent one wearing another word",
                    where,
                )
            )
            continue
        if raw < today:
            refusals.append(
                Refusal(
                    "exception.expired",
                    f"'{identifier}' expired on {raw.isoformat()} and is no longer "
                    f"suppressing anything; renew it with a reason or fix the "
                    f"dependency",
                    where,
                )
            )
            continue
        live.append(Waiver(identifier, reason, raw))
    return live, refusals


def scan(requirements: Sequence[Path], ignored: Sequence[str]) -> Outcome:
    """Audit pinned requirement files against the advisory database.

    `--no-deps` because every file handed here is a complete compiled lockfile;
    the entries are the resolved set and there is nothing under them to walk.
    `--strict` so that a package the service could not answer for is a failure
    rather than a quiet pass.
    """
    return _run(scan_command(requirements, ignored))


def scan_command(requirements: Sequence[Path], ignored: Sequence[str]) -> list[str]:
    """The argument vector, apart from running it, so a test can read it."""
    command = [
        sys.executable,
        "-m",
        "pip_audit",
        "--no-deps",
        "--strict",
        "--progress-spinner",
        "off",
    ]
    for identifier in ignored:
        command += ["--ignore-vuln", identifier]
    for path in requirements:
        command += ["--requirement", str(path)]
    return command


# The ways a lockfile is made stale, each one change to the real file, each with
# the identifier the run has to earn. Written as functions rather than as stored
# copies of a mutated lockfile: a stored copy drifts the moment the real lock is
# regenerated, and then the self-test proves something about last month's file.
def _entry_lines(text: str, name: str) -> tuple[int, int]:
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith(f"{name}=="):
            end = index + 1
            while end < len(lines) and lines[end].startswith((" ", "\t")):
                end += 1
            return index, end
    raise LookupError(f"no requirement named {name!r} in this lockfile")


def loosen_the_pin(text: str, name: str) -> str:
    start, _ = _entry_lines(text, name)
    lines = text.splitlines(keepends=True)
    lines[start] = lines[start].replace("==", ">=", 1)
    return "".join(lines)


def drop_the_hashes(text: str, name: str) -> str:
    start, end = _entry_lines(text, name)
    lines = text.splitlines(keepends=True)
    kept = [line for line in lines[start:end] if "--hash=sha256:" not in line]
    kept[0] = kept[0].replace(" \\", "")
    return "".join(lines[:start] + kept + lines[end:])


def alter_the_hashes(text: str, name: str) -> str:
    start, end = _entry_lines(text, name)
    lines = text.splitlines(keepends=True)
    changed = []
    for line in lines[start:end]:
        head, marker, tail = line.partition("--hash=sha256:")
        if marker:
            line = head + marker + ("0" if tail[0] != "0" else "1") + tail[1:]
        changed.append(line)
    return "".join(lines[:start] + changed + lines[end:])


def drop_every_hash(text: str, name: str) -> str:  # noqa: ARG001
    """Every hash in the file, not one entry's.

    This is the case `--require-hashes` is actually for, and it took measuring to
    find out. pip turns hash checking on BY ITSELF as soon as any requirement in
    the file carries a hash, so with one entry unhashed among many the flag
    changes nothing and dropping it from the command leaves every other case here
    green. With no hash left anywhere there is nothing for that behaviour to
    trigger on, and the flag is the only thing between this file and an install
    that checks nothing.

    The requirement name is not read. It is in the signature because every
    mutation shares one, and a second signature for one case would be worse.
    """
    lines = [
        line for line in text.splitlines(keepends=True) if "--hash=sha256:" not in line
    ]
    return "".join(line.replace(" \\\n", "\n") for line in lines)


@dataclass(frozen=True)
class Mutation:
    """One way of making the lockfile stale, and who has to notice.

    `refused_by` is a SET and it is compared as one. A membership check would
    pass on `pin-loosened` the day pip started refusing it, and would pass on
    `hashes-altered` the day this file started refusing everything, and either
    way the reader would be told which half is carrying the check and be wrong.
    """

    name: str
    what: str
    apply: Callable[[str, str], str]
    refused_by: frozenset[str]
    # Whether the mutation is one contiguous edit. Three of the four are, and
    # tests/test_supply_chain.py checks it, for the reason
    # tests/test_refused_corpus.py gives about its pairs: a refusal is
    # attributable to the mistake only when the mistake is the one difference.
    # The fourth is a whole-file edit by construction, and saying so here is what
    # keeps that from being a silent exemption.
    contiguous: bool = True


MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        "hashes-dropped",
        "an entry left with no hash at all",
        drop_the_hashes,
        # Both. pip refuses it because --require-hashes has nothing to check
        # against, and the rule here refuses it because an unhashed entry is not
        # a lockfile entry. This is the only case with two refusers and it is the
        # one a regenerated lock is least likely to produce.
        frozenset({"pip", "this file"}),
    ),
    Mutation(
        "hashes-altered",
        "one character changed in every hash of one entry",
        alter_the_hashes,
        # pip alone. The entry is still pinned and still hashed, so nothing about
        # the FILE is wrong; what is wrong is the archive it names, and only the
        # process that fetches the archive can say so.
        frozenset({"pip"}),
    ),
    Mutation(
        "pin-loosened",
        "one entry's '==' widened to '>=', hashes untouched",
        loosen_the_pin,
        # This file alone. Measured, not assumed: pip accepts it, because the
        # version it still resolves to carries one of the listed hashes. That
        # measurement is the whole reason check_pinned exists.
        frozenset({"this file"}),
    ),
    Mutation(
        "every-hash-dropped",
        "every hash in the file gone, which is the case the flag is for",
        drop_every_hash,
        # Both, and this is the only case in which `--require-hashes` is what
        # makes pip refuse. Dropping that flag from the command leaves the three
        # cases above green, because pip enables hash checking by itself as soon
        # as anything in the file is hashed. Without this row the flag could be
        # deleted and nothing here would notice.
        frozenset({"pip", "this file"}),
        contiguous=False,
    ),
)

MUTATED = "mpmath"


def selftest(quiet: bool = False) -> int:
    """Prove both halves refuse what they name, and that a good input passes.

    Every mutation is paired with the unmutated file, for the reason
    tests/test_refused_corpus.py gives: a checker that refused everything would
    satisfy the refusing half on its own.
    """

    def say(line: str) -> None:
        if not quiet:
            print(line, flush=True)

    wrong = 0
    lock = LOCKFILES[0]
    text = lock.read_text(encoding="utf-8")
    scratch = REPO_ROOT / ".supply-chain-selftest"
    scratch.mkdir(exist_ok=True)

    say(f"selftest: the lockfile half, over {lock.name}, mutating '{MUTATED}'")
    for mutation in MUTATIONS:
        mutated = mutation.apply(text, MUTATED)
        target = scratch / f"{mutation.name}.lock"
        target.write_text(mutated, encoding="utf-8")
        # Both are asked every time. Stopping at the first refusal would leave
        # the set below saying which refuser was reached first rather than which
        # ones refuse.
        refusers = set()
        if check_pinned(mutated, mutation.name):
            refusers.add("this file")
        if locked_install(target).refused:
            refusers.add("pip")
        if refusers == set(mutation.refused_by):
            listed = " and ".join(sorted(refusers))
            say(f"  ok      {mutation.name:<18} refused by {listed}: {mutation.what}")
        else:
            wrong += 1
            say(
                f"  FAIL    {mutation.name:<18} refused by "
                f"{sorted(refusers) or 'nothing'}, expected "
                f"{sorted(mutation.refused_by)}"
            )

    neighbour = scratch / "unmutated.lock"
    neighbour.write_text(text, encoding="utf-8")
    if check_pinned(text, "unmutated") or locked_install(neighbour).refused:
        wrong += 1
        say("  FAIL    unmutated          the real lockfile has to be accepted")
    else:
        say(
            f"  ok      {'unmutated':<18} accepted, so the {len(MUTATIONS)} above "
            f"are the mutation"
        )

    say("")
    say("selftest: the scan half, over the fixtures")
    trips = FIXTURES / "trips" / "a-version-with-known-advisories.txt"
    clean = FIXTURES / "neighbour" / "a-version-with-known-advisories.txt"
    if scan([trips], []).refused:
        say("  ok      trips              the scan refuses a pin with known advisories")
    else:
        wrong += 1
        say("  FAIL    trips            the scan passed a pin with known advisories")
    if scan([clean], []).refused:
        wrong += 1
        say(
            "  FAIL    neighbour          the fixed version is reported vulnerable; "
            "this half is a claim about the advisory database on the day it ran, "
            "not about this tree, and the fixture needs raising"
        )
    else:
        say("  ok      neighbour          the same file at the fixed version passes")

    say("")
    if wrong:
        say(f"selftest: REFUSED, {wrong} case(s) wrong. The checks do not bite.")
        return 1
    say(f"selftest: {len(MUTATIONS) + 3} cases, all as expected.")
    return 0


def check() -> int:
    """The two checks, over the real lockfiles."""
    refusals: list[Refusal] = []
    print(f"supply-chain: {len(LOCKFILES)} lockfile(s) to check", flush=True)

    for path in LOCKFILES:
        refusals.extend(check_pinned(path.read_text(encoding="utf-8"), path.name))
    for refusal in refusals:
        print(f"  {refusal}")
    if not refusals:
        print("supply-chain: every requirement names one version and carries a hash")

    failed = bool(refusals)
    for path in LOCKFILES:
        outcome = locked_install(path)
        verdict = "REFUSED" if outcome.refused else "accepted"
        print(f"supply-chain: locked install of {path.name}: {verdict}")
        if outcome.refused:
            failed = True
            print(outcome.output)

    today = dt.datetime.now(tz=dt.UTC).date()
    live, expired = read_exceptions(EXCEPTIONS, today)
    for refusal in expired:
        print(f"  {refusal}")
        failed = True
    print(
        f"supply-chain: {len(live)} live vulnerability exception(s) "
        f"on {today.isoformat()}"
    )
    for entry in live:
        print(f"  {entry.identifier} until {entry.expires.isoformat()}: {entry.reason}")

    outcome = scan(LOCKFILES, [entry.identifier for entry in live])
    print(outcome.output.rstrip())
    if outcome.refused:
        failed = True
        print("supply-chain: REFUSED by the scan, whose own output is above")

    if failed:
        print("supply-chain: REFUSED")
        return 1
    print("supply-chain: the lockfiles bind and the resolved set carries no advisory")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the dependency set.")
    parser.add_argument(
        "--check", action="store_true", help="run the checks over the real lockfiles"
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="prove both halves refuse what they name",
    )
    arguments = parser.parse_args(argv)
    if arguments.selftest:
        return selftest()
    if arguments.check or not (arguments.check or arguments.selftest):
        return check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
