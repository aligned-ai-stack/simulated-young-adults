from __future__ import annotations

import random
import secrets
import uuid
from dataclasses import dataclass
from typing import Any


YOUNG_ADULT_AGE_MIN = 18
YOUNG_ADULT_AGE_MAX = 29

FIRST_NAMES = [
    "Aaliyah",
    "Alex",
    "Amara",
    "Ava",
    "Ethan",
    "Isabella",
    "Jayden",
    "Jordan",
    "Maya",
    "Noah",
    "Riley",
    "Sofia",
]

LAST_NAMES = [
    "Anderson",
    "Brown",
    "Carter",
    "Garcia",
    "Johnson",
    "Kim",
    "Lee",
    "Martinez",
    "Patel",
    "Robinson",
    "Smith",
    "Williams",
]

STREET_NAMES = [
    "Maple",
    "Oak",
    "Pine",
    "Cedar",
    "Elmwood",
    "Riverside",
    "Hillcrest",
    "Lakeview",
]

US_CITIES = [
    {"city": "Little Rock", "state": "AR", "region": "West South Central"},
    {"city": "Austin", "state": "TX", "region": "West South Central"},
    {"city": "Phoenix", "state": "AZ", "region": "Mountain"},
    {"city": "Columbus", "state": "OH", "region": "East North Central"},
    {"city": "Raleigh", "state": "NC", "region": "South Atlantic"},
    {"city": "Madison", "state": "WI", "region": "East North Central"},
    {"city": "Portland", "state": "OR", "region": "Pacific"},
    {"city": "Philadelphia", "state": "PA", "region": "Middle Atlantic"},
    {"city": "Denver", "state": "CO", "region": "Mountain"},
    {"city": "Atlanta", "state": "GA", "region": "South Atlantic"},
]

MARGINALS: dict[str, list[Any]] = {
    "country": ["US", "US", "US", "CA", "GB", "NL", "DE", "AU"],
    "region_type": ["large_city", "large_city", "suburb", "small_city", "rural_area"],
    "gender": ["woman", "man", "nonbinary", "prefer_not_to_say"],
    "sex": ["Female", "Male", "Male", "Female", "Intersex", "Prefer not to say"],
    "ethnicity": ["American only", "American only", "Mexican American", "Puerto Rican", "Other"],
    "race": ["White", "White", "Black or African American", "Asian", "Multiracial", "Other"],
    "detailed_race": [
        "White",
        "Black or African American",
        "Chinese",
        "Asian Indian",
        "Korean",
        "Vietnamese",
        "Multiracial",
        "Other",
    ],
    "hispanic_origin": ["Not Hispanic", "Not Hispanic", "Mexican", "Puerto Rican", "Cuban", "Other Hispanic"],
    "education": [
        "high_school_or_equivalent",
        "some_college",
        "undergraduate",
        "vocational_training",
        "bachelors_degree",
        "graduate_student",
    ],
    "highest_degree_received": [
        "Less than high school",
        "High school",
        "Some college",
        "Associate degree",
        "Bachelor's degree",
        "Graduate degree",
    ],
    "nationality": ["US", "US", "US", "Canadian", "British", "Dutch", "German", "Australian"],
    "political_views": [
        "Very liberal",
        "Liberal",
        "Slightly liberal",
        "Moderate",
        "Slightly conservative",
        "Conservative",
        "Very conservative",
    ],
    "party_identification": [
        "Democrat",
        "Independent, close to democrat",
        "Independent",
        "Independent, close to republican",
        "Republican",
        "Other party",
        "No preference",
    ],
    "same_residence_since_16": ["Same city", "Same state", "Different state", "Different country"],
    "family_structure_at_16": [
        "Lived with parents",
        "Lived with mother only",
        "Lived with father only",
        "Lived with relatives",
        "Other arrangement",
    ],
    "family_income_at_16": ["Far below average", "Below average", "Average", "Above average", "Far above average"],
    "fathers_highest_degree": [
        "Less than high school",
        "High school",
        "Some college",
        "Bachelor's degree",
        "Graduate degree",
        "Unknown",
    ],
    "mothers_highest_degree": [
        "Less than high school",
        "High school",
        "Some college",
        "Bachelor's degree",
        "Graduate degree",
        "Unknown",
    ],
    "mothers_work_history": ["Yes", "No", "Part-time", "Not sure"],
    "marital_status": ["Never married", "Married", "Separated", "Divorced", "Living with partner"],
    "student_status": ["undergraduate", "undergraduate", "graduate_student", "not_student"],
    "employment_status": [
        "part_time",
        "part_time",
        "full_time",
        "not_currently_employed",
        "gig_or_freelance",
    ],
    "work_status": [
        "Working full-time",
        "Working part-time",
        "With a job, but not at work because of temporary illness, vacation, strike",
        "Unemployed, looking for work",
        "Student",
        "Keeping house",
        "Other",
    ],
    "military_service_duration": ["No active duty", "Less than 2 years", "2-4 years", "More than 4 years"],
    "religion": [
        "None",
        "Catholic",
        "Protestant",
        "Other Christian",
        "Jewish",
        "Muslim",
        "Hindu",
        "Buddhist",
        "Other",
    ],
    "religion_at_16": [
        "None",
        "Catholic",
        "Protestant",
        "Other Christian",
        "Jewish",
        "Muslim",
        "Hindu",
        "Buddhist",
        "Other",
    ],
    "born_in_us": ["Yes", "Yes", "No"],
    "us_citizenship_status": [
        "A U.S. citizen",
        "A U.S. citizen",
        "Permanent resident",
        "Temporary visa holder",
        "Not a U.S. citizen",
    ],
    "speak_other_language": ["No", "No", "Yes"],
    "other_language": ["Spanish", "French", "Mandarin", "Hindi", "Arabic", "German", "None"],
    "total_wealth": [
        "Less than $5,000",
        "$5,000 to $24,999",
        "$25,000 to $49,999",
        "$50,000 to $99,999",
        "$100,000 to $249,999",
        "$250,000 or more",
        "Prefer not to say",
    ],
    "living_situation": [
        "with_roommates",
        "with_family",
        "alone",
        "with_partner",
        "student_housing",
    ],
    "relationship_status": ["single", "dating", "in_relationship", "prefer_not_to_say"],
    "household_income_band": [
        "low",
        "lower_middle",
        "middle",
        "upper_middle",
        "prefer_not_to_say",
    ],
    "digital_habits": [
        "heavy_social_media",
        "moderate_social_media",
        "privacy_conscious",
        "creator_or_poster",
        "mostly_messaging",
    ],
    "personality_texture": [
        "reflective",
        "practical",
        "socially_oriented",
        "skeptical",
        "optimistic",
        "low_energy",
    ],
    "survey_style": [
        "concise",
        "conversational",
        "slightly_uncertain",
        "detail_oriented",
        "casual",
    ],
    "attention_level": ["high", "medium", "medium", "low"],
    "ai_literacy": [1, 2, 3, 3, 4, 4, 5, 6, 7],
    "ai_literacy_level": ["low", "medium", "medium", "high"],
    "ai_trust": [1, 2, 3, 3, 4, 4, 5, 6, 7],
    "baseline_trust_in_ai": [1, 2, 3, 3, 4, 4, 5, 6, 7],
    "ai_familiarity": [1, 2, 3, 4, 4, 5, 6, 7],
    "ai_skepticism": [1, 2, 3, 4, 4, 5, 6, 7],
    "openness_to_change": [1, 2, 3, 4, 4, 5, 6, 7],
    "topic_familiarity": [1, 2, 3, 4, 4, 5, 6, 7],
    "initial_opinion_strength": [1, 2, 3, 4, 4, 5, 6, 7],
    "initial_opinion_confidence": [1, 2, 3, 4, 4, 5, 6, 7],
    "prior_ai_use": ["none", "rare", "occasional", "occasional", "frequent"],
    "online_content_skepticism": ["low", "moderate", "moderate", "high"],
    "attention_to_detail": ["low", "medium", "medium", "high"],
    "prior_exposure_to_misinformation": ["low", "medium", "medium", "high"],
    "general_confidence": [1, 2, 3, 4, 4, 5, 5, 6, 7],
    "openness_to_new_information": ["low", "moderate", "moderate", "high"],
    "reasoning_style": ["analytical", "mixed", "mixed", "intuitive"],
    "initial_climate_lifestyle_view": [1, 2, 3, 4, 4, 5, 6, 7],
    "knowledge_geography_history": [1, 2, 3, 4, 4, 5, 6, 7],
    "knowledge_science_health": [1, 2, 3, 4, 4, 5, 6, 7],
    "knowledge_entertainment_literature": [1, 2, 3, 4, 4, 5, 6, 7],
    "knowledge_technology_internet": [1, 2, 3, 4, 4, 5, 6, 7],
    "resilience_under_distraction": [1, 2, 3, 4, 4, 5, 6, 7],
    "cognitive_capacity": [1, 2, 3, 4, 4, 5, 6, 7],
    "working_memory": [1, 2, 3, 4, 4, 5, 6, 7],
}

CRITERIA_ALIASES = {
    "state": "state",
    "us_state": "state",
    "highest_degree": "highest_degree_received",
    "degree": "highest_degree_received",
    "employment": "work_status",
    "party": "party_identification",
}


@dataclass(frozen=True)
class PersonaSample:
    persona_id: str
    seed: int
    attributes: dict[str, Any]


class PersonaSampler:
    """Samples synthetic personas while keeping unspecified fields independent."""

    def sample(
        self,
        criteria: dict[str, Any] | None = None,
        conditioned_attributes: dict[str, Any] | None = None,
        random_seed: int | None = None,
    ) -> PersonaSample:
        seed = random_seed if random_seed is not None else secrets.randbits(63)
        rng = random.Random(seed)
        criteria = criteria or {}
        conditioned_attributes = conditioned_attributes or {}
        criteria = self._normalize_keys(criteria)
        conditioned_attributes = self._normalize_keys(conditioned_attributes)

        attributes: dict[str, Any] = {}
        attributes["age"] = self._sample_age(rng, criteria, conditioned_attributes)
        attributes.update(self._sample_identity_and_location(rng, criteria, conditioned_attributes))

        for name, values in MARGINALS.items():
            if name in attributes:
                continue
            if name in conditioned_attributes:
                attributes[name] = conditioned_attributes[name]
            else:
                attributes[name] = self._sample_attribute(rng, name, values, criteria)

        unknown_conditioned = set(conditioned_attributes) - set(attributes)
        for name in sorted(unknown_conditioned):
            attributes[name] = conditioned_attributes[name]

        return PersonaSample(
            persona_id=f"persona_{uuid.uuid4().hex[:12]}",
            seed=seed,
            attributes=attributes,
        )

    def _normalize_keys(self, values: dict[str, Any]) -> dict[str, Any]:
        return {
            CRITERIA_ALIASES.get(key, key): value
            for key, value in values.items()
        }

    def _sample_identity_and_location(
        self,
        rng: random.Random,
        criteria: dict[str, Any],
        conditioned_attributes: dict[str, Any],
    ) -> dict[str, Any]:
        first_name = conditioned_attributes.get("first_name", rng.choice(FIRST_NAMES))
        last_name = conditioned_attributes.get("last_name", rng.choice(LAST_NAMES))
        city_record = self._sample_city(rng, criteria, conditioned_attributes)
        street_number = conditioned_attributes.get("street_number", rng.randint(100, 9999))
        street_name = conditioned_attributes.get("street_name", rng.choice(STREET_NAMES))
        street_address = conditioned_attributes.get(
            "street_address",
            f"{street_number} {street_name} {rng.choice(['St', 'Ave', 'Drive', 'Lane'])} (synthetic)",
        )
        residence_at_16 = conditioned_attributes.get(
            "residence_at_16",
            rng.choice([
                city_record["region"],
                city_record["region"],
                "New England",
                "Middle Atlantic",
                "South Atlantic",
                "Pacific",
                "Mountain",
            ]),
        )
        return {
            "first_name": first_name,
            "last_name": last_name,
            "street_address": street_address,
            "city": city_record["city"],
            "state": city_record["state"],
            "residence_at_16": residence_at_16,
        }

    def _sample_city(
        self,
        rng: random.Random,
        criteria: dict[str, Any],
        conditioned_attributes: dict[str, Any],
    ) -> dict[str, str]:
        if "city" in conditioned_attributes or "state" in conditioned_attributes:
            city = conditioned_attributes.get("city")
            state = conditioned_attributes.get("state")
            matching = [
                record
                for record in US_CITIES
                if (city is None or record["city"] == city)
                and (state is None or record["state"] == state)
            ]
            if matching:
                return rng.choice(matching)
            return {
                "city": city or "Unknown City",
                "state": state or "NA",
                "region": conditioned_attributes.get("residence_at_16", "Unknown"),
            }

        state_criterion = criteria.get("state")
        if state_criterion is not None:
            allowed_states = state_criterion if isinstance(state_criterion, list) else [state_criterion]
            matching = [record for record in US_CITIES if record["state"] in allowed_states]
            if not matching:
                raise ValueError(f"state criteria have no supported eligible values: {state_criterion!r}")
            return rng.choice(matching)

        return rng.choice(US_CITIES)

    def _sample_age(
        self,
        rng: random.Random,
        criteria: dict[str, Any],
        conditioned_attributes: dict[str, Any],
    ) -> int:
        if "age" in conditioned_attributes:
            age = int(conditioned_attributes["age"])
            if age < YOUNG_ADULT_AGE_MIN or age > YOUNG_ADULT_AGE_MAX:
                raise ValueError("conditioned age must be between 18 and 29")
            return age

        min_age = YOUNG_ADULT_AGE_MIN
        max_age = YOUNG_ADULT_AGE_MAX
        age_criteria = criteria.get("age")

        if isinstance(age_criteria, dict):
            min_age = max(min_age, int(age_criteria.get("min", min_age)))
            max_age = min(max_age, int(age_criteria.get("max", max_age)))
        elif isinstance(age_criteria, int):
            min_age = max_age = age_criteria
        elif isinstance(age_criteria, list) and age_criteria:
            eligible = [
                int(age)
                for age in age_criteria
                if YOUNG_ADULT_AGE_MIN <= int(age) <= YOUNG_ADULT_AGE_MAX
            ]
            if not eligible:
                raise ValueError("age criteria do not overlap young-adult range 18-29")
            return rng.choice(eligible)

        if min_age > max_age:
            raise ValueError("age criteria do not overlap young-adult range 18-29")
        return rng.randint(min_age, max_age)

    def _sample_attribute(
        self,
        rng: random.Random,
        name: str,
        values: list[Any],
        criteria: dict[str, Any],
    ) -> Any:
        criterion = criteria.get(name)
        if criterion is None:
            return rng.choice(values)

        if isinstance(criterion, list):
            eligible = [value for value in values if value in criterion]
            if not eligible:
                raise ValueError(f"{name} criteria have no supported eligible values")
            return rng.choice(eligible)

        if criterion in values:
            return criterion

        raise ValueError(f"unsupported {name} criterion: {criterion!r}")
