from __future__ import annotations

import unittest

from app.persona import PersonaSampler


class PersonaSamplerTests(unittest.TestCase):
    def test_seed_reproducibly_samples_attributes(self) -> None:
        sampler = PersonaSampler()

        first = sampler.sample(criteria={"age": {"min": 20, "max": 22}}, random_seed=7)
        second = sampler.sample(criteria={"age": {"min": 20, "max": 22}}, random_seed=7)

        self.assertEqual(first.attributes, second.attributes)
        self.assertNotEqual(first.persona_id, second.persona_id)

    def test_conditioned_attributes_override_sampling(self) -> None:
        sample = PersonaSampler().sample(
            conditioned_attributes={"age": 24, "country": "US", "student_status": "not_student"},
            random_seed=99,
        )

        self.assertEqual(sample.attributes["age"], 24)
        self.assertEqual(sample.attributes["country"], "US")
        self.assertEqual(sample.attributes["student_status"], "not_student")

    def test_age_criteria_are_restricted_to_young_adults(self) -> None:
        sample = PersonaSampler().sample(
            criteria={"age": {"min": 26, "max": 40}},
            random_seed=123,
        )

        self.assertGreaterEqual(sample.attributes["age"], 26)
        self.assertLessEqual(sample.attributes["age"], 29)

    def test_invalid_age_criteria_raise(self) -> None:
        with self.assertRaises(ValueError):
            PersonaSampler().sample(criteria={"age": {"min": 30, "max": 40}})

    def test_samples_comprehensive_panel_style_fields(self) -> None:
        sample = PersonaSampler().sample(random_seed=44)

        expected_fields = {
            "first_name",
            "last_name",
            "sex",
            "ethnicity",
            "race",
            "detailed_race",
            "hispanic_origin",
            "street_address",
            "city",
            "state",
            "political_views",
            "party_identification",
            "residence_at_16",
            "same_residence_since_16",
            "family_structure_at_16",
            "family_income_at_16",
            "fathers_highest_degree",
            "mothers_highest_degree",
            "mothers_work_history",
            "marital_status",
            "work_status",
            "military_service_duration",
            "religion",
            "religion_at_16",
            "born_in_us",
            "us_citizenship_status",
            "highest_degree_received",
            "speak_other_language",
            "total_wealth",
        }

        self.assertTrue(expected_fields.issubset(sample.attributes))
        self.assertIn("(synthetic)", sample.attributes["street_address"])

    def test_state_criteria_restrict_location(self) -> None:
        sample = PersonaSampler().sample(criteria={"state": ["AR"]}, random_seed=5)

        self.assertEqual(sample.attributes["state"], "AR")
        self.assertEqual(sample.attributes["city"], "Little Rock")

    def test_conditioned_panel_attributes_override_sampling(self) -> None:
        sample = PersonaSampler().sample(
            conditioned_attributes={
                "first_name": "Ethan",
                "last_name": "Robinson",
                "sex": "Male",
                "race": "White",
                "state": "AR",
                "city": "Little Rock",
                "highest_degree_received": "High school",
                "total_wealth": "Less than $5,000",
            },
            random_seed=12,
        )

        self.assertEqual(sample.attributes["first_name"], "Ethan")
        self.assertEqual(sample.attributes["last_name"], "Robinson")
        self.assertEqual(sample.attributes["sex"], "Male")
        self.assertEqual(sample.attributes["race"], "White")
        self.assertEqual(sample.attributes["state"], "AR")
        self.assertEqual(sample.attributes["city"], "Little Rock")
        self.assertEqual(sample.attributes["highest_degree_received"], "High school")
        self.assertEqual(sample.attributes["total_wealth"], "Less than $5,000")


if __name__ == "__main__":
    unittest.main()
