"""Replay the seed corpus against the parser, and search on request.

    python tools/fuzz_parser.py

replays every committed seed and is what the gate leg and the
`parser fuzz seed replay` job run. It needs no fuzzing engine and costs seconds,
and what it catches is a change that makes a known-hostile input crash rather
than refuse.

    python tools/fuzz_parser.py --search 8

derives inputs from the corpus and replays those as well. It is out of the gate
by construction rather than by a flag the gate happens not to pass: the leg in
tools/gate.py invokes this file with no arguments and the default is the replay.

    python tools/fuzz_parser.py --write-finding-into tests/fixtures/fuzz/seeds

writes anything the search found into the corpus, so that a corpus grows by
having found something rather than only by hand.

WHAT THE RUN SAYS. The number of seeds and the number of derived inputs, always,
because a replay of nothing and a replay that found nothing print the same
verdict otherwise. An absent or empty corpus is a refusal here rather than a
green run over zero seeds; findbuch.fuzz decides that and this file reports it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from findbuch.fuzz import (
    SEEDS,
    CorpusRefused,
    Finding,
    Seed,
    as_seed_file,
    read_corpus,
    replay,
    search,
)


def report(findings: list[Finding], what: str) -> None:
    print(f"fuzz: {len(findings)} finding(s) over {what}")
    for finding in findings:
        print(f"  {finding}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fuzz the expression parser.")
    parser.add_argument(
        "--corpus",
        default=str(SEEDS),
        metavar="DIR",
        help="the seed corpus to replay",
    )
    parser.add_argument(
        "--search",
        type=int,
        default=0,
        metavar="ROUNDS",
        help="also derive inputs from each seed and replay those; out of the gate",
    )
    parser.add_argument(
        "--write-finding-into",
        default="",
        metavar="DIR",
        help="write each finding's input into this corpus directory as a seed",
    )
    arguments = parser.parse_args(argv)

    try:
        seeds = read_corpus(Path(arguments.corpus))
    except CorpusRefused as refused:
        print(f"fuzz: REFUSED, {refused}")
        return 1

    print(f"fuzz: replaying {len(seeds)} seed(s) from {arguments.corpus}", flush=True)
    findings = replay(seeds)
    report(findings, f"{len(seeds)} seed(s)")

    if arguments.search:
        derived_findings, tried = search(seeds, arguments.search)
        print(
            f"\nfuzz: searched {tried} input(s) derived from the corpus, "
            f"{arguments.search} round(s) per seed",
            flush=True,
        )
        report(derived_findings, f"{tried} derived input(s)")
        findings = findings + derived_findings
    else:
        print(
            "\nfuzz: the search was NOT run and this run covered the committed "
            "seeds only. Ask for it with --search N, which derives inputs from "
            "each seed; it is deterministic and it is not coverage guided."
        )

    if findings and arguments.write_finding_into:
        into = Path(arguments.write_finding_into)
        into.mkdir(parents=True, exist_ok=True)
        for finding in findings:
            path = into / f"{finding.seed}.b64"
            path.write_text(
                as_seed_file(
                    Seed(
                        finding.seed,
                        f"found by the search: {finding.kind}",
                        finding.data,
                    )
                ),
                encoding="utf-8",
            )
        print(f"fuzz: wrote {len(findings)} finding(s) into {into}")

    if findings:
        print("\nfuzz: REFUSED, the outcomes above were neither of the two admitted")
        return 1
    print("\nfuzz: every input produced a built object or a declared refusal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
