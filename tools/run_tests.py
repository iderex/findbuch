"""Run the test suite, the one way it is run.

Three callers need the suite: the `tests` leg of the gate, the coverage
measurement in tools/coverage_bar.py, and the workflow that runs the invariant
suite on its own. Three spellings of one invocation drift, and the one that
drifts is the one nobody runs by hand, so the invocation is written here and the
three callers exec this file.

    python tools/run_tests.py               the whole suite
    python tools/run_tests.py tests/x.py    one module, and anything else pytest
                                            accepts is passed through

IN PROCESS, NOT IN A SUBPROCESS. tools/coverage_bar.py runs this file under
`coverage run`, and coverage measures the process it starts. A launcher that
handed the work to a child would leave the measurement counting the launcher and
reporting nothing about the suite, which is a coverage number that looks like a
coverage number and is not one.

WHY THE ENVIRONMENT IS SET HERE RATHER THAN IN A CONFIGURATION FILE. pytest
loads every plugin that any installed distribution advertises through an entry
point, before it collects a single test. That is code this repository did not
ask for, running inside the run that decides whether the gate is green, and it
is chosen by whatever else happens to be in the environment. It is switched off
by an environment variable and by nothing else: pyproject.toml has no setting
that turns it off, which is why this file exists rather than a line of
configuration. What the suite gives up is that a plugin cannot be installed into
a checkout and picked up without being asked for, which is the point.

The rest of the configuration is in pyproject.toml, under
`[tool.pytest.ini_options]`, because that part pytest does read from a file and a
second home for it here would be the drift this file exists against.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

AUTOLOAD_OFF = "PYTEST_DISABLE_PLUGIN_AUTOLOAD"


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    # Set before pytest is imported. The variable is read while pytest builds
    # its plugin manager, and importing pytest first is the ordering mistake
    # that would leave this line true and ineffective.
    os.environ[AUTOLOAD_OFF] = "1"

    import pytest

    print(f"tests: pytest {pytest.__version__}, plugin autoload off", flush=True)
    return int(pytest.main([*arguments], plugins=[]))


if __name__ == "__main__":
    os.chdir(REPO_ROOT)
    raise SystemExit(main())
