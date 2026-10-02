from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Iterable, Mapping


Sampler = Callable[[random.Random, Mapping[str, Any]], Any]


@dataclass(frozen=True)
class CausalNode:
    name: str
    parents: tuple[str, ...] = ()
    role: str = "baseline"
    sampler: Sampler | None = None
    public: bool = True


class CausalGraph:
    """Small dependency-free DAG with d-separation and adjustment checks."""

    def __init__(self, nodes: Iterable[CausalNode]) -> None:
        node_list = list(nodes)
        self.nodes = {node.name: node for node in node_list}
        if len(self.nodes) != len(node_list):
            raise ValueError("causal graph contains duplicate node names")
        for node in self.nodes.values():
            missing = set(node.parents) - set(self.nodes)
            if missing:
                raise ValueError(f"{node.name} has missing parents: {sorted(missing)}")
        self.order = self._topological_order()

    def _topological_order(self) -> tuple[str, ...]:
        indegree = {name: len(node.parents) for name, node in self.nodes.items()}
        children = self.children_map()
        ready = [name for name, degree in indegree.items() if degree == 0]
        order: list[str] = []
        while ready:
            name = ready.pop(0)
            order.append(name)
            for child in sorted(children[name]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
        if len(order) != len(self.nodes):
            raise ValueError("causal graph must be acyclic")
        return tuple(order)

    def children_map(self) -> dict[str, set[str]]:
        children = {name: set() for name in self.nodes}
        for node in self.nodes.values():
            for parent in node.parents:
                children[parent].add(node.name)
        return children

    def ancestors(self, names: Iterable[str]) -> set[str]:
        pending = list(names)
        result: set[str] = set()
        while pending:
            name = pending.pop()
            self._require_node(name)
            for parent in self.nodes[name].parents:
                if parent not in result:
                    result.add(parent)
                    pending.append(parent)
        return result

    def descendants(self, names: Iterable[str]) -> set[str]:
        children = self.children_map()
        pending = list(names)
        result: set[str] = set()
        while pending:
            name = pending.pop()
            self._require_node(name)
            for child in sorted(children[name]):
                if child not in result:
                    result.add(child)
                    pending.append(child)
        return result

    def d_separated(
        self,
        left: str | Iterable[str],
        right: str | Iterable[str],
        conditioned: Iterable[str] = (),
    ) -> bool:
        left_set = {left} if isinstance(left, str) else set(left)
        right_set = {right} if isinstance(right, str) else set(right)
        given = set(conditioned)
        for name in left_set | right_set | given:
            self._require_node(name)

        ancestral = left_set | right_set | given
        ancestral |= self.ancestors(ancestral)
        adjacency = {name: set() for name in ancestral}
        for name in ancestral:
            parents = [p for p in self.nodes[name].parents if p in ancestral]
            for parent in parents:
                adjacency[name].add(parent)
                adjacency[parent].add(name)
            for index, first in enumerate(parents):
                for second in parents[index + 1 :]:
                    adjacency[first].add(second)
                    adjacency[second].add(first)

        for name in given:
            for neighbor in list(adjacency.get(name, ())):
                adjacency[neighbor].discard(name)
            adjacency.pop(name, None)

        pending = [name for name in left_set if name in adjacency]
        seen = set(pending)
        while pending:
            current = pending.pop()
            if current in right_set:
                return False
            for neighbor in adjacency[current] - seen:
                seen.add(neighbor)
                pending.append(neighbor)
        return True

    def without_outgoing(self, name: str) -> "CausalGraph":
        self._require_node(name)
        nodes = []
        for node in self.nodes.values():
            parents = tuple(parent for parent in node.parents if parent != name)
            nodes.append(
                CausalNode(
                    name=node.name,
                    parents=parents,
                    role=node.role,
                    sampler=node.sampler,
                    public=node.public,
                )
            )
        return CausalGraph(nodes)

    def adjustment_report(
        self,
        exposure: str,
        outcomes: Iterable[str],
        adjustment_set: Iterable[str] = (),
    ) -> dict[str, Any]:
        outcomes = tuple(outcomes)
        adjusted = set(adjustment_set)
        forbidden_descendants = adjusted & self.descendants({exposure})
        backdoor = self.without_outgoing(exposure)
        separated = {
            outcome: backdoor.d_separated(exposure, outcome, adjusted)
            for outcome in outcomes
        }
        exposure_ancestors = self.ancestors({exposure})
        outcome_ancestors = self.ancestors(outcomes)
        confounders = sorted(exposure_ancestors & outcome_ancestors)
        colliders = sorted(
            name for name, node in self.nodes.items() if len(node.parents) >= 2
        )
        return {
            "exposure": exposure,
            "outcomes": list(outcomes),
            "adjustment_set": sorted(adjusted),
            "identified_confounders": confounders,
            "graph_colliders": colliders,
            "forbidden_descendants_in_adjustment": sorted(forbidden_descendants),
            "backdoor_d_separated": separated,
            "valid_adjustment_set": not forbidden_descendants and all(separated.values()),
        }

    def _require_node(self, name: str) -> None:
        if name not in self.nodes:
            raise ValueError(f"unknown causal node: {name}")


@dataclass(frozen=True)
class StudyCausalModel:
    setup_id: str
    family: str
    graph: CausalGraph
    exposure: str
    outcomes: tuple[str, ...]
    treatment_value: Any = None
    adjustment_set: tuple[str, ...] = ()

    @property
    def allowed_persona_fields(self) -> set[str]:
        return {
            name
            for name, node in self.graph.nodes.items()
            if node.public and node.role == "baseline" and node.sampler is not None
        }

    @property
    def blocked_persona_fields(self) -> set[str]:
        return set(self.graph.nodes) - self.allowed_persona_fields

    def validate_persona_request(
        self,
        criteria: Mapping[str, Any],
        interventions: Mapping[str, Any],
    ) -> None:
        requested = set(criteria) | set(interventions)
        unknown = requested - set(self.graph.nodes)
        if unknown:
            raise ValueError(f"unknown persona attributes: {sorted(unknown)}")
        blocked = requested - self.allowed_persona_fields
        if blocked:
            roles = {
                name: self.graph.nodes[name].role
                for name in sorted(blocked)
            }
            raise ValueError(
                "persona generation may only use pre-treatment baseline attributes; "
                f"blocked causal nodes: {roles}"
            )

    def diagnostics(self) -> dict[str, Any]:
        report = self.graph.adjustment_report(
            self.exposure,
            self.outcomes,
            self.adjustment_set,
        )
        return {
            "model_id": self.setup_id,
            "model_family": self.family,
            "treatment_assignment": {
                "node": self.exposure,
                "value": self.treatment_value,
            },
            "node_count": len(self.graph.nodes),
            "edge_count": sum(len(node.parents) for node in self.graph.nodes.values()),
            "sampling_order": list(self.graph.order),
            "adjustment": report,
        }


@dataclass(frozen=True)
class CausalPersonaResult:
    attributes: dict[str, Any]
    trace: dict[str, Any]


class CausalPersonaGenerator:
    def sample(
        self,
        *,
        model: StudyCausalModel,
        criteria: Mapping[str, Any],
        interventions: Mapping[str, Any],
        rng: random.Random,
        max_attempts: int = 5000,
    ) -> CausalPersonaResult:
        criteria = _normalize_keys(criteria)
        interventions = _normalize_keys(interventions)
        model.validate_persona_request(criteria, interventions)
        conflicts = {
            name
            for name, value in interventions.items()
            if name in criteria and not _matches(value, criteria[name])
        }
        if conflicts:
            raise ValueError(
                f"interventions conflict with eligibility criteria: {sorted(conflicts)}"
            )

        for attempt in range(1, max_attempts + 1):
            values: dict[str, Any] = {}
            sources: dict[str, str] = {}
            for name in model.graph.order:
                node = model.graph.nodes[name]
                if node.sampler is None:
                    continue
                if name in interventions:
                    values[name] = interventions[name]
                    sources[name] = "intervention"
                else:
                    values[name] = node.sampler(rng, values)
                    sources[name] = "structural_equation"

            public = {
                name: values[name]
                for name in model.graph.order
                if name in values and model.graph.nodes[name].public
            }
            if all(_matches(public.get(name), criterion) for name, criterion in criteria.items()):
                trace = model.diagnostics()
                trace.update(
                    {
                        "criteria": dict(criteria),
                        "interventions": dict(interventions),
                        "attempts": attempt,
                        "node_sources": sources,
                        "latent_state": {
                            name: value
                            for name, value in values.items()
                            if not model.graph.nodes[name].public
                        },
                    }
                )
                return CausalPersonaResult(attributes=public, trace=trace)

        raise ValueError(
            "eligibility criteria were too restrictive for the causal population model "
            f"after {max_attempts} attempts"
        )


def _weighted(rng: random.Random, values: list[tuple[Any, float]]) -> Any:
    return rng.choices(
        [value for value, _ in values],
        weights=[weight for _, weight in values],
        k=1,
    )[0]


def _clamp(value: float, minimum: float = 1, maximum: float = 7) -> int:
    return max(int(minimum), min(int(maximum), int(round(value))))


def _band(value: float) -> str:
    if value <= 2.7:
        return "low"
    if value >= 5.3:
        return "high"
    return "moderate"


def _normal_score(rng: random.Random, mean: float, spread: float = 1.0) -> int:
    return _clamp(rng.gauss(mean, spread))


US_LOCATIONS = [
    ("AR", "Little Rock", "West South Central"),
    ("TX", "Austin", "West South Central"),
    ("AZ", "Phoenix", "Mountain"),
    ("OH", "Columbus", "East North Central"),
    ("NC", "Raleigh", "South Atlantic"),
    ("WI", "Madison", "East North Central"),
    ("OR", "Portland", "Pacific"),
    ("PA", "Philadelphia", "Middle Atlantic"),
    ("CO", "Denver", "Mountain"),
    ("GA", "Atlanta", "South Atlantic"),
]

NON_US_CITIES = {
    "GB": "Manchester",
    "CA": "Toronto",
    "NL": "Utrecht",
    "DE": "Cologne",
    "AU": "Melbourne",
}

FIRST_NAMES = ["Aaliyah", "Alex", "Amara", "Ava", "Ethan", "Isabella", "Jayden", "Jordan", "Maya", "Noah", "Riley", "Sofia"]
LAST_NAMES = ["Anderson", "Brown", "Carter", "Garcia", "Johnson", "Kim", "Lee", "Martinez", "Patel", "Robinson", "Smith", "Williams"]
STREET_NAMES = ["Maple", "Oak", "Pine", "Cedar", "Elmwood", "Riverside", "Hillcrest", "Lakeview"]


def _base_nodes() -> list[CausalNode]:
    n = CausalNode
    return [
        n("_family_ses", role="latent", public=False, sampler=lambda r, v: r.gauss(0, 1)),
        n("_cognitive_endowment", role="latent", public=False, sampler=lambda r, v: r.gauss(0, 1)),
        n("_openness", role="latent", public=False, sampler=lambda r, v: r.gauss(0, 1)),
        n("_digital_engagement", role="latent", public=False, sampler=lambda r, v: r.gauss(0.25, 1)),
        n("_skepticism", role="latent", public=False, sampler=lambda r, v: r.gauss(0, 1)),
        n("_confidence", ("_cognitive_endowment",), role="latent", public=False, sampler=lambda r, v: 0.35 * v["_cognitive_endowment"] + r.gauss(0, 0.9)),
        n("age", sampler=lambda r, v: r.randint(18, 29)),
        n("sex", sampler=lambda r, v: _weighted(r, [("Female", 0.49), ("Male", 0.48), ("Intersex", 0.01), ("Prefer not to say", 0.02)])),
        n("gender", ("sex",), sampler=lambda r, v: _sample_gender(r, v["sex"])),
        n("country", sampler=lambda r, v: _weighted(r, [("US", 0.55), ("GB", 0.18), ("CA", 0.10), ("NL", 0.05), ("DE", 0.05), ("AU", 0.07)])),
        n("state", ("country",), sampler=lambda r, v: r.choice(US_LOCATIONS)[0] if v["country"] == "US" else "NA"),
        n("city", ("country", "state"), sampler=lambda r, v: _sample_city(r, v["country"], v["state"])),
        n("nationality", ("country",), sampler=lambda r, v: {"US": "US", "GB": "British", "CA": "Canadian", "NL": "Dutch", "DE": "German", "AU": "Australian"}[v["country"]]),
        n("born_in_us", ("country",), sampler=lambda r, v: "Yes" if v["country"] == "US" and r.random() < 0.88 else "No"),
        n("us_citizenship_status", ("country", "born_in_us"), sampler=_sample_citizenship),
        n("race", ("country",), sampler=lambda r, v: _sample_race(r, v["country"])),
        n("detailed_race", ("race",), sampler=_sample_detailed_race),
        n("hispanic_origin", ("country", "race"), sampler=_sample_hispanic_origin),
        n("ethnicity", ("hispanic_origin",), sampler=lambda r, v: "American only" if v["hispanic_origin"] == "Not Hispanic" else v["hispanic_origin"]),
        n("family_income_at_16", ("_family_ses",), sampler=lambda r, v: _ordered_band(v["_family_ses"] + r.gauss(0, 0.65), ["Far below average", "Below average", "Average", "Above average", "Far above average"])),
        n("fathers_highest_degree", ("_family_ses",), sampler=lambda r, v: _parent_degree(r, v["_family_ses"])),
        n("mothers_highest_degree", ("_family_ses",), sampler=lambda r, v: _parent_degree(r, v["_family_ses"] + 0.15)),
        n("mothers_work_history", ("_family_ses",), sampler=lambda r, v: _weighted(r, [("Yes", 0.63), ("Part-time", 0.22), ("No", 0.12), ("Not sure", 0.03)])),
        n("family_structure_at_16", ("_family_ses",), sampler=lambda r, v: _weighted(r, [("Lived with parents", 0.67), ("Lived with mother only", 0.20), ("Lived with father only", 0.05), ("Lived with relatives", 0.05), ("Other arrangement", 0.03)])),
        n("cognitive_capacity", ("_cognitive_endowment",), sampler=lambda r, v: _normal_score(r, 4 + 1.05 * v["_cognitive_endowment"], 0.65)),
        n("education", ("age", "_family_ses", "cognitive_capacity"), sampler=_sample_education),
        n("highest_degree_received", ("education",), sampler=lambda r, v: {"high_school_or_equivalent": "High school", "some_college": "Some college", "undergraduate": "Some college", "vocational_training": "Associate degree", "bachelors_degree": "Bachelor's degree", "graduate_student": "Bachelor's degree"}[v["education"]]),
        n("student_status", ("age", "education"), sampler=_sample_student_status),
        n("employment_status", ("age", "education", "student_status"), sampler=_sample_employment),
        n("work_status", ("employment_status", "student_status"), sampler=_work_status),
        n("total_wealth", ("age", "employment_status", "_family_ses"), sampler=_sample_wealth),
        n("household_income_band", ("employment_status", "_family_ses"), sampler=_sample_income_band),
        n("living_situation", ("age", "student_status", "household_income_band"), sampler=_sample_living),
        n("marital_status", ("age", "living_situation"), sampler=_sample_marital),
        n("relationship_status", ("marital_status",), sampler=_sample_relationship),
        n("religion_at_16", ("country",), sampler=_sample_religion),
        n("religion", ("religion_at_16", "_openness"), sampler=_sample_current_religion),
        n("political_views", ("religion", "education", "_openness"), sampler=_sample_politics),
        n("party_identification", ("political_views",), sampler=_sample_party),
        n("digital_habits", ("_digital_engagement",), sampler=_sample_digital_habits),
        n("prior_ai_use", ("_digital_engagement", "education"), sampler=_sample_prior_ai_use),
        n("ai_familiarity", ("prior_ai_use", "education", "_digital_engagement"), sampler=_sample_ai_familiarity),
        n("ai_literacy", ("ai_familiarity", "education", "cognitive_capacity"), sampler=lambda r, v: _normal_score(r, 0.48 * v["ai_familiarity"] + 0.24 * v["cognitive_capacity"] + 1.2 + _education_score(v["education"]), 0.65)),
        n("ai_literacy_level", ("ai_literacy",), sampler=lambda r, v: "low" if v["ai_literacy"] <= 2 else "high" if v["ai_literacy"] >= 6 else "medium"),
        n("online_content_skepticism", ("_skepticism", "ai_literacy"), sampler=lambda r, v: _band(4 + 0.75 * v["_skepticism"] + 0.18 * (v["ai_literacy"] - 4) + r.gauss(0, 0.7))),
        n("ai_skepticism", ("_skepticism", "ai_literacy", "prior_ai_use"), sampler=lambda r, v: _normal_score(r, 4 + 0.8 * v["_skepticism"] + 0.12 * (v["ai_literacy"] - 4) - 0.18 * _ai_use_score(v["prior_ai_use"]), 0.7)),
        n("ai_trust", ("ai_skepticism", "prior_ai_use", "ai_literacy"), sampler=lambda r, v: _normal_score(r, 4.2 - 0.45 * (v["ai_skepticism"] - 4) + 0.22 * _ai_use_score(v["prior_ai_use"]) + 0.08 * (v["ai_literacy"] - 4), 0.75)),
        n("baseline_trust_in_ai", ("ai_trust",), sampler=lambda r, v: _clamp(v["ai_trust"] + r.choice([-1, 0, 0, 0, 1]))),
        n("general_confidence", ("_confidence",), sampler=lambda r, v: _normal_score(r, 4 + v["_confidence"], 0.65)),
        n("working_memory", ("cognitive_capacity",), sampler=lambda r, v: _normal_score(r, 1.0 + 0.78 * v["cognitive_capacity"], 0.75)),
        n("openness_to_change", ("_openness",), sampler=lambda r, v: _normal_score(r, 4 + 0.95 * v["_openness"], 0.7)),
        n("openness_to_new_information", ("openness_to_change",), sampler=lambda r, v: _band(v["openness_to_change"] + r.gauss(0, 0.55))),
        n("reasoning_style", ("cognitive_capacity", "education", "_openness"), sampler=_sample_reasoning_style),
        n("attention_to_detail", ("working_memory", "reasoning_style"), sampler=lambda r, v: _band(0.55 * v["working_memory"] + (1.0 if v["reasoning_style"] == "analytical" else 0.3) + 1.4 + r.gauss(0, 0.7))),
        n("attention_level", ("attention_to_detail",), sampler=lambda r, v: {"low": "low", "moderate": "medium", "high": "high"}[v["attention_to_detail"]]),
        n("resilience_under_distraction", ("working_memory", "openness_to_change"), sampler=lambda r, v: _normal_score(r, 0.58 * v["working_memory"] + 0.22 * v["openness_to_change"] + 0.8, 0.75)),
        n("task_effort", ("attention_to_detail", "resilience_under_distraction"), sampler=lambda r, v: _normal_score(r, 0.48 * v["resilience_under_distraction"] + {"low": 0.4, "moderate": 1.6, "high": 2.5}[v["attention_to_detail"]], 0.7)),
        n("uncertainty_tolerance", ("openness_to_change", "general_confidence"), sampler=lambda r, v: _normal_score(r, 3.2 + 0.38 * (v["openness_to_change"] - 4) - 0.22 * (v["general_confidence"] - 4), 0.8)),
        n("fatigue_sensitivity", ("resilience_under_distraction", "working_memory"), sampler=lambda r, v: _normal_score(r, 7.5 - 0.48 * v["resilience_under_distraction"] - 0.30 * v["working_memory"], 0.75)),
        n("knowledge_geography_history", ("education", "cognitive_capacity"), sampler=lambda r, v: _knowledge(r, v)),
        n("knowledge_science_health", ("education", "cognitive_capacity"), sampler=lambda r, v: _knowledge(r, v)),
        n("knowledge_entertainment_literature", ("education", "cognitive_capacity", "_digital_engagement"), sampler=lambda r, v: _knowledge(r, v, 0.18 * v["_digital_engagement"])),
        n("knowledge_technology_internet", ("education", "cognitive_capacity", "ai_literacy"), sampler=lambda r, v: _knowledge(r, v, 0.22 * (v["ai_literacy"] - 4))),
        n("topic_familiarity", ("knowledge_science_health", "knowledge_technology_internet"), sampler=lambda r, v: _normal_score(r, 0.42 * v["knowledge_science_health"] + 0.35 * v["knowledge_technology_internet"] + 0.9, 0.85)),
        n("initial_opinion_strength", ("topic_familiarity", "general_confidence"), sampler=lambda r, v: _normal_score(r, 0.42 * v["topic_familiarity"] + 0.32 * v["general_confidence"] + 1.0, 0.8)),
        n("initial_opinion_confidence", ("initial_opinion_strength", "general_confidence"), sampler=lambda r, v: _normal_score(r, 0.52 * v["initial_opinion_strength"] + 0.32 * v["general_confidence"] + 0.65, 0.7)),
        n("initial_climate_lifestyle_view", ("political_views", "openness_to_change", "knowledge_science_health"), sampler=_sample_climate_view),
        n("prior_exposure_to_misinformation", ("_digital_engagement", "digital_habits"), sampler=lambda r, v: _band(4 + 0.8 * v["_digital_engagement"] + (0.5 if v["digital_habits"] == "heavy_social_media" else 0) + r.gauss(0, 0.7))),
        n("personality_texture", ("_openness", "_skepticism", "_confidence"), sampler=_sample_personality),
        n("survey_style", ("personality_texture", "attention_to_detail"), sampler=_sample_survey_style),
        n("social_agreement_tendency", ("personality_texture", "general_confidence"), sampler=_sample_social_agreement),
        n("response_consistency", ("attention_to_detail", "reasoning_style", "task_effort"), sampler=lambda r, v: _normal_score(r, 1.6 + 0.38 * v["task_effort"] + (0.8 if v["reasoning_style"] == "analytical" else 0.35) + {"low": -0.4, "moderate": 0.2, "high": 0.7}[v["attention_to_detail"]], 0.65)),
        n("region_type", ("country", "city"), sampler=lambda r, v: _weighted(r, [("large_city", 0.35), ("suburb", 0.30), ("small_city", 0.23), ("rural_area", 0.12)])),
        n("residence_at_16", ("state", "country"), sampler=_sample_residence_region),
        n("same_residence_since_16", ("age", "country"), sampler=lambda r, v: _weighted(r, [("Same city", 0.32), ("Same state", 0.34), ("Different state", 0.25), ("Different country", 0.09)])),
        n("speak_other_language", ("country",), sampler=lambda r, v: "Yes" if v["country"] != "US" or r.random() < 0.24 else "No"),
        n("other_language", ("speak_other_language", "country"), sampler=_sample_other_language),
        n("military_service_duration", ("age",), sampler=lambda r, v: _weighted(r, [("No active duty", 0.96), ("Less than 2 years", 0.025), ("2-4 years", 0.014), ("More than 4 years", 0.001)])),
        n("first_name", ("gender",), sampler=lambda r, v: r.choice(FIRST_NAMES)),
        n("last_name", ("race", "country"), sampler=lambda r, v: r.choice(LAST_NAMES)),
        n("street_address", ("state", "city"), sampler=lambda r, v: f"{r.randint(100, 9999)} {r.choice(STREET_NAMES)} {r.choice(['St', 'Ave', 'Drive', 'Lane'])} (synthetic)"),
    ]


def _study_nodes(family: str) -> tuple[str, tuple[str, ...], list[CausalNode]]:
    n = CausalNode
    if family == "truth_source":
        return "source_label_visibility", ("predicted_truthfulness", "confidence", "trustworthiness"), [
            n("statement_truthfulness", role="treatment"),
            n("statement_source", role="treatment"),
            n("source_label_visibility", role="treatment"),
            n("predicted_truthfulness", ("statement_truthfulness", "source_label_visibility", "general_confidence", "knowledge_geography_history", "knowledge_science_health", "knowledge_entertainment_literature", "knowledge_technology_internet", "task_effort", "response_consistency"), role="outcome"),
            n("perceived_source", ("statement_source", "source_label_visibility", "ai_literacy", "ai_skepticism"), role="outcome"),
            n("confidence", ("predicted_truthfulness", "general_confidence", "topic_familiarity", "uncertainty_tolerance"), role="outcome"),
            n("trustworthiness", ("statement_source", "source_label_visibility", "ai_trust", "predicted_truthfulness"), role="outcome"),
            n("detection_accuracy", ("statement_truthfulness", "predicted_truthfulness"), role="collider"),
        ]
    if family == "sycophancy":
        return "llm_condition", ("trust_in_llm", "opinion_change", "perceived_trustworthiness"), [
            n("llm_condition", role="treatment"),
            n("perceived_agreement", ("llm_condition", "initial_opinion_strength", "social_agreement_tendency"), role="mediator"),
            n("conversation_engagement", ("perceived_agreement", "openness_to_change"), role="collider"),
            n("trust_in_llm", ("perceived_agreement", "baseline_trust_in_ai", "ai_skepticism"), role="outcome"),
            n("perceived_trustworthiness", ("perceived_agreement", "ai_skepticism"), role="outcome"),
            n("opinion_change", ("perceived_agreement", "openness_to_change", "topic_familiarity", "social_agreement_tendency"), role="outcome"),
            n("opinion_strength_change", ("opinion_change", "initial_opinion_strength"), role="outcome"),
            n("opinion_confidence_change", ("opinion_change", "initial_opinion_confidence"), role="outcome"),
            n("manipulation_check_sycophancy_score", ("llm_condition", "perceived_agreement"), role="outcome"),
        ]
    if family == "climate_partner":
        return "partner_condition", ("opinion_change", "epistemic_trust", "perceived_autonomy"), [
            n("partner_condition", role="treatment"),
            n("argument_exposure", ("partner_condition",), role="mediator"),
            n("conversation_quality", ("argument_exposure", "openness_to_new_information", "reasoning_style", "task_effort", "fatigue_sensitivity"), role="collider"),
            n("opinion_change", ("argument_exposure", "initial_climate_lifestyle_view", "openness_to_new_information"), role="outcome"),
            n("epistemic_trust", ("argument_exposure", "ai_trust", "conversation_quality"), role="outcome"),
            n("perceived_autonomy", ("partner_condition", "conversation_quality", "general_confidence"), role="outcome"),
        ]
    if family == "cognitive_load":
        return "cognitive_load", ("accuracy", "confidence", "sharing_likelihood"), [
            n("cognitive_load", role="treatment"),
            n("effective_working_memory", ("cognitive_load", "working_memory", "resilience_under_distraction"), role="mediator"),
            n("secondary_task_performance", ("cognitive_load", "cognitive_capacity"), role="collider"),
            n("veracity_judgement", ("effective_working_memory", "topic_familiarity", "ai_skepticism"), role="outcome"),
            n("accuracy", ("veracity_judgement", "effective_working_memory", "topic_familiarity", "task_effort", "fatigue_sensitivity"), role="outcome"),
            n("confidence", ("accuracy", "general_confidence", "effective_working_memory"), role="outcome"),
            n("sharing_likelihood", ("veracity_judgement", "confidence", "online_content_skepticism"), role="outcome"),
        ]
    if family == "ai_literacy_intervention":
        return "literacy_intervention", ("detection_accuracy", "confidence", "perceived_difficulty"), [
            n("literacy_intervention", role="treatment"),
            n("stimulus_source", role="treatment"),
            n("applied_detection_skill", ("literacy_intervention", "ai_literacy", "attention_to_detail"), role="mediator"),
            n("detection_judgement", ("stimulus_source", "applied_detection_skill", "online_content_skepticism", "task_effort", "response_consistency"), role="outcome"),
            n("detection_accuracy", ("stimulus_source", "detection_judgement"), role="collider"),
            n("confidence", ("detection_accuracy", "general_confidence"), role="outcome"),
            n("perceived_difficulty", ("applied_detection_skill", "attention_to_detail"), role="outcome"),
            n("improvement", ("literacy_intervention", "detection_accuracy"), role="outcome"),
        ]
    return "study_condition", ("response",), [
        n("study_condition", role="treatment"),
        n("response", ("study_condition", "general_confidence"), role="outcome"),
    ]


MODEL_FAMILIES = {
    "truth_source_unlabeled": "truth_source",
    "truth_source_labeled": "truth_source",
    "sycophancy_neutral": "sycophancy",
    "sycophancy_sycophantic": "sycophancy",
    "climate_thinking_partner_neutral": "climate_partner",
    "climate_thinking_partner_steelman": "climate_partner",
    "climate_thinking_partner_socratic": "climate_partner",
    "cognitive_load_no_load": "cognitive_load",
    "cognitive_load_low_load": "cognitive_load",
    "cognitive_load_high_load": "cognitive_load",
    "ai_agent_literacy_intervention": "ai_literacy_intervention",
    "image_text_ai_generated_intervention": "ai_literacy_intervention",
}

TREATMENT_ASSIGNMENTS = {
    "truth_source_unlabeled": "unlabeled",
    "truth_source_labeled": "labeled",
    "sycophancy_neutral": "neutral",
    "sycophancy_sycophantic": "sycophantic",
    "climate_thinking_partner_neutral": "neutral",
    "climate_thinking_partner_steelman": "steelman",
    "climate_thinking_partner_socratic": "socratic",
    "cognitive_load_no_load": "no_load",
    "cognitive_load_low_load": "low_load",
    "cognitive_load_high_load": "high_load",
    "ai_agent_literacy_intervention": "within_subject_pre_post",
    "image_text_ai_generated_intervention": "within_subject_pre_post",
}


@lru_cache(maxsize=None)
def get_causal_model(setup_id: str | None) -> StudyCausalModel:
    model_id = setup_id or "generic_young_adult"
    family = MODEL_FAMILIES.get(model_id, "generic")
    exposure, outcomes, study_nodes = _study_nodes(family)
    graph = CausalGraph([*_base_nodes(), *study_nodes])
    return StudyCausalModel(
        setup_id=model_id,
        family=family,
        graph=graph,
        exposure=exposure,
        outcomes=outcomes,
        treatment_value=TREATMENT_ASSIGNMENTS.get(model_id),
        adjustment_set=(),
    )


def validate_persona_request(
    setup_id: str | None,
    criteria: Mapping[str, Any],
    interventions: Mapping[str, Any],
) -> None:
    normalized_criteria = _normalize_keys(criteria)
    normalized_interventions = _normalize_keys(interventions)
    get_causal_model(setup_id).validate_persona_request(
        normalized_criteria,
        normalized_interventions,
    )
    if "age" in normalized_interventions:
        age = int(normalized_interventions["age"])
        if age < 18 or age > 29:
            raise ValueError("conditioned age must be between 18 and 29")


def _normalize_keys(values: Mapping[str, Any]) -> dict[str, Any]:
    aliases = {
        "us_state": "state",
        "highest_degree": "highest_degree_received",
        "degree": "highest_degree_received",
        "employment": "work_status",
        "party": "party_identification",
    }
    return {aliases.get(key, key): value for key, value in values.items()}


def _matches(value: Any, criterion: Any) -> bool:
    if value is None:
        return False
    if isinstance(criterion, dict):
        minimum = criterion.get("min")
        maximum = criterion.get("max")
        return (minimum is None or value >= minimum) and (maximum is None or value <= maximum)
    if isinstance(criterion, list):
        return value in criterion
    return value == criterion


def _sample_gender(rng: random.Random, sex: str) -> str:
    if sex == "Female":
        return _weighted(rng, [("woman", 0.94), ("nonbinary", 0.04), ("prefer_not_to_say", 0.02)])
    if sex == "Male":
        return _weighted(rng, [("man", 0.95), ("nonbinary", 0.03), ("prefer_not_to_say", 0.02)])
    return _weighted(rng, [("nonbinary", 0.65), ("woman", 0.12), ("man", 0.12), ("prefer_not_to_say", 0.11)])


def _sample_city(rng: random.Random, country: str, state: str) -> str:
    if country != "US":
        return NON_US_CITIES[country]
    matches = [city for candidate, city, _ in US_LOCATIONS if candidate == state]
    return rng.choice(matches) if matches else "Unknown City"


def _sample_citizenship(rng: random.Random, values: Mapping[str, Any]) -> str:
    if values["born_in_us"] == "Yes":
        return "A U.S. citizen"
    if values["country"] == "US":
        return _weighted(rng, [("A U.S. citizen", 0.46), ("Permanent resident", 0.28), ("Temporary visa holder", 0.18), ("Not a U.S. citizen", 0.08)])
    return "Not a U.S. citizen"


def _sample_race(rng: random.Random, country: str) -> str:
    weights = [("White", 0.57), ("Black or African American", 0.14), ("Asian", 0.15), ("Multiracial", 0.10), ("Other", 0.04)]
    if country in {"GB", "NL", "DE"}:
        weights = [("White", 0.72), ("Black or African American", 0.08), ("Asian", 0.11), ("Multiracial", 0.06), ("Other", 0.03)]
    return _weighted(rng, weights)


def _sample_detailed_race(rng: random.Random, values: Mapping[str, Any]) -> str:
    race = values["race"]
    if race == "Asian":
        return rng.choice(["Chinese", "Asian Indian", "Korean", "Vietnamese"])
    return race


def _sample_hispanic_origin(rng: random.Random, values: Mapping[str, Any]) -> str:
    if values["country"] != "US" or rng.random() > 0.18:
        return "Not Hispanic"
    return _weighted(rng, [("Mexican", 0.62), ("Puerto Rican", 0.17), ("Cuban", 0.07), ("Other Hispanic", 0.14)])


def _ordered_band(value: float, labels: list[str]) -> str:
    index = max(0, min(len(labels) - 1, int(round(value + (len(labels) - 1) / 2))))
    return labels[index]


def _parent_degree(rng: random.Random, ses: float) -> str:
    return _ordered_band(ses + rng.gauss(0, 0.8), ["Less than high school", "High school", "Some college", "Bachelor's degree", "Graduate degree"])


def _sample_education(rng: random.Random, values: Mapping[str, Any]) -> str:
    age = values["age"]
    score = 0.55 * values["_family_ses"] + 0.12 * (values["cognitive_capacity"] - 4) + rng.gauss(0, 0.8)
    if age <= 19:
        return _weighted(rng, [("high_school_or_equivalent", 0.32), ("some_college", 0.18), ("undergraduate", 0.43), ("vocational_training", 0.07)])
    if age <= 22:
        return _weighted(rng, [("high_school_or_equivalent", 0.12), ("some_college", 0.18), ("undergraduate", 0.48), ("vocational_training", 0.08), ("bachelors_degree", 0.14)])
    if score > 0.9:
        return _weighted(rng, [("bachelors_degree", 0.55), ("graduate_student", 0.30), ("undergraduate", 0.15)])
    return _weighted(rng, [("high_school_or_equivalent", 0.12), ("some_college", 0.21), ("undergraduate", 0.20), ("vocational_training", 0.10), ("bachelors_degree", 0.29), ("graduate_student", 0.08)])


def _sample_student_status(rng: random.Random, values: Mapping[str, Any]) -> str:
    education = values["education"]
    if education == "graduate_student":
        return "graduate_student"
    if education == "undergraduate" or (values["age"] <= 22 and education == "some_college"):
        return _weighted(rng, [("undergraduate", 0.82), ("not_student", 0.18)])
    return _weighted(rng, [("not_student", 0.78), ("undergraduate", 0.17), ("graduate_student", 0.05)])


def _sample_employment(rng: random.Random, values: Mapping[str, Any]) -> str:
    if values["student_status"] != "not_student":
        return _weighted(rng, [("part_time", 0.52), ("not_currently_employed", 0.31), ("gig_or_freelance", 0.12), ("full_time", 0.05)])
    return _weighted(rng, [("full_time", 0.54), ("part_time", 0.20), ("not_currently_employed", 0.14), ("gig_or_freelance", 0.12)])


def _work_status(rng: random.Random, values: Mapping[str, Any]) -> str:
    if values["student_status"] != "not_student" and values["employment_status"] == "not_currently_employed":
        return "Student"
    return {"full_time": "Working full-time", "part_time": "Working part-time", "not_currently_employed": "Unemployed, looking for work", "gig_or_freelance": "Other"}[values["employment_status"]]


def _sample_wealth(rng: random.Random, values: Mapping[str, Any]) -> str:
    score = values["_family_ses"] + 0.10 * (values["age"] - 22) + (0.55 if values["employment_status"] == "full_time" else 0) + rng.gauss(0, 0.7)
    return _ordered_band(score, ["Less than $5,000", "$5,000 to $24,999", "$25,000 to $49,999", "$50,000 to $99,999", "$100,000 to $249,999", "$250,000 or more"])


def _sample_income_band(rng: random.Random, values: Mapping[str, Any]) -> str:
    score = values["_family_ses"] + (0.6 if values["employment_status"] == "full_time" else -0.2) + rng.gauss(0, 0.55)
    return _ordered_band(score, ["low", "lower_middle", "middle", "upper_middle"])


def _sample_living(rng: random.Random, values: Mapping[str, Any]) -> str:
    if values["student_status"] != "not_student":
        return _weighted(rng, [("student_housing", 0.35), ("with_roommates", 0.30), ("with_family", 0.26), ("alone", 0.04), ("with_partner", 0.05)])
    return _weighted(rng, [("with_family", 0.36), ("with_roommates", 0.24), ("alone", 0.15), ("with_partner", 0.25)])


def _sample_marital(rng: random.Random, values: Mapping[str, Any]) -> str:
    if values["living_situation"] == "with_partner":
        return _weighted(rng, [("Living with partner", 0.70), ("Married", 0.20), ("Never married", 0.10)])
    return _weighted(rng, [("Never married", 0.91), ("Married", 0.04), ("Separated", 0.01), ("Divorced", 0.02), ("Living with partner", 0.02)])


def _sample_relationship(rng: random.Random, values: Mapping[str, Any]) -> str:
    if values["marital_status"] in {"Married", "Living with partner"}:
        return "in_relationship"
    return _weighted(rng, [("single", 0.50), ("dating", 0.27), ("in_relationship", 0.19), ("prefer_not_to_say", 0.04)])


def _sample_religion(rng: random.Random, values: Mapping[str, Any]) -> str:
    return _weighted(rng, [("None", 0.34), ("Catholic", 0.18), ("Protestant", 0.13), ("Other Christian", 0.16), ("Jewish", 0.03), ("Muslim", 0.05), ("Hindu", 0.04), ("Buddhist", 0.03), ("Other", 0.04)])


def _sample_current_religion(rng: random.Random, values: Mapping[str, Any]) -> str:
    if rng.random() < 0.72 - 0.08 * max(values["_openness"], 0):
        return values["religion_at_16"]
    return _weighted(rng, [("None", 0.58), ("Other", 0.12), (values["religion_at_16"], 0.30)])


def _sample_politics(rng: random.Random, values: Mapping[str, Any]) -> str:
    religion_shift = 0.55 if values["religion"] in {"Protestant", "Other Christian"} else -0.15 if values["religion"] == "None" else 0
    education_shift = -0.25 if values["education"] in {"bachelors_degree", "graduate_student"} else 0
    score = religion_shift + education_shift - 0.25 * values["_openness"] + rng.gauss(0, 0.85)
    return _ordered_band(score, ["Very liberal", "Liberal", "Slightly liberal", "Moderate", "Slightly conservative", "Conservative", "Very conservative"])


def _sample_party(rng: random.Random, values: Mapping[str, Any]) -> str:
    view = values["political_views"]
    if "liberal" in view.lower():
        return _weighted(rng, [("Democrat", 0.54), ("Independent, close to democrat", 0.30), ("Independent", 0.12), ("No preference", 0.04)])
    if "conservative" in view.lower():
        return _weighted(rng, [("Republican", 0.51), ("Independent, close to republican", 0.31), ("Independent", 0.13), ("No preference", 0.05)])
    return _weighted(rng, [("Independent", 0.46), ("Democrat", 0.16), ("Republican", 0.14), ("No preference", 0.18), ("Other party", 0.06)])


def _sample_digital_habits(rng: random.Random, values: Mapping[str, Any]) -> str:
    engagement = values["_digital_engagement"]
    if engagement > 0.8:
        return _weighted(rng, [("heavy_social_media", 0.54), ("creator_or_poster", 0.25), ("moderate_social_media", 0.16), ("mostly_messaging", 0.05)])
    if engagement < -0.6:
        return _weighted(rng, [("privacy_conscious", 0.45), ("mostly_messaging", 0.32), ("moderate_social_media", 0.23)])
    return _weighted(rng, [("moderate_social_media", 0.44), ("mostly_messaging", 0.24), ("privacy_conscious", 0.16), ("heavy_social_media", 0.11), ("creator_or_poster", 0.05)])


def _sample_prior_ai_use(rng: random.Random, values: Mapping[str, Any]) -> str:
    score = values["_digital_engagement"] + _education_score(values["education"]) + rng.gauss(0, 0.7)
    return _ordered_band(score, ["none", "rare", "occasional", "frequent"])


def _ai_use_score(value: str) -> int:
    return {"none": -2, "rare": -1, "occasional": 0, "frequent": 2}[value]


def _education_score(value: str) -> float:
    return {"high_school_or_equivalent": -0.4, "some_college": -0.1, "undergraduate": 0.2, "vocational_training": 0, "bachelors_degree": 0.45, "graduate_student": 0.7}[value]


def _sample_ai_familiarity(rng: random.Random, values: Mapping[str, Any]) -> int:
    return _normal_score(rng, 4 + 0.85 * _ai_use_score(values["prior_ai_use"]) + 0.35 * values["_digital_engagement"] + _education_score(values["education"]), 0.6)


def _sample_reasoning_style(rng: random.Random, values: Mapping[str, Any]) -> str:
    score = 0.55 * (values["cognitive_capacity"] - 4) + _education_score(values["education"]) + 0.2 * values["_openness"] + rng.gauss(0, 0.65)
    if score > 0.65:
        return "analytical"
    if score < -0.65:
        return "intuitive"
    return "mixed"


def _knowledge(rng: random.Random, values: Mapping[str, Any], shift: float = 0) -> int:
    mean = 2.0 + 0.34 * values["cognitive_capacity"] + _education_score(values["education"]) + shift
    return _normal_score(rng, mean, 0.9)


def _sample_climate_view(rng: random.Random, values: Mapping[str, Any]) -> int:
    politics = {"Very liberal": 1.3, "Liberal": 1.0, "Slightly liberal": 0.6, "Moderate": 0, "Slightly conservative": -0.4, "Conservative": -0.8, "Very conservative": -1.1}[values["political_views"]]
    return _normal_score(rng, 4 + politics + 0.18 * (values["openness_to_change"] - 4) + 0.16 * (values["knowledge_science_health"] - 4), 0.85)


def _sample_personality(rng: random.Random, values: Mapping[str, Any]) -> str:
    if values["_skepticism"] > 0.8:
        return "skeptical"
    if values["_openness"] > 0.9:
        return "reflective"
    if values["_confidence"] > 0.8:
        return "optimistic"
    return rng.choice(["practical", "socially_oriented", "low_energy", "reflective"])


def _sample_survey_style(rng: random.Random, values: Mapping[str, Any]) -> str:
    if values["attention_to_detail"] == "high":
        return _weighted(rng, [("detail_oriented", 0.58), ("conversational", 0.22), ("concise", 0.20)])
    if values["personality_texture"] == "low_energy":
        return _weighted(rng, [("concise", 0.55), ("casual", 0.30), ("slightly_uncertain", 0.15)])
    return rng.choice(["concise", "conversational", "slightly_uncertain", "casual"])


def _sample_social_agreement(rng: random.Random, values: Mapping[str, Any]) -> int:
    texture_shift = {
        "socially_oriented": 0.9,
        "optimistic": 0.35,
        "practical": 0.0,
        "reflective": -0.15,
        "low_energy": 0.2,
        "skeptical": -0.8,
    }[values["personality_texture"]]
    mean = 4 + texture_shift - 0.18 * (values["general_confidence"] - 4)
    return _normal_score(rng, mean, 0.75)


def _sample_residence_region(rng: random.Random, values: Mapping[str, Any]) -> str:
    if values["country"] != "US":
        return "Different country"
    matches = [region for state, _, region in US_LOCATIONS if state == values["state"]]
    return matches[0] if matches else "Unknown"


def _sample_other_language(rng: random.Random, values: Mapping[str, Any]) -> str:
    if values["speak_other_language"] == "No":
        return "None"
    country_language = {"GB": "None", "CA": "French", "NL": "Dutch", "DE": "German", "AU": "None", "US": "Spanish"}
    preferred = country_language[values["country"]]
    return preferred if preferred != "None" else rng.choice(["Spanish", "French", "Mandarin", "Hindi", "Arabic", "German"])
