"""The mutation run decides one thing, and this is the pair that proves it can.

What tools/mutation_sample.py decides is whether a suite noticed a mutant. A
tool that reported every mutant killed would look exactly like a tree whose
tests are thorough, and it is the same failure shape as a checker that has
stopped refusing: green, for a reason nobody checked.

So the fixture pair changes the SUITE and not the subject. Both directories
under tests/fixtures/mutation hold the same guard, byte for byte, and one
mutant is derived from it. The suite in `trips` asserts the boundary that
mutant moves and has to kill it; the suite in `neighbour` asserts one value
past the boundary and has to let it live. A tool that always answered KILLED
fails on the neighbour and one that always answered SURVIVED fails on the trip,
so neither constant answer passes this file.

The fixtures are copied into a temporary directory before anything runs. The
tool writes the mutant into the module in place, which is right for a checkout
and wrong for a tracked fixture: a suite that mutated the tree it is stored in
would leave the repository dirty the one time the restore failed.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import ast
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "mutation"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "mutation.yml"

sys.path.insert(0, str(REPO_ROOT / "tools"))

import coverage_bar  # noqa: E402
import mutation_sample  # noqa: E402

# The one mutant the guard yields, written here as the key the register uses so
# that a change to either spelling shows up as a failure rather than as a case
# that quietly stopped matching.
THE_MUTANT = ("guard.py", "return value < 10", "<", "<=")


@contextmanager
def laid_out(case: str) -> Iterator[Path]:
    """Copy one fixture case into a directory the tool may write in."""
    with tempfile.TemporaryDirectory(prefix="findbuch-mutation-") as into:
        root = Path(into)
        for name in ("guard", "suite"):
            source = FIXTURES / case / f"{name}.py.txt"
            if source.is_file():
                shutil.copyfile(source, root / f"{name}.py")
        yield root


@contextmanager
def accepted(key: tuple[str, str, str, str], reason: str) -> Iterator[None]:
    """Hold one entry in the register for the length of a block.

    The register is module state and the cases below need it to hold three
    different things. A case that left an entry behind would decide the verdict
    of whichever case ran next.
    """
    mutation_sample.ACCEPTED_SURVIVORS[key] = reason
    try:
        yield
    finally:
        mutation_sample.ACCEPTED_SURVIVORS.pop(key, None)


@contextmanager
def patched_surface(surface: dict[str, str]) -> Iterator[None]:
    """Stand a different gated list in front of the tool for one block."""
    original = dict(coverage_bar.VERDICT_SURFACE)
    coverage_bar.VERDICT_SURFACE.clear()
    coverage_bar.VERDICT_SURFACE.update(surface)
    try:
        yield
    finally:
        coverage_bar.VERDICT_SURFACE.clear()
        coverage_bar.VERDICT_SURFACE.update(original)


def suite_command(root: Path) -> list[str]:
    return [sys.executable, str(root / "suite.py")]


class BothFixturesWereReadBeforeAnythingIsClaimed(unittest.TestCase):
    """A pair that did not load would make every outcome below vacuous."""

    def test_the_two_guards_are_the_same_bytes(self) -> None:
        trips = (FIXTURES / "trips" / "guard.py.txt").read_bytes()
        neighbour = (FIXTURES / "neighbour" / "guard.py.txt").read_bytes()
        self.assertEqual(trips, neighbour, "the pair differs in its subject")

    def test_the_two_suites_differ(self) -> None:
        trips = (FIXTURES / "trips" / "suite.py.txt").read_bytes()
        neighbour = (FIXTURES / "neighbour" / "suite.py.txt").read_bytes()
        self.assertNotEqual(trips, neighbour)

    def test_both_suites_pass_over_the_unmutated_guard(self) -> None:
        # A neighbour that was already red would survive nothing: the tool
        # would answer KILLED for a reason that has nothing to do with the
        # mutant, and the trip half of this file would pass by accident.
        for case in ("trips", "neighbour"):
            with self.subTest(case=case), laid_out(case) as root:
                completed = subprocess.run(
                    suite_command(root),
                    cwd=root,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_exactly_one_mutant_is_derived_from_the_guard(self) -> None:
        source = (FIXTURES / "trips" / "guard.py.txt").read_text(encoding="utf-8")
        mutants = mutation_sample.mutants_in(source, "guard.py")
        self.assertEqual(len(mutants), 1, [m.describe() for m in mutants])
        self.assertEqual(mutants[0].key, THE_MUTANT)


class TheSameMutantDiesUnderOneSuiteAndLivesUnderTheOther(unittest.TestCase):
    def outcome_for(self, case: str) -> str:
        with laid_out(case) as root:
            mutant = mutation_sample.population(root, ["guard.py"])[0]
            outcome, _ = mutation_sample.run_one(
                root, mutant, suite_command(root), timeout=60
            )
            return outcome

    def test_the_suite_that_asserts_the_boundary_kills_it(self) -> None:
        self.assertEqual(self.outcome_for("trips"), mutation_sample.KILLED)

    def test_the_suite_one_value_past_the_boundary_lets_it_live(self) -> None:
        self.assertEqual(self.outcome_for("neighbour"), mutation_sample.SURVIVED)


class TheModuleIsPutBackAfterwards(unittest.TestCase):
    def test_the_bytes_are_what_they_were_once_the_mutant_has_run(self) -> None:
        with laid_out("trips") as root:
            before = (root / "guard.py").read_bytes()
            mutant = mutation_sample.population(root, ["guard.py"])[0]
            mutation_sample.run_one(root, mutant, suite_command(root), timeout=60)
            self.assertEqual((root / "guard.py").read_bytes(), before)

    def test_the_module_is_put_back_even_when_the_suite_cannot_be_run(self) -> None:
        # The restore is in a finally. A suite command that does not exist is
        # the cheapest way to reach it by a path that is not the happy one.
        with laid_out("trips") as root:
            before = (root / "guard.py").read_bytes()
            mutant = mutation_sample.population(root, ["guard.py"])[0]
            with self.assertRaises(OSError):
                mutation_sample.run_one(
                    root, mutant, [str(root / "no-such-command")], timeout=60
                )
            self.assertEqual((root / "guard.py").read_bytes(), before)


class AnEmptyPopulationIsARefusalAndNotAGreenRun(unittest.TestCase):
    def test_a_module_the_table_matches_nothing_in_is_refused(self) -> None:
        with laid_out("nothing-to-mutate") as root:
            verdict = mutation_sample.run(
                root=root,
                modules=["guard.py"],
                suite=[sys.executable, "-c", ""],
                seed=1,
                size=1,
                timeout=60,
            )
            self.assertEqual(verdict, 1)

    def test_a_surface_that_is_not_in_the_tree_is_refused(self) -> None:
        with laid_out("trips") as root:
            verdict = mutation_sample.run(
                root=root,
                modules=["not-in-this-tree.py"],
                suite=[sys.executable, "-c", ""],
                seed=1,
                size=1,
                timeout=60,
            )
            self.assertEqual(verdict, 1)


class TheRegisterOfAcceptedSurvivorsFailsClosedInBothDirections(unittest.TestCase):
    def test_an_unaccepted_survivor_refuses(self) -> None:
        with laid_out("neighbour") as root:
            verdict = mutation_sample.run(
                root=root,
                modules=["guard.py"],
                suite=suite_command(root),
                seed=1,
                size=None,
                timeout=60,
            )
            self.assertEqual(verdict, 1)

    def test_the_same_survivor_passes_once_it_is_accepted_with_a_reason(self) -> None:
        with laid_out("neighbour") as root:
            with accepted(THE_MUTANT, "the fixture that proves acceptance works"):
                verdict = mutation_sample.run(
                    root=root,
                    modules=["guard.py"],
                    suite=suite_command(root),
                    seed=1,
                    size=None,
                    timeout=60,
                )
            self.assertEqual(verdict, 0)

    def test_an_acceptance_of_a_mutant_the_suite_kills_refuses_as_stale(self) -> None:
        with laid_out("trips") as root:
            with accepted(THE_MUTANT, "a debt this suite has already paid"):
                verdict = mutation_sample.run(
                    root=root,
                    modules=["guard.py"],
                    suite=suite_command(root),
                    seed=1,
                    size=None,
                    timeout=60,
                )
            self.assertEqual(verdict, 1)

    def test_an_acceptance_naming_no_mutant_of_this_tree_refuses_as_dangling(
        self,
    ) -> None:
        with laid_out("trips") as root:
            entry = ("guard.py", "a line this fixture does not have", "<", "<=")
            with accepted(entry, "a register entry describing code that is gone"):
                verdict = mutation_sample.run(
                    root=root,
                    modules=["guard.py"],
                    suite=suite_command(root),
                    seed=1,
                    size=None,
                    timeout=60,
                )
            self.assertEqual(verdict, 1)

    def test_every_acceptance_in_the_tool_carries_a_reason(self) -> None:
        for key, reason in mutation_sample.ACCEPTED_SURVIVORS.items():
            with self.subTest(key=key):
                self.assertTrue(reason.strip())


class TheSurfaceHasOneHome(unittest.TestCase):
    def test_the_default_surface_follows_the_gated_list_when_it_moves(self) -> None:
        # Asserted by moving it. A copy taken from the bar at import time would
        # pass any comparison of the two lists as they stand today and would go
        # on naming yesterday's modules after somebody edited the bar, which is
        # the way the two go apart in silence.
        with laid_out("trips") as root, patched_surface({"guard.py": "the fixture"}):
            printed = io.StringIO()
            with redirect_stdout(printed):
                verdict = mutation_sample.main(["--root", str(root), "--list"])
            self.assertEqual(verdict, 0)
            self.assertIn("guard.py:11", printed.getvalue())
            self.assertIn("1 mutant(s)", printed.getvalue())

    def test_a_module_the_bar_does_not_gate_is_not_mutated_by_default(self) -> None:
        with laid_out("trips") as root, patched_surface({"absent.py": "not here"}):
            printed = io.StringIO()
            with redirect_stdout(printed):
                verdict = mutation_sample.main(["--root", str(root), "--list"])
            self.assertEqual(verdict, 1)
            self.assertIn("0 mutant(s)", printed.getvalue())

    def test_every_module_on_the_surface_yields_at_least_one_mutant(self) -> None:
        # A module the table matches nothing in would be on the surface and out
        # of every sample, which is the quietest way for a module to leave this
        # check.
        for module in sorted(coverage_bar.VERDICT_SURFACE):
            with self.subTest(module=module):
                source = (REPO_ROOT / module).read_text(encoding="utf-8")
                self.assertNotEqual(mutation_sample.mutants_in(source, module), [])


class ThePopulationIsDerivedTheSameWayTwice(unittest.TestCase):
    def candidates(self) -> list[mutation_sample.Mutant]:
        return mutation_sample.population(
            REPO_ROOT, sorted(coverage_bar.VERDICT_SURFACE)
        )

    def test_the_same_seed_over_the_same_population_chooses_the_same_sample(
        self,
    ) -> None:
        candidates = self.candidates()
        first = mutation_sample.chosen(candidates, seed=55, size=7)
        second = mutation_sample.chosen(candidates, seed=55, size=7)
        self.assertEqual(first, second)

    def test_a_different_seed_chooses_a_different_sample(self) -> None:
        # Not a guarantee about any two seeds. It is asserted over a population
        # large enough that a collision would mean the seed is not reaching the
        # choice at all.
        candidates = self.candidates()
        self.assertGreater(len(candidates), 50)
        first = mutation_sample.chosen(candidates, seed=55, size=7)
        second = mutation_sample.chosen(candidates, seed=56, size=7)
        self.assertNotEqual(first, second)

    def test_every_admitted_mutant_is_a_python_file(self) -> None:
        # The table swaps tokens and a token carries no grammar with it. A
        # candidate that only produced a syntax error would be a mutant nothing
        # could kill, counted against the suite for a reason that is this
        # tool's rather than the suite's.
        for module in sorted(coverage_bar.VERDICT_SURFACE):
            source = (REPO_ROOT / module).read_text(encoding="utf-8")
            for mutant in mutation_sample.mutants_in(source, module):
                with self.subTest(mutant=mutant.describe()):
                    ast.parse(mutation_sample.spliced(source, mutant), module)


class TheSampleSizeAndTheSeedHaveOneHome(unittest.TestCase):
    def test_the_workflow_passes_neither_number(self) -> None:
        # The size and the seed are declared in tools/mutation_sample.py with
        # the reason for each value. A second copy in the workflow moves apart
        # from them in silence, and the job would then be sampling a different
        # number from the one a contributor reproduces with.
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("--sample", text)
        self.assertNotIn("--seed", text)

    def test_the_workflow_runs_the_tool(self) -> None:
        self.assertIn("tools/mutation_sample.py", WORKFLOW.read_text(encoding="utf-8"))

    def test_the_job_produces_the_name_the_parity_mapping_asks_for(self) -> None:
        self.assertIn("name: mutation sample\n", WORKFLOW.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
