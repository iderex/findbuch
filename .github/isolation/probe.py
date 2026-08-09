"""What the container has to be before the suite running in it means anything.

#19 requires the full default suite to pass with no display server, no
privileged user and no outbound network. A job that merely claims those three
conditions is worth nothing: drop `--network none` from one `docker run` line
and the suite passes exactly as before, the check stays green, and the sentence
in the workflow goes on saying the network was blocked. Nobody would notice for
as long as it took somebody to add a test that fetches something.

So the conditions are read inside the container, in the same process tree as the
suite, and a condition that does not hold is a refusal. This file is the guard,
and the workflow proves it bites by running it once with the network attached
and requiring it to refuse.

WHAT EACH CONDITION IS READ FROM, because a probe that asks a library what it
thinks is weaker than one that reads the state.

The display is the environment. There is nothing else to read: a display server
is reachable or not through the variables that name it, and an X or Wayland
client finds it no other way.

The privilege is `/proc/self/status`, whose `Uid:` line carries the real,
effective, saved and filesystem user ids of this process. Reading it rather than
calling `os.geteuid` keeps this file type-checkable on the machine a contributor
runs mypy on, which is not necessarily the platform the probe runs on, and it is
also the more direct evidence.

The network is read twice, from two different directions, because either one
alone has a hole. `/sys/class/net` lists the interfaces the network namespace
has, and a detached namespace has only the loopback device; but an interface
list says nothing about whether a route exists. So a connection is also
attempted, to a literal address so that the attempt does not depend on name
resolution, and it has to fail. An attempt that succeeds is the case this whole
file exists for.

WHY THIS FILE IMPORTS A SOCKET-OPENING MODULE, disclosed rather than left to be
noticed. `no-socket-opening-import-on-a-shipped-path` refuses exactly this
import, and its declared path set is what this project ships:
`src/findbuch/*.py` and `tools/*.py`. This file is under `.github/` and is in
neither, so nothing refuses it. That is the invariant's scope rather than a way
around it: the rule is about the loading and verification paths, and a probe
whose whole job is to prove that a socket cannot be opened is not one of them.
It is not installed, not imported by anything the package ships, and not on any
path a row travels.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path

# A literal address, so that the attempt does not depend on name resolution and
# a failure cannot be a DNS failure wearing the same coat. It is a well-known
# public resolver on its DNS-over-TLS port; nothing is sent and nothing is read.
UNREACHABLE_IF_ISOLATED = ("1.1.1.1", 853)
CONNECT_SECONDS = 5

DISPLAY_VARIABLES = ("DISPLAY", "WAYLAND_DISPLAY")
LOOPBACK = "lo"

PROC_STATUS = Path("/proc/self/status")
INTERFACES = Path("/sys/class/net")


def refuse(condition: str, detail: str) -> None:
    print(f"probe: REFUSED {condition}: {detail}")


def check_no_display() -> bool:
    named = {
        variable: os.environ.get(variable, "")
        for variable in DISPLAY_VARIABLES
        if os.environ.get(variable, "").strip()
    }
    if named:
        refuse("display", f"these variables name a display: {named}")
        return False
    print(f"probe: ok display, none of {', '.join(DISPLAY_VARIABLES)} names one")
    return True


def effective_user_id() -> int | None:
    if not PROC_STATUS.is_file():
        return None
    for line in PROC_STATUS.read_text(encoding="utf-8").splitlines():
        if line.startswith("Uid:"):
            fields = line.split()
            # Uid: <real> <effective> <saved> <filesystem>
            return int(fields[2])
    return None


def check_not_privileged() -> bool:
    effective = effective_user_id()
    if effective is None:
        refuse("privilege", f"{PROC_STATUS} does not exist, so nothing was read")
        return False
    if effective == 0:
        refuse("privilege", "the effective user is root")
        return False
    print(f"probe: ok privilege, effective user id is {effective} and not 0")
    return True


def check_only_loopback() -> bool:
    if not INTERFACES.is_dir():
        refuse("interfaces", f"{INTERFACES} does not exist, so nothing was read")
        return False
    present = sorted(entry.name for entry in INTERFACES.iterdir())
    if present != [LOOPBACK]:
        refuse("interfaces", f"the namespace carries {present}, not [{LOOPBACK!r}]")
        return False
    print(f"probe: ok interfaces, the namespace carries only {LOOPBACK}")
    return True


def check_connection_fails() -> bool:
    host, port = UNREACHABLE_IF_ISOLATED
    try:
        with socket.create_connection((host, port), CONNECT_SECONDS):
            pass
    except OSError as refused:
        print(f"probe: ok network, connecting to {host}:{port} failed: {refused}")
        return True
    refuse("network", f"a connection to {host}:{port} succeeded from inside")
    return False


def main() -> int:
    print("probe: reading the conditions #19 requires, inside the container")
    results = [
        check_no_display(),
        check_not_privileged(),
        check_only_loopback(),
        check_connection_fails(),
    ]
    if all(results):
        print(f"probe: {len(results)} condition(s) read, all of them held")
        return 0
    print(
        f"probe: REFUSED, {results.count(False)} of {len(results)} condition(s) "
        f"did not hold; the suite was not started, because a run under the wrong "
        f"conditions is worse than no run"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
