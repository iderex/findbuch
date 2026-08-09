"""The three structures load, and their Casimirs are checked rather than trusted.

0002 decided that the Poisson structure is data, that the three members of the
family are one file each with one parameter fixed, and that the Casimirs are
declared and then checked. The declaration is what makes them convenient. This
file is what makes them safe, and 0002 says neither is optional.

WHAT EACH CHECK CATCHES, because the three are not interchangeable. Antisymmetry
catches a transposed sign in one entry of the table. The Jacobi identity catches
a sign that is consistent between the two halves of a pair and wrong against the
rest of the table, which antisymmetry cannot see. The Casimir check catches a
declared invariant that is not one, and that is the one with teeth: the numeric
leg measures drift against these, so a wrong Casimir does not produce a red row,
it produces a noise floor that quietly means nothing.

THE MUTATION IS IN THE SUITE RATHER THAN ONLY IN A PULL REQUEST BODY. A copy of
the family file with one sign turned over is built in a temporary directory and
loaded, and the failures it produces are asserted. A demonstration that lives
only in a body is a demonstration that stops being re-run the day after it is
written.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

import sympy

from findbuch.structures import (
    PoissonStructure,
    StructureRefused,
    antisymmetry_failures,
    casimir_failures,
    every_failure,
    jacobi_failures,
    load_all,
    load_structure,
)
from findbuch.validation import StructureRegistry

REPO_ROOT = Path(__file__).resolve().parent.parent
STRUCTURES = REPO_ROOT / "structures"
FAMILIES = STRUCTURES / "family"
FAMILY_FILE = FAMILIES / "rigid-body.toml"

# The three 0002 names, with the parameter each one fixes.
EXPECTED = {"e3": 0, "so4": 1, "so31": -1}


def loaded() -> dict[str, PoissonStructure]:
    return load_all(STRUCTURES)


class TheThreeStructuresExistAndLoad(unittest.TestCase):
    def test_the_directory_holds_exactly_the_three(self) -> None:
        self.assertEqual(sorted(loaded()), sorted(EXPECTED))

    def test_each_one_fixes_its_own_parameter(self) -> None:
        for identifier, value in EXPECTED.items():
            with self.subTest(structure=identifier):
                self.assertEqual(loaded()[identifier].parameter_value, value)

    def test_the_family_file_is_not_loadable_as_a_structure(self) -> None:
        # It lives in a subdirectory for this reason: a family with its parameter
        # still free has no bracket a checker can evaluate, and a directory scan
        # that picked it up would hand one out.
        self.assertNotIn("rigid-body", loaded())
        self.assertTrue(FAMILY_FILE.is_file())

    def test_the_three_share_one_table_and_differ_only_where_the_parameter_is(
        self,
    ) -> None:
        structures = loaded()
        differ = [
            pair
            for pair in structures["e3"].table
            if structures["e3"].entry(*pair) != structures["so4"].entry(*pair)
        ]
        # Six ordered entries, the two-vector block off its diagonal, and nothing
        # else. A fourth structure added later that moved anything outside this
        # set would not be a member of this family.
        self.assertEqual(len(differ), 6)
        for left, right in differ:
            with self.subTest(pair=(left, right)):
                self.assertTrue(left.startswith("g") and right.startswith("g"))


class TheBracketIsAntisymmetricAndSatisfiesJacobi(unittest.TestCase):
    def test_antisymmetry_on_every_ordered_pair(self) -> None:
        for identifier, structure in loaded().items():
            with self.subTest(structure=identifier):
                self.assertEqual(antisymmetry_failures(structure), [])

    def test_the_jacobi_identity_on_every_triple(self) -> None:
        for identifier, structure in loaded().items():
            with self.subTest(structure=identifier):
                self.assertEqual(jacobi_failures(structure), [])

    def test_the_checks_were_run_over_something_rather_than_over_nothing(
        self,
    ) -> None:
        # Both functions above return an empty list for a structure with no
        # coordinates, which is the same answer they give for a correct one.
        for identifier, structure in loaded().items():
            with self.subTest(structure=identifier):
                self.assertEqual(len(structure.coordinates), 6)
                self.assertEqual(len(structure.table), 36)


class TheDeclaredCasimirsAreCasimirs(unittest.TestCase):
    def test_each_declared_casimir_brackets_to_zero_with_every_generator(
        self,
    ) -> None:
        for identifier, structure in loaded().items():
            with self.subTest(structure=identifier):
                self.assertEqual(casimir_failures(structure), [])

    def test_two_casimirs_are_declared_on_each_structure(self) -> None:
        for identifier, structure in loaded().items():
            with self.subTest(structure=identifier):
                self.assertEqual(len(structure.casimirs), 2)

    def test_the_area_constant_is_the_one_a_conditional_case_sets_to_zero(
        self,
    ) -> None:
        # Named rather than positional, so a reordering of the file does not
        # quietly change what a later leg thinks it is measuring.
        structure = loaded()["e3"]
        area = next(c for c in structure.casimirs if c.name == "the area constant")
        symbols = {name: sympy.Symbol(name) for name in structure.coordinates}
        expected = (
            symbols["M1"] * symbols["g1"]
            + symbols["M2"] * symbols["g2"]
            + symbols["M3"] * symbols["g3"]
        )
        self.assertEqual(sympy.expand(area.built - expected), 0)


class ATransposedSignIsCaught(unittest.TestCase):
    """The mistake that will actually be made, made on purpose."""

    def mutated(self, before: str, after: str) -> PoissonStructure:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        (directory / "family").mkdir()
        text = FAMILY_FILE.read_text(encoding="utf-8")
        self.assertIn(before, text)
        (directory / "family" / "rigid-body.toml").write_text(
            text.replace(before, after, 1), encoding="utf-8"
        )
        shutil.copy(STRUCTURES / "so4.toml", directory / "so4.toml")
        return load_structure(directory / "so4.toml", directory / "family")

    def test_one_entry_transposed_against_its_partner_fails_antisymmetry(
        self,
    ) -> None:
        structure = self.mutated(
            '{ left = "M1", right = "M2", value = "M3" }',
            '{ left = "M1", right = "M2", value = "-M3" }',
        )
        failures = antisymmetry_failures(structure)
        self.assertNotEqual(failures, [])
        self.assertIn("M1", failures[0])
        self.assertIn("antisymmetry", failures[0])

    def test_a_sign_turned_over_on_both_halves_passes_antisymmetry_and_fails_jacobi(
        self,
    ) -> None:
        # The case antisymmetry cannot see: the pair still agrees with itself and
        # disagrees with the rest of the table. Without the Jacobi leg this
        # table would load clean.
        structure = self.mutated(
            '{ left = "M1", right = "M2", value = "M3" },\n'
            '    { left = "M1", right = "M3", value = "-M2" },\n'
            '    { left = "M2", right = "M1", value = "-M3" },',
            '{ left = "M1", right = "M2", value = "-M3" },\n'
            '    { left = "M1", right = "M3", value = "-M2" },\n'
            '    { left = "M2", right = "M1", value = "M3" },',
        )
        self.assertEqual(antisymmetry_failures(structure), [])
        self.assertNotEqual(jacobi_failures(structure), [])

    def test_a_wrong_casimir_is_caught_where_neither_identity_would_be(
        self,
    ) -> None:
        structure = self.mutated(
            'expression = "M1*g1 + M2*g2 + M3*g3"',
            'expression = "M1*g1 + M2*g2 + 2*M3*g3"',
        )
        self.assertEqual(antisymmetry_failures(structure), [])
        self.assertEqual(jacobi_failures(structure), [])
        failures = casimir_failures(structure)
        self.assertNotEqual(failures, [])
        self.assertIn("is not a Casimir", failures[0])


class AStructureFileIsRefusedByIdentifier(unittest.TestCase):
    def written(self, name: str, text: str, family: str | None = None) -> Path:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        (directory / "family").mkdir()
        (directory / "family" / "rigid-body.toml").write_text(
            family if family is not None else FAMILY_FILE.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        path = directory / name
        path.write_text(text, encoding="utf-8")
        return path

    def code_of(self, path: Path) -> str:
        with self.assertRaises(StructureRefused) as refused:
            load_structure(path, path.parent / "family")
        return refused.exception.code

    def test_a_missing_file(self) -> None:
        path = self.written("x.toml", "")
        self.assertEqual(
            self.code_of(path.parent / "nothing-here.toml"), "structure.file-missing"
        )

    def test_a_missing_field(self) -> None:
        path = self.written("x.toml", 'name = "no identifier"\n')
        self.assertEqual(self.code_of(path), "structure.missing-field")

    def test_a_family_that_does_not_exist(self) -> None:
        path = self.written("x.toml", 'id = "x"\nfamily = "no-such-family"\n')
        self.assertEqual(self.code_of(path), "structure.family-unknown")

    def test_a_parameter_that_is_not_an_integer(self) -> None:
        path = self.written(
            "x.toml",
            'id = "x"\nfamily = "rigid-body"\nkappa = "one"\n'
            'coordinates = ["M1", "M2", "M3", "g1", "g2", "g3"]\n',
        )
        self.assertEqual(self.code_of(path), "structure.parameter-not-an-integer")

    def test_coordinates_that_disagree_with_the_family(self) -> None:
        path = self.written(
            "x.toml",
            'id = "x"\nfamily = "rigid-body"\nkappa = 0\n'
            'coordinates = ["M1", "M2", "M3"]\n',
        )
        self.assertEqual(
            self.code_of(path), "structure.coordinates-disagree-with-the-family"
        )

    def test_a_bracket_pair_left_out(self) -> None:
        text = FAMILY_FILE.read_text(encoding="utf-8").replace(
            '    { left = "M1", right = "M1", value = "0" },\n', "", 1
        )
        path = self.written(
            "x.toml",
            'id = "x"\nfamily = "rigid-body"\nkappa = 0\n'
            'coordinates = ["M1", "M2", "M3", "g1", "g2", "g3"]\n',
            family=text,
        )
        self.assertEqual(self.code_of(path), "structure.bracket-incomplete")

    def test_a_bracket_pair_declared_twice(self) -> None:
        text = FAMILY_FILE.read_text(encoding="utf-8").replace(
            '    { left = "M1", right = "M2", value = "M3" },\n',
            '    { left = "M1", right = "M2", value = "M3" },\n'
            '    { left = "M1", right = "M2", value = "-M3" },\n',
            1,
        )
        path = self.written(
            "x.toml",
            'id = "x"\nfamily = "rigid-body"\nkappa = 0\n'
            'coordinates = ["M1", "M2", "M3", "g1", "g2", "g3"]\n',
            family=text,
        )
        self.assertEqual(self.code_of(path), "structure.bracket-declared-twice")

    def test_a_bracket_entry_naming_something_that_is_not_a_coordinate(self) -> None:
        text = FAMILY_FILE.read_text(encoding="utf-8").replace(
            '{ left = "M1", right = "M1", value = "0" }',
            '{ left = "M1", right = "M4", value = "0" }',
            1,
        )
        path = self.written(
            "x.toml",
            'id = "x"\nfamily = "rigid-body"\nkappa = 0\n'
            'coordinates = ["M1", "M2", "M3", "g1", "g2", "g3"]\n',
            family=text,
        )
        self.assertEqual(self.code_of(path), "structure.bracket-names-a-stranger")

    def test_a_family_declaring_no_casimir(self) -> None:
        text = FAMILY_FILE.read_text(encoding="utf-8")
        text = text[: text.index("[[casimirs]]")] + "casimirs = []\n"
        path = self.written(
            "x.toml",
            'id = "x"\nfamily = "rigid-body"\nkappa = 0\n'
            'coordinates = ["M1", "M2", "M3", "g1", "g2", "g3"]\n',
            family=text,
        )
        self.assertEqual(self.code_of(path), "structure.no-casimir")

    def test_two_files_declaring_one_identifier(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        (directory / "family").mkdir()
        (directory / "family" / "rigid-body.toml").write_text(
            FAMILY_FILE.read_text(encoding="utf-8"), encoding="utf-8"
        )
        for name in ("a.toml", "b.toml"):
            (directory / name).write_text(
                'id = "same"\nfamily = "rigid-body"\nkappa = 0\n'
                'coordinates = ["M1", "M2", "M3", "g1", "g2", "g3"]\n',
                encoding="utf-8",
            )
        with self.assertRaises(StructureRefused) as refused:
            load_all(directory)
        self.assertEqual(refused.exception.code, "structure.identifier-declared-twice")

    def test_a_directory_that_is_not_there_yields_nothing(self) -> None:
        self.assertEqual(load_all(REPO_ROOT / "no-such-directory"), {})


class TheTwoReadersOfThisDirectoryAgree(unittest.TestCase):
    """A drift this change creates, converted into something a run decides.

    `findbuch.validation.StructureRegistry` reads the same directory for the
    identifiers and coordinates a row is resolved against, and it reads only
    those two things. Two readers of one directory is a thing that drifts, so
    what they share is asserted rather than assumed. Merging them is not this
    change: the registry also resolves against the fixture structures under
    tests/fixtures/, which declare coordinates and no family.
    """

    def test_the_identifiers_and_the_coordinates_are_the_same_on_both_routes(
        self,
    ) -> None:
        registry = StructureRegistry.from_directory(STRUCTURES)
        structures = loaded()
        self.assertEqual(set(registry.identifiers), set(structures))
        for identifier, structure in structures.items():
            with self.subTest(structure=identifier):
                self.assertEqual(
                    registry.coordinates(identifier), structure.coordinates
                )


class EverythingTogether(unittest.TestCase):
    def test_no_structure_in_the_tree_has_any_failure(self) -> None:
        self.assertEqual(every_failure(loaded().values()), [])

    def test_a_broken_structure_is_reported_with_the_identifier_it_came_from(
        self,
    ) -> None:
        # The aggregate is what a later leg will print, so it has to say which
        # structure a failure belongs to. Over one broken structure this is the
        # only thing that distinguishes it from a list of unattributed strings.
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        (directory / "family").mkdir()
        (directory / "family" / "rigid-body.toml").write_text(
            FAMILY_FILE.read_text(encoding="utf-8").replace(
                '{ left = "M1", right = "M2", value = "M3" }',
                '{ left = "M1", right = "M2", value = "-M3" }',
                1,
            ),
            encoding="utf-8",
        )
        shutil.copy(STRUCTURES / "so4.toml", directory / "so4.toml")
        failures = every_failure(load_all(directory).values())
        self.assertNotEqual(failures, [])
        for failure in failures:
            with self.subTest(failure=failure):
                self.assertTrue(failure.startswith("so4: "))


if __name__ == "__main__":
    unittest.main()
