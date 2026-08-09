"""What the supply-chain checks decide without reaching the network.

#53. The tool has two halves and they are testable in different places, so the
split is written here rather than discovered.

WHAT THIS MODULE COVERS: the rule that a lockfile names one version per
requirement and hashes it, the register of accepted advisories and its expiry,
and the shape of every subprocess the tool builds. All of that is a function of
bytes in this tree and is decided offline, which is why it is in the suite the
gate runs.

WHAT THIS MODULE DOES NOT COVER, said here so that a green suite is not read as
the whole check: whether pip refuses a tampered lockfile and whether the scanner
refuses a pin with known advisories. Both are answered by processes that fetch,
they are the `--selftest` verb of tools/supply_chain.py, and they run in
.github/workflows/supply-chain.yml rather than here. A suite that reached the
network would fail on the machine of anybody working offline and would be the
first thing removed.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import ast
import datetime as dt
import difflib
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import supply_chain  # noqa: E402

TODAY = dt.date(2026, 8, 9)


def write(text: str) -> Path:
    """A register on disk, because read_exceptions reads a path and not a string.

    The path is what the tool takes, so handing it a string here would test a
    function this project does not have.
    """
    target = Path(tempfile.mkdtemp()) / "vulnerability-exceptions.toml"
    target.write_text(text, encoding="utf-8")
    return target


class TheRealLockfilesAreReadBeforeAnythingIsClaimedAboutThem(unittest.TestCase):
    """A reader that recovered nothing would make every case below vacuous."""

    def test_every_lockfile_named_by_the_tool_is_in_the_tree(self) -> None:
        for path in supply_chain.LOCKFILES:
            with self.subTest(lockfile=path.name):
                self.assertTrue(path.is_file(), f"{path} is not a file")

    def test_the_reader_recovers_a_plausible_number_of_requirements(self) -> None:
        for path in supply_chain.LOCKFILES:
            with self.subTest(lockfile=path.name):
                found = supply_chain.requirements_in(path.read_text(encoding="utf-8"))
                self.assertGreater(len(found), 3)
                for _, name, specifier, hashes in found:
                    self.assertTrue(name)
                    self.assertTrue(specifier)
                    self.assertGreater(hashes, 0)


class EveryRequirementNamesOneVersionAndCarriesAHash(unittest.TestCase):
    def test_the_committed_lockfiles_are_accepted(self) -> None:
        for path in supply_chain.LOCKFILES:
            with self.subTest(lockfile=path.name):
                refusals = supply_chain.check_pinned(
                    path.read_text(encoding="utf-8"), path.name
                )
                self.assertEqual([str(refusal) for refusal in refusals], [])

    def test_a_loosened_pin_is_refused_by_identifier(self) -> None:
        # The case measured to walk straight through `pip --require-hashes`,
        # which is the whole reason this rule is in the tool rather than left to
        # pip. tools/supply_chain.py says so at the top and this is the assertion
        # behind that sentence.
        text = supply_chain.LOCKFILES[0].read_text(encoding="utf-8")
        loosened = supply_chain.loosen_the_pin(text, supply_chain.MUTATED)
        codes = {
            refusal.code for refusal in supply_chain.check_pinned(loosened, "loosened")
        }
        self.assertEqual(codes, {"lock.unpinned"})

    def test_an_entry_with_no_hash_is_refused_by_identifier(self) -> None:
        text = supply_chain.LOCKFILES[0].read_text(encoding="utf-8")
        dropped = supply_chain.drop_the_hashes(text, supply_chain.MUTATED)
        codes = {
            refusal.code for refusal in supply_chain.check_pinned(dropped, "dropped")
        }
        self.assertEqual(codes, {"lock.unhashed"})

    def test_a_file_with_no_hash_anywhere_is_refused_for_every_entry(self) -> None:
        # The case pip's own flag is for, and the one this rule has to catch on
        # its own if the flag is ever dropped from the command.
        text = supply_chain.LOCKFILES[0].read_text(encoding="utf-8")
        stripped = supply_chain.drop_every_hash(text, supply_chain.MUTATED)
        refusals = supply_chain.check_pinned(stripped, "stripped")
        self.assertEqual({refusal.code for refusal in refusals}, {"lock.unhashed"})
        self.assertEqual(len(refusals), len(supply_chain.requirements_in(text)))

    def test_the_refusal_names_the_requirement_it_is_about(self) -> None:
        text = supply_chain.LOCKFILES[0].read_text(encoding="utf-8")
        loosened = supply_chain.loosen_the_pin(text, supply_chain.MUTATED)
        stated = " ".join(
            str(refusal) for refusal in supply_chain.check_pinned(loosened, "loosened")
        )
        self.assertIn(supply_chain.MUTATED, stated)


class EachMutationIsOneChangeToTheRealLockfile(unittest.TestCase):
    """A mutation with four differences proves something other than the mistake.

    The same argument tests/test_refused_corpus.py makes for its pairs. Here the
    neighbour is the committed lockfile itself, so the comparison is against the
    file the check runs over rather than against a stored copy that drifts.
    """

    def test_exactly_one_stretch_of_lines_differs(self) -> None:
        text = supply_chain.LOCKFILES[0].read_text(encoding="utf-8")
        for mutation in supply_chain.MUTATIONS:
            if not mutation.contiguous:
                # Declared rather than skipped in silence. The case that is not
                # contiguous is a whole-file edit by construction, and its own
                # entry says why.
                continue
            with self.subTest(mutation=mutation.name):
                mutated = mutation.apply(text, supply_chain.MUTATED)
                self.assertNotEqual(mutated, text, "the mutation changed nothing")
                edits = [
                    opcode
                    for opcode in difflib.SequenceMatcher(
                        None, text.splitlines(), mutated.splitlines()
                    ).get_opcodes()
                    if opcode[0] != "equal"
                ]
                self.assertEqual(len(edits), 1)

    def test_every_mutation_changes_the_lockfile(self) -> None:
        text = supply_chain.LOCKFILES[0].read_text(encoding="utf-8")
        for mutation in supply_chain.MUTATIONS:
            with self.subTest(mutation=mutation.name):
                self.assertNotEqual(mutation.apply(text, supply_chain.MUTATED), text)

    def test_only_the_declared_case_is_allowed_to_be_a_whole_file_edit(self) -> None:
        scattered = [m.name for m in supply_chain.MUTATIONS if not m.contiguous]
        self.assertEqual(scattered, ["every-hash-dropped"])

    def test_every_mutation_names_who_has_to_refuse_it(self) -> None:
        for mutation in supply_chain.MUTATIONS:
            with self.subTest(mutation=mutation.name):
                self.assertLessEqual(mutation.refused_by, {"pip", "this file"})
                self.assertNotEqual(mutation.refused_by, frozenset())
                self.assertTrue(mutation.what.strip())

    def test_the_two_refusers_are_both_load_bearing(self) -> None:
        # If every mutation named the same refuser, one of the two halves would
        # be carrying nothing and the self-test would not say so.
        named = {
            who for mutation in supply_chain.MUTATIONS for who in mutation.refused_by
        }
        self.assertEqual(named, {"pip", "this file"})


class AnAcceptedAdvisoryCarriesAReasonAndRunsOut(unittest.TestCase):
    def test_a_live_entry_is_returned_and_suppresses(self) -> None:
        path = write(
            '[[exception]]\nid = "PYSEC-0000-1"\n'
            'reason = "no fixed release exists yet"\nexpires = 2026-12-31\n'
        )
        live, refusals = supply_chain.read_exceptions(path, TODAY)
        self.assertEqual([entry.identifier for entry in live], ["PYSEC-0000-1"])
        self.assertEqual(refusals, [])

    def test_an_expired_entry_stops_suppressing_and_is_refused(self) -> None:
        path = write(
            '[[exception]]\nid = "PYSEC-0000-2"\n'
            'reason = "waiting on the upstream release"\nexpires = 2026-01-01\n'
        )
        live, refusals = supply_chain.read_exceptions(path, TODAY)
        self.assertEqual(live, [])
        self.assertEqual({refusal.code for refusal in refusals}, {"exception.expired"})
        # Both halves matter. Dropping it puts the advisory back in front of the
        # scan, and refusing it says the register still carries a row nobody
        # revisited, which is what an expiry is for.
        self.assertIn("PYSEC-0000-2", str(refusals[0]))

    def test_an_entry_with_no_expiry_is_refused(self) -> None:
        path = write('[[exception]]\nid = "PYSEC-0000-3"\nreason = "accepted"\n')
        live, refusals = supply_chain.read_exceptions(path, TODAY)
        self.assertEqual(live, [])
        self.assertEqual(
            {refusal.code for refusal in refusals}, {"exception.no-expiry"}
        )

    def test_an_entry_with_no_reason_is_refused(self) -> None:
        path = write('[[exception]]\nid = "PYSEC-0000-4"\nexpires = 2026-12-31\n')
        live, refusals = supply_chain.read_exceptions(path, TODAY)
        self.assertEqual(live, [])
        self.assertEqual(
            {refusal.code for refusal in refusals}, {"exception.incomplete"}
        )

    def test_the_register_in_the_tree_is_readable_and_carries_nothing_expired(
        self,
    ) -> None:
        self.assertTrue(supply_chain.EXCEPTIONS.is_file())
        _, refusals = supply_chain.read_exceptions(
            supply_chain.EXCEPTIONS, dt.datetime.now(tz=dt.UTC).date()
        )
        self.assertEqual([str(refusal) for refusal in refusals], [])


class NoVerdictHereIsReadOffTheEndOfAPipe(unittest.TestCase):
    """The mistake #53 names, refused at the source rather than remembered.

    A scan piped into anything reports the exit status of the last command in the
    pipe, so a scanner that refused leaves a green step and a check that looks
    exactly like one that works.
    """

    def test_no_subprocess_is_run_through_a_shell(self) -> None:
        # Read as a syntax tree rather than as text. A grep would also match the
        # prose in the module's own docstring, which is where the rule is
        # explained, and a test that its explanation satisfies is not a test.
        tree = ast.parse(Path(supply_chain.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                with self.subTest(keyword=keyword.arg):
                    self.assertNotEqual(
                        keyword.arg,
                        "shell",
                        "a shell here would put a pipe between the process that "
                        "decided and the status this tool reads",
                    )
            self.assertNotEqual(ast.unparse(node.func), "os.system")

    def test_every_command_the_tool_builds_is_a_list_of_arguments(self) -> None:
        # Built rather than run: what is asserted is the shape of the argument
        # vector, and running either of these would reach the network.
        commands = [
            supply_chain.scan_command(
                list(supply_chain.LOCKFILES), ["PYSEC-0000-1", "PYSEC-0000-2"]
            ),
            supply_chain.locked_install_command(supply_chain.LOCKFILES[0]),
        ]
        for command in commands:
            with self.subTest(command=command[:3]):
                self.assertIsInstance(command, list)
                for argument in command:
                    self.assertIsInstance(argument, str)
                    # A pipe or a redirection inside an argument would only be
                    # read as one by a shell, and there is no shell here; this
                    # says the arguments do not rely on one either.
                    self.assertNotIn("|", argument)
                    self.assertNotIn(">", argument)

    def test_every_accepted_advisory_reaches_the_scanner(self) -> None:
        ignored = ["PYSEC-0000-1", "PYSEC-0000-2"]
        command = supply_chain.scan_command(list(supply_chain.LOCKFILES), ignored)
        for identifier in ignored:
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, command)
                self.assertEqual(
                    command[command.index(identifier) - 1], "--ignore-vuln"
                )

    def test_every_lockfile_reaches_the_scanner(self) -> None:
        command = supply_chain.scan_command(list(supply_chain.LOCKFILES), [])
        for path in supply_chain.LOCKFILES:
            with self.subTest(lockfile=path.name):
                self.assertIn(str(path), command)

    def test_an_outcome_reports_the_status_of_the_process_it_came_from(self) -> None:
        self.assertTrue(supply_chain.Outcome(1, "").refused)
        self.assertTrue(supply_chain.Outcome(2, "").refused)
        self.assertFalse(supply_chain.Outcome(0, "").refused)


if __name__ == "__main__":
    unittest.main()
