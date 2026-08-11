"""The schema and the validator refuse a malformed row, and say what was wrong.

Every case here is a one-change neighbour of the valid fixture: the fixture is
loaded, one thing is changed, and the refusal identifier is asserted. A test that
only asserted "something was refused" would pass on a validator that refused
everything, which is the failure this shape exists against.

Standard library `unittest`, for the reason given in test_package_tree.py.
"""

import copy
import tomllib
import unittest
from pathlib import Path
from typing import Any

from findbuch import validation
from findbuch.validation import (
    SCHEMA_PATH,
    Refusal,
    StructureRegistry,
    validate_file,
    validate_row,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
VALID_ROW = FIXTURES / "rows" / "euler.toml"


def registry() -> StructureRegistry:
    return StructureRegistry.from_directory(FIXTURES / "structures")


def valid_document() -> dict[str, Any]:
    with VALID_ROW.open("rb") as handle:
        loaded: dict[str, Any] = tomllib.load(handle)
    return loaded


def codes(refusals: list[Refusal]) -> set[str]:
    return {refusal.code for refusal in refusals}


def messages(refusals: list[Refusal]) -> str:
    return " | ".join(refusal.message for refusal in refusals)


class TheSchemaIsPublishedAtAStablePath(unittest.TestCase):
    def test_the_schema_file_is_tracked_where_the_export_can_point_at_it(self) -> None:
        self.assertTrue(SCHEMA_PATH.is_file())
        self.assertEqual(
            SCHEMA_PATH.parent,
            REPO_ROOT / "src" / "findbuch" / "data" / "schema",
        )
        self.assertEqual(SCHEMA_PATH.name, "row-1.0.schema.json")

    def test_the_path_is_addressed_through_the_package_and_not_through_the_root(
        self,
    ) -> None:
        # The constant used to be built from the source file's grandparent, which
        # is the checkout in a working copy and a directory beside
        # `site-packages` in an installed one, so the schema was unreadable
        # wherever the package was installed rather than checked out. Asserting
        # the file exists says nothing about that, because in a checkout the old
        # path existed too. What the property is, is that the schema sits under
        # the directory the module itself is in. #84 measured the other case and
        # tests/test_package_data.py runs the package away from this tree.
        module = Path(validation.__file__).resolve().parent
        self.assertEqual(SCHEMA_PATH.parents[2], module)


class AWellFormedRowIsAccepted(unittest.TestCase):
    def test_the_fixture_row_validates(self) -> None:
        result = validate_file(VALID_ROW, registry())
        self.assertEqual([str(r) for r in result.refusals], [])
        self.assertTrue(result.valid)

    def test_the_undeclared_parameter_rule_actually_ran_on_it(self) -> None:
        # Otherwise every parameter case below would be passing by not running.
        result = validate_file(VALID_ROW, registry())
        self.assertTrue(result.parameters_rule_evaluated)


class AMissingRequiredFieldIsRefusedByName(unittest.TestCase):
    def test_each_required_field_is_named_in_its_own_refusal(self) -> None:
        required = [
            "id",
            "name",
            "structure",
            "hamiltonian",
            "parameters",
            "validity",
            "domain",
            "provenance",
        ]
        for field in required:
            with self.subTest(field=field):
                document = valid_document()
                del document[field]
                refusals = validate_row(
                    document, file_stem="euler", registry=registry()
                )
                self.assertIn("schema.missing-field", codes(refusals))
                self.assertIn(f"'{field}'", messages(refusals))

    def test_the_neighbour_with_the_field_present_loads(self) -> None:
        document = valid_document()
        self.assertEqual(
            validate_row(document, file_stem="euler", registry=registry()), []
        )


class AnUnknownStructureIsRefusedByName(unittest.TestCase):
    def test_the_structure_is_named_in_the_message(self) -> None:
        document = valid_document()
        document["structure"] = "e4"
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertEqual(codes(refusals), {"structure.unknown"})
        self.assertIn("'e4'", messages(refusals))

    def test_the_known_structures_are_listed_so_the_fix_is_visible(self) -> None:
        document = valid_document()
        document["structure"] = "e4"
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertIn("e3", messages(refusals))
        self.assertIn("so4", messages(refusals))

    def test_the_one_change_neighbour_that_names_a_real_structure_loads(self) -> None:
        document = valid_document()
        document["structure"] = "so4"
        refusals = validate_row(document, file_stem="euler", registry=registry())
        # so4 has no g coordinates, so the hamiltonian's symbols are all
        # parameters or declared; the row is well formed against it.
        self.assertEqual(codes(refusals), set())


class ConstraintsAreRequiredExactlyWhenTheKindRequiresThem(unittest.TestCase):
    def test_conditional_without_constraints_is_refused(self) -> None:
        document = valid_document()
        document["validity"] = "conditional"
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertIn("validity.constraints-missing", codes(refusals))

    def test_conditional_with_constraints_loads(self) -> None:
        document = valid_document()
        document["validity"] = "conditional"
        document["constraints"] = ["M1*g1 + M2*g2 + M3*g3"]
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertEqual(codes(refusals), set())

    def test_general_with_constraints_is_refused(self) -> None:
        document = valid_document()
        document["constraints"] = ["M1*g1 + M2*g2 + M3*g3"]
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertIn("validity.constraints-refused", codes(refusals))

    def test_invariant_relation_carrying_an_integral_is_refused(self) -> None:
        document = valid_document()
        document["validity"] = "invariant-relation"
        document["constraints"] = ["M1*g1 + M2*g2 + M3*g3"]
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertIn("validity.integral-on-invariant-relation", codes(refusals))

    def test_invariant_relation_without_an_integral_loads(self) -> None:
        document = valid_document()
        document["validity"] = "invariant-relation"
        document["constraints"] = ["M1*g1 + M2*g2 + M3*g3"]
        document["integrals"] = []
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertEqual(codes(refusals), set())

    def test_a_kind_outside_the_three_is_refused(self) -> None:
        document = valid_document()
        document["validity"] = "generally"
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertIn("schema.enum", codes(refusals))


class TheParameterListIsNotEmptyWhereTheHamiltonianUsesOne(unittest.TestCase):
    def test_an_empty_parameter_list_under_a_parametrised_hamiltonian(self) -> None:
        document = valid_document()
        document["parameters"] = []
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertIn("parameters.undeclared", codes(refusals))
        self.assertIn("A1", messages(refusals))

    def test_an_empty_parameter_list_under_a_bare_hamiltonian_loads(self) -> None:
        document = valid_document()
        document["parameters"] = []
        document["hamiltonian"] = "M1*M1 + M2*M2 + M3*M3"
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertEqual(codes(refusals), set())

    def test_the_rule_does_not_run_when_the_structure_declares_no_coordinates(
        self,
    ) -> None:
        empty = StructureRegistry.from_directory(FIXTURES / "rows")
        document = valid_document()
        document["parameters"] = []
        document["structure"] = "euler"
        refusals = validate_row(document, file_stem="euler", registry=empty)
        self.assertNotIn("parameters.undeclared", codes(refusals))


class TheIdentifierAndTheFileNameAreTheSameThing(unittest.TestCase):
    def test_a_mismatch_is_refused(self) -> None:
        document = valid_document()
        refusals = validate_row(document, file_stem="euler-1758", registry=registry())
        self.assertIn("id.mismatches-file-name", codes(refusals))

    def test_a_malformed_identifier_is_refused_by_the_schema(self) -> None:
        document = valid_document()
        document["id"] = "Euler Case"
        refusals = validate_row(document, file_stem="Euler Case", registry=registry())
        self.assertIn("schema.pattern", codes(refusals))


class ASupersededRowPointsSomewhere(unittest.TestCase):
    def test_superseded_without_a_pointer_is_refused(self) -> None:
        document = valid_document()
        document["status"] = "superseded"
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertIn("status.superseded-without-pointer", codes(refusals))

    def test_superseded_with_a_pointer_loads(self) -> None:
        document = valid_document()
        document["status"] = "superseded"
        document["superseded_by"] = "euler-corrected"
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertEqual(codes(refusals), set())


class ProvenanceIsRequiredAndIsChecked(unittest.TestCase):
    def test_an_empty_provenance_list_is_refused(self) -> None:
        document = valid_document()
        document["provenance"] = []
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertIn("schema.minItems", codes(refusals))

    def test_an_entry_missing_its_notation_is_refused_by_name(self) -> None:
        document = valid_document()
        del document["provenance"][0]["notation"]
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertIn("schema.missing-field", codes(refusals))
        self.assertIn("'notation'", messages(refusals))

    def test_a_role_outside_the_three_is_refused(self) -> None:
        document = valid_document()
        document["provenance"][0]["role"] = "secondary"
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertIn("schema.enum", codes(refusals))


class AFieldNobodyDeclaredIsRefused(unittest.TestCase):
    def test_an_unknown_top_level_field(self) -> None:
        document = valid_document()
        document["hamiltonain"] = document["hamiltonian"]
        refusals = validate_row(document, file_stem="euler", registry=registry())
        self.assertIn("schema.additionalProperties", codes(refusals))
        self.assertIn("hamiltonain", messages(refusals))


class TheValidatorDoesNotMutateWhatItReads(unittest.TestCase):
    def test_the_document_is_unchanged(self) -> None:
        document = valid_document()
        before = copy.deepcopy(document)
        validate_row(document, file_stem="euler", registry=registry())
        self.assertEqual(document, before)


if __name__ == "__main__":
    unittest.main()
