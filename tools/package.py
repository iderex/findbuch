"""Build the artefact, install it somewhere fresh, and write its bill of materials.

#51. Three questions that read as one and are not, which is why this file has
three phases and the workflow beside it has three check names.

THE FIRST IS WHETHER THE TREE BUILDS. `build` runs the PyPA front end over the
backend `pyproject.toml` already declares, with `--no-isolation`, so the backend
comes from requirements-package.lock with a hash behind it. The default mode
makes an isolated environment and resolves setuptools from the index unpinned,
which would leave the one step that turns this tree into an artefact as the one
step in the project that installs something nothing hashed.

THE SECOND IS WHETHER WHAT IT BUILT WORKS, AND IT IS A DIFFERENT QUESTION. A
distribution that builds and does not install is an ordinary outcome, so the
wheel goes into a fresh interpreter and is imported there. A wheel is imported
from `site-packages` and never from `src/`, which is the whole reason for the
fresh environment: run from the checkout, `import findbuch` succeeds whatever
the wheel contains.

WHAT THE IMPORT DOES NOT ANSWER, and this is the sentence to read twice. The
package reads two directories that are not Python: the row schema and the
Poisson structure files. Both are addressed today through a path computed from
the source file's grandparent, which is the repository root in a checkout and a
directory beside `site-packages` in an installed environment, and neither
directory is in the wheel. So an installed package imports and then cannot read
its own schema, and `findbuch.structures.load_all()` returns an empty registry
rather than raising, under which every row is refused as `structure.unknown` for
a fault in the package. `install` MEASURES both and PRINTS what it found. It
does not refuse them, because the repair is a change to how the package is laid
out rather than to this file, and it is #84. What is here is the measurement, so
that the repair has something to move and a green tick on this leg is not read
as saying the data travelled.

THE THIRD IS WHAT THE ARTEFACT IS MADE OF. `sbom` writes a CycloneDX document
from `requirements.lock`, which is the resolved runtime set rather than the
environment this file happens to be running in, and then validates the document
it just wrote against the CycloneDX schema of the version it declared. Writing
and validating are separate steps on purpose: the writer is asked not to
validate, so the validation below is a check on the writer rather than the
writer reporting on itself.

EXIT STATUS COMES FROM THE PROCESS THAT DECIDED. Every subprocess is a list
handed to `subprocess.run` and read back through its own `returncode`. No shell,
so no pipe, so nothing can report success on behalf of a step that refused.

Run the three phases:

    python tools/package.py --build
    python tools/package.py --install
    python tools/package.py --sbom

Run the proof that the second and third refuse what they name:

    python tools/package.py --selftest

`--build`, `--install` and `--sbom` all reach the package index. That is why
none of them is in the gate's default run. `--selftest` does not: it makes its
environment with `--without-pip` and reads a fixture pair out of the tree, so it
runs first in the jobs below and the verdicts after it are worth reading only
because it passed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST = REPO_ROOT / "dist"
RUNTIME_LOCK = REPO_ROOT / "requirements.lock"
SBOM = DIST / "sbom.cdx.json"

# The pair the self-test validates, one change apart: the same document with and
# without a field the format requires. Files rather than strings in this source,
# for the reason the suite's own fixtures are files, and the smaller of the two
# is the one that must be refused.
SBOM_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "sbom"
SBOM_NEIGHBOUR = SBOM_FIXTURES / "neighbour.json"
SBOM_TRIPS = SBOM_FIXTURES / "trips.json"

# The CycloneDX version this project writes and validates against. It is written
# here rather than left to the writer's default, because the document carries the
# version inside it and a validator reading a different one would either refuse a
# good document or accept a field the declared version does not have.
SCHEMA_VERSION = "1.6"

# What the installed package reads and is not Python. Each entry is measured by
# `install` in the fresh environment, and the reason it is measured rather than
# assumed is the module docstring above.
PACKAGE_DATA: tuple[tuple[str, str, str], ...] = (
    ("schema", "the row schema", "findbuch.validation.SCHEMA_PATH"),
    ("structures", "the Poisson structure files", "findbuch.structures.STRUCTURES"),
)


@dataclass(frozen=True)
class Refusal:
    """One reason a phase refused, carrying the identifier a test asserts on."""

    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class Outcome:
    """What one subprocess did, kept whole so a caller can print it."""

    returncode: int
    output: str

    @property
    def refused(self) -> bool:
        return self.returncode != 0


def run(command: Sequence[str], cwd: Path | None = None) -> Outcome:
    """Run a command as a list, capture both streams, keep its own status."""
    completed = subprocess.run(
        list(command),
        cwd=cwd or REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return Outcome(completed.returncode, completed.stdout + completed.stderr)


def interpreter_of(environment: Path) -> Path:
    """The interpreter inside a virtual environment, on either layout."""
    windows = environment / "Scripts" / "python.exe"
    return windows if windows.exists() else environment / "bin" / "python"


def make_environment(directory: Path, with_pip: bool) -> Path:
    """Create a fresh environment and return its interpreter.

    `with_pip` is false wherever nothing is going to be installed, which is what
    keeps the self-test off the network.
    """
    command = [sys.executable, "-m", "venv"]
    if not with_pip:
        command.append("--without-pip")
    command.append(str(directory))
    outcome = run(command)
    if outcome.refused:
        print(outcome.output)
        raise SystemExit("package: could not create an environment to install into")
    return interpreter_of(directory)


# The probe the fresh environment runs. It imports the package, then asks each
# data path whether it is there, and prints one line per answer in a shape the
# caller parses back. It is a string rather than a file under tools/ because it
# has to run under an interpreter that has this repository nowhere on its path.
PROBE = """
import findbuch
print("import-ok " + findbuch.__file__)
from findbuch.validation import SCHEMA_PATH
print("schema " + str(SCHEMA_PATH.is_file()) + " " + str(SCHEMA_PATH))
from findbuch.structures import STRUCTURES, load_all
print("structures " + str(STRUCTURES.is_dir()) + " " + str(STRUCTURES))
print("registry " + str(len(load_all())))
"""


def build() -> int:
    """Build the sdist and the wheel from the checkout, and say what appeared."""
    if DIST.exists():
        shutil.rmtree(DIST)

    print(f"=== building from {REPO_ROOT}", flush=True)
    outcome = run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--sdist",
            "--wheel",
            "--outdir",
            str(DIST),
        ]
    )
    print(outcome.output)
    if outcome.refused:
        print(Refusal("package.build-failed", "the build front end refused"))
        return 1

    wheels = sorted(DIST.glob("*.whl"))
    sdists = sorted(DIST.glob("*.tar.gz"))
    for kind, found in (("wheel", wheels), ("sdist", sdists)):
        if len(found) != 1:
            names = ", ".join(path.name for path in found) or "nothing"
            print(
                Refusal(
                    f"package.no-{kind}",
                    f"expected exactly one {kind} in {DIST}, found {names}",
                )
            )
            return 1

    for path in (*sdists, *wheels):
        print(f"built {path.name}  {path.stat().st_size} bytes")
    return 0


def the_wheel() -> Path | None:
    wheels = sorted(DIST.glob("*.whl"))
    return wheels[0] if len(wheels) == 1 else None


def install() -> int:
    """Install the built wheel into a fresh environment and import it there."""
    wheel = the_wheel()
    if wheel is None:
        print(
            Refusal(
                "package.no-wheel",
                f"no single wheel in {DIST}; run --build first",
            )
        )
        return 1

    with tempfile.TemporaryDirectory() as workspace:
        python = make_environment(Path(workspace) / "fresh", with_pip=True)

        print(f"=== installing the locked runtime set into {python.parent}")
        locked = run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--require-hashes",
                "--requirement",
                str(RUNTIME_LOCK),
            ]
        )
        print(locked.output)
        if locked.refused:
            print(Refusal("package.install-failed", "the locked runtime set refused"))
            return 1

        print(f"=== installing {wheel.name}")
        # --no-deps, because the dependencies came from the lockfile above with
        # a hash behind each one. Letting the wheel pull its own would resolve
        # the same names again, unhashed, and the environment that imports would
        # no longer be the environment that was locked.
        installed = run([str(python), "-m", "pip", "install", "--no-deps", str(wheel)])
        print(installed.output)
        if installed.refused:
            print(Refusal("package.install-failed", f"{wheel.name} did not install"))
            return 1

        return report_probe(run([str(python), "-c", PROBE]))


def report_probe(probe: Outcome) -> int:
    """Read the probe back: refuse on the import, measure and print the rest."""
    print(probe.output)
    if probe.refused:
        print(Refusal("package.import-failed", "the installed package did not import"))
        return 1

    answers = {
        line.split(" ", 1)[0]: line.split(" ", 1)[1]
        for line in probe.output.splitlines()
        if " " in line
    }
    print("=== what the installed package can reach, measured rather than assumed")
    for key, description, name in PACKAGE_DATA:
        print(f"  {description} ({name}): {answers.get(key, 'not measured')}")
    loaded = answers.get("registry", "not measured")
    print(f"  structures the registry loaded: {loaded}")
    print(
        "  NOT REFUSED HERE. #84 carries the repair; this leg measures and this "
        "line is why a green tick above does not say the data travelled."
    )
    return 0


def write_sbom() -> int:
    """Write the bill of materials, then validate what was written."""
    DIST.mkdir(parents=True, exist_ok=True)
    print(f"=== writing a CycloneDX {SCHEMA_VERSION} document from {RUNTIME_LOCK.name}")
    # --no-validate on purpose: the writer is not asked to report on itself. The
    # validation below is a separate read of the bytes that were written.
    written = run(
        [
            sys.executable,
            "-m",
            "cyclonedx_py",
            "requirements",
            str(RUNTIME_LOCK),
            "--of",
            "JSON",
            "--sv",
            SCHEMA_VERSION,
            "--output-reproducible",
            "-o",
            str(SBOM),
            "--no-validate",
        ]
    )
    print(written.output)
    if written.refused or not SBOM.is_file():
        print(Refusal("package.sbom-failed", "the writer produced no document"))
        return 1

    text = SBOM.read_text(encoding="utf-8")
    refusal = validate_sbom(text)
    if refusal is not None:
        print(refusal)
        return 1

    document = json.loads(text)
    components = len(document.get("components", []))
    print(f"validated {SBOM.name} against CycloneDX {SCHEMA_VERSION}")
    declared = document.get("bomFormat"), document.get("specVersion")
    print(f"  bomFormat={declared[0]} specVersion={declared[1]}")
    print(f"  components: {components}")
    if components == 0:
        print(
            Refusal(
                "package.sbom-empty",
                "the document validates and describes nothing, which is what a "
                "bill of materials generated from an unresolved set looks like",
            )
        )
        return 1
    return 0


def validate_sbom(text: str) -> Refusal | None:
    """Validate a document against the CycloneDX schema, and say which one."""
    from cyclonedx.schema import SchemaVersion
    from cyclonedx.validation.json import JsonStrictValidator

    version = SchemaVersion.from_version(SCHEMA_VERSION)
    error = JsonStrictValidator(version).validate_str(text)
    if error is None:
        return None
    # The first line only. A schema violation carries the whole schema behind
    # it, and a refusal a reader has to scroll past is one they stop reading.
    first = str(error).splitlines()[0]
    return Refusal(
        "package.sbom-invalid",
        f"the document does not validate against CycloneDX {SCHEMA_VERSION}: {first}",
    )


def selftest() -> int:
    """Prove the two refusals that a green run would otherwise only assert.

    Neither row reaches the network. The first makes an environment with no pip
    and nothing installed; the second reads a document already in `dist/`.
    """
    failures = 0

    print("=== an environment the wheel was not installed into must refuse")
    with tempfile.TemporaryDirectory() as workspace:
        python = make_environment(Path(workspace) / "empty", with_pip=False)
        probe = run([str(python), "-c", PROBE])
        if report_probe(probe) == 0:
            print("FAIL  the import check passed where nothing was installed")
            failures += 1
        else:
            print("ok    refused package.import-failed")

    print("\n=== a document with a required field removed must fail validation")
    good = SBOM_NEIGHBOUR.read_text(encoding="utf-8")
    if validate_sbom(good) is not None:
        print(f"FAIL  {SBOM_NEIGHBOUR.name} did not validate")
        failures += 1
    else:
        print(f"ok    {SBOM_NEIGHBOUR.name} validates")

    refusal = validate_sbom(SBOM_TRIPS.read_text(encoding="utf-8"))
    if refusal is None:
        print(f"FAIL  {SBOM_TRIPS.name} validated, and it has no bomFormat")
        failures += 1
    else:
        print(f"ok    refused {refusal.code}")

    if failures:
        print(f"\npackage: self-test REFUSED, {failures} row(s) wrong")
        return 1
    print("\npackage: self-test, every row as expected")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and package this project.")
    parser.add_argument("--build", action="store_true", help="build sdist and wheel")
    parser.add_argument(
        "--install",
        action="store_true",
        help="install the built wheel into a fresh environment and import it",
    )
    parser.add_argument(
        "--sbom",
        action="store_true",
        help="write the bill of materials and validate it",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="the three phases in order, which is what the gate leg runs",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="prove the import check and the validation refuse what they name",
    )
    arguments = parser.parse_args(argv)

    phases = []
    if arguments.all or arguments.build:
        phases.append(build)
    if arguments.all or arguments.install:
        phases.append(install)
    if arguments.all or arguments.sbom:
        phases.append(write_sbom)
    if arguments.selftest:
        phases.append(selftest)
    if not phases:
        parser.error("nothing asked for; pass --build, --install, --sbom or --all")

    for phase in phases:
        code = phase()
        if code != 0:
            print(f"\npackage: REFUSED by {phase.__name__}")
            return code
    print("\npackage: every phase that ran was clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
