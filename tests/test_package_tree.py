"""The tree exists and is importable.

Deliberately the smallest possible suite. It is written against the standard
library's unittest rather than against a test framework, because choosing the
harness and fixing the shape every later refusal test follows is #15, and a
harness picked here would be that decision taken by accident.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class PackageIsInstalledAndImportable(unittest.TestCase):
    def test_import_succeeds(self) -> None:
        import findbuch

        self.assertTrue(findbuch.__version__)

    def test_package_is_the_one_in_this_tree(self) -> None:
        import findbuch

        installed = Path(findbuch.__file__).resolve()
        self.assertEqual(installed, REPO_ROOT / "src" / "findbuch" / "__init__.py")


class TheTreeHasThePlacesLaterWorkLandsIn(unittest.TestCase):
    def test_directories_exist(self) -> None:
        for relative in ("src/findbuch", "tests", "catalogue", "docs/decisions"):
            with self.subTest(relative=relative):
                self.assertTrue((REPO_ROOT / relative).is_dir())

    def test_the_interpreter_pin_exists_and_holds_one_version(self) -> None:
        pinned = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").split()
        self.assertEqual(len(pinned), 1)


if __name__ == "__main__":
    unittest.main()
