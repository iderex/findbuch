"""The type checker's module list may not fall behind the tree.

`[tool.mypy] files` is written out by hand on purpose, so that a module is
covered by being added rather than by accident. The cost of writing it out is
that somebody adds a module and forgets the list, and then the module is not
type checked and nothing says so. This is the check that says so.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import subprocess
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def tracked_python_files() -> set[str]:
    listed = subprocess.run(
        ["git", "ls-files", "--", "*.py"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    return {line for line in listed.stdout.splitlines() if line}


def type_checked_files() -> set[str]:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        configuration = tomllib.load(handle)
    return set(configuration["tool"]["mypy"]["files"])


class TheDeclaredModuleSetCoversTheTree(unittest.TestCase):
    def test_every_tracked_module_is_declared(self) -> None:
        missing = sorted(tracked_python_files() - type_checked_files())
        self.assertEqual(
            missing,
            [],
            "these tracked modules are not in [tool.mypy] files, so nothing type "
            "checks them; add them to the list in pyproject.toml",
        )

    def test_every_declared_module_exists(self) -> None:
        dangling = sorted(type_checked_files() - tracked_python_files())
        self.assertEqual(
            dangling,
            [],
            "these entries in [tool.mypy] files are not tracked python files, so "
            "the list names something the tree does not have",
        )


if __name__ == "__main__":
    unittest.main()
