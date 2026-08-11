"""The package reads its own data when it is not sitting in this checkout.

#84. The schema and the Poisson structure files used to live at the repository
root and be addressed through the source file's grandparent. That path is the
checkout in a working copy and a directory beside `site-packages` in an
installed one, so the installed package imported and then read neither: the
schema raised `FileNotFoundError`, and `load_all()` returned an empty registry
without raising at all, under which every row is refused as `structure.unknown`
for a fault in the package rather than in the row.

WHY THIS RUNS THE PACKAGE OUT OF A COPY RATHER THAN OUT OF A WHEEL. Building and
installing a wheel reaches the package index, and every leg of the default gate
decides from bytes in the checkout so that a contributor with no network runs
all of it. `tools/package.py --install` does the real thing on the `package`
check name and is out of the default run for exactly that reason. What is left
for the suite is the property that fails underneath it: the package away from
this tree, with only the files a wheel would carry, reading both directories.

So the copy is not "src/findbuch with some files": it is the modules plus
exactly what `[tool.setuptools.package-data]` declares, read out of
pyproject.toml rather than written here. A data file added to the package and
left out of that table is therefore absent from this copy, and the probe below
fails the same way the wheel would. That is the one-line mistake this exists
against.

AND THE COPY IS PROVEN TO BITE. `TheProbeRefusesWhenTheDataDidNotTravel` runs
the identical procedure over a copy with the data directory removed and requires
it to fail. Without that row, a probe that had stopped asking anything would
report a working package and look exactly like one.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_SOURCE = REPO_ROOT / "src" / "findbuch"

# The same three questions tools/package.py asks in the fresh environment, in a
# shape this file parses back. It is a string rather than a module under tools/
# because it runs under an interpreter that has this repository nowhere on its
# path, which is the whole point of running it at all.
PROBE = """
import findbuch
print("module " + findbuch.__file__)
from findbuch.validation import SCHEMA_PATH, load_schema
print("schema " + str(SCHEMA_PATH.is_file()))
print("schema-id " + str(load_schema().get("$id", "")))
from findbuch.structures import STRUCTURES, load_all
print("structures " + str(STRUCTURES.is_dir()))
print("registry " + str(len(load_all())))
"""


def declared_data_patterns() -> list[str]:
    """What pyproject.toml says the wheel carries beside the modules."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        configuration = tomllib.load(handle)
    patterns = configuration["tool"]["setuptools"]["package-data"]["findbuch"]
    return [str(pattern) for pattern in patterns]


def declared_data_files() -> set[Path]:
    """Every file under the package that a declared pattern matches."""
    matched: set[Path] = set()
    for pattern in declared_data_patterns():
        matched.update(path for path in PACKAGE_SOURCE.glob(pattern) if path.is_file())
    return matched


def carried_files() -> set[Path]:
    """The modules plus the declared data, which is what a wheel holds."""
    modules = {path for path in PACKAGE_SOURCE.rglob("*.py") if path.is_file()}
    return modules | declared_data_files()


def lay_out_a_package(destination: Path) -> Path:
    """Copy what a wheel would carry into `destination/findbuch`."""
    root = destination / "findbuch"
    for source in sorted(carried_files()):
        target = root / source.relative_to(PACKAGE_SOURCE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return root


def probe(destination: Path) -> subprocess.CompletedProcess[str]:
    """Import the copied package with this tree nowhere on the path.

    The environment is built rather than inherited whole: PYTHONPATH is set to
    the copy alone, so the copy is ahead of the path entry the editable install
    adds, and the working directory is the copy for the same reason. The
    interpreter is this one, because the runtime dependencies are installed for
    it and resolving those again is not what this file is about.
    """
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(destination)
    return subprocess.run(
        [sys.executable, "-c", PROBE],
        capture_output=True,
        text=True,
        check=False,
        cwd=destination,
        env=environment,
    )


def answers(output: str) -> dict[str, str]:
    return {
        line.split(" ", 1)[0]: line.split(" ", 1)[1]
        for line in output.splitlines()
        if " " in line
    }


class TheDeclaredDataCoversEveryNonModuleFileInThePackage(unittest.TestCase):
    """A data file the table does not name is a file the wheel does not carry.

    This is the cheap half and it runs without starting anything. It reads the
    package directory and the table, and refuses a file that is in one and not
    the other. The probe below would also catch it, but only for a file
    something imports on the way to an answer.
    """

    def test_every_file_that_is_not_a_module_is_declared(self) -> None:
        present = {
            path
            for path in PACKAGE_SOURCE.rglob("*")
            if path.is_file()
            and path.suffix != ".py"
            and "__pycache__" not in path.parts
        }
        undeclared = sorted(
            str(path.relative_to(PACKAGE_SOURCE).as_posix())
            for path in present - declared_data_files()
        )
        self.assertEqual(
            undeclared,
            [],
            "these files sit under src/findbuch and no pattern in "
            "[tool.setuptools.package-data] matches them, so a wheel would not "
            "carry them and the installed package could not read them",
        )

    def test_the_table_names_something_that_is_there(self) -> None:
        # The other direction. A pattern matching nothing is a declaration that
        # has quietly stopped covering anything, and it looks identical to one
        # that covers everything.
        for pattern in declared_data_patterns():
            with self.subTest(pattern=pattern):
                self.assertNotEqual(
                    sorted(PACKAGE_SOURCE.glob(pattern)),
                    [],
                    f"no file under src/findbuch matches '{pattern}'",
                )


class ThePackageAwayFromThisTreeReadsBothDirectories(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.destination = Path(self.workspace.name)
        lay_out_a_package(self.destination)
        self.result = probe(self.destination)
        self.answered = answers(self.result.stdout)

    def test_the_probe_ran_against_the_copy_and_not_against_this_tree(self) -> None:
        # Without this the whole class could pass by importing the checkout,
        # which is the state #84 describes and would be indistinguishable from
        # the repair.
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        imported = Path(self.answered["module"]).resolve()
        self.assertEqual(imported.parent.parent, self.destination.resolve())

    def test_the_schema_is_readable(self) -> None:
        self.assertEqual(self.answered.get("schema"), "True")

    def test_the_schema_that_was_read_is_the_row_schema(self) -> None:
        # `is_file` is a claim about a path. This is a claim about the bytes: the
        # loader opened them, parsed them as JSON, and what came back declares
        # itself to be the row schema.
        self.assertIn("row-1.0.schema.json", self.answered.get("schema-id", ""))

    def test_the_structure_directory_is_readable(self) -> None:
        self.assertEqual(self.answered.get("structures"), "True")

    def test_the_registry_is_not_empty(self) -> None:
        # The half that does not raise. An empty registry is a legal value, so
        # this is asserted as a number rather than left to an exception that
        # would never come.
        self.assertNotEqual(self.answered.get("registry"), "0")
        self.assertGreater(int(self.answered["registry"]), 0)


class TheProbeRefusesWhenTheDataDidNotTravel(unittest.TestCase):
    """The same procedure over a copy with the data removed must fail.

    One change from the class above: the data directory is deleted after the
    copy is laid out. If this passed, the class above would be proving that a
    subprocess exits zero rather than that anything travelled.
    """

    def setUp(self) -> None:
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.destination = Path(self.workspace.name)
        root = lay_out_a_package(self.destination)
        shutil.rmtree(root / "data")
        self.result = probe(self.destination)
        self.answered = answers(self.result.stdout)

    def test_the_import_still_succeeds_which_is_why_the_import_proves_nothing(
        self,
    ) -> None:
        self.assertIn("module ", self.result.stdout)

    def test_reading_the_schema_refuses(self) -> None:
        self.assertNotEqual(self.result.returncode, 0)
        self.assertEqual(self.answered.get("schema"), "False")
        self.assertIn("FileNotFoundError", self.result.stderr)


if __name__ == "__main__":
    unittest.main()
