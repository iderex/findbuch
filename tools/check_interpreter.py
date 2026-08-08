"""Refuse a gate run on an interpreter other than the one .python-version pins.

`.python-version` is the only tracked file that holds that number, and this is
what reads it locally. The workflow reads the same file through its own
interpreter setup, so the two cannot drift apart into two different pins.

The pin is not the floor. `pyproject.toml` declares which interpreters the
project claims to work with, and this file declares the one the gate is measured
on. A green run on a different interpreter would be a measurement of something
other than what the pin names, which is why this refuses rather than warns. The
build against the floor is its own job, #52.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PIN = REPO_ROOT / ".python-version"


def pinned() -> str:
    return PIN.read_text(encoding="utf-8").strip()


def running() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def main() -> int:
    wanted = pinned()
    have = running()
    print(f"interpreter: {PIN.name} pins {wanted}, this run is {have}")
    if not wanted:
        print("interpreter: REFUSED, the pin is empty")
        return 1
    if have != wanted:
        print(
            f"interpreter: REFUSED, the gate is measured on {wanted} and this is "
            f"{have}; run it on {wanted} or change the pin deliberately"
        )
        return 1
    print(f"interpreter: {have} matches the pin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
