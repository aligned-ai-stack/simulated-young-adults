from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExperimentSetup:
    id: str
    name: str
    description: str
    default_criteria: dict[str, Any]
    source_label_visibility: str
    statement_count_per_run: int
    response_questions: list[str]
    dependent_variables: list[str]
    confounds_to_sample: list[str]
    independent_variables: list[str] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "default_criteria": deepcopy(self.default_criteria),
            "source_label_visibility": self.source_label_visibility,
            "statement_count_per_run": self.statement_count_per_run,
            "response_questions": list(self.response_questions),
            "independent_variables": list(self.independent_variables),
            "dependent_variables": list(self.dependent_variables),
            "confounds_to_sample": list(self.confounds_to_sample),
        }


def _climate_thinking_partner_setup(
    *,
    setup_id: str,
    name: str,
    partner_role: str,
    role_description: str,
) -> ExperimentSetup:
    return ExperimentSetup(
        id=setup_id,
        name=name,
        description=(
            "Between-subjects structured discussion study about the topic: "
            "'Individual lifestyle changes are a meaningful and necessary part of "
            "addressing climate change.' Personas complete a pre-study survey, state "
            "their initial position, complete five exchanges with a thinking partner, "
            "then complete a post-study survey. "
            f"Thinking partner condition: {partner_role}. {role_description}"
        ),
        default_criteria={"age": {"min": 18, "max": 25}},
        source_label_visibility="not_applicable",
        statement_count_per_run=5,
        response_questions=[
            "pre_opinion_likert_1_to_7",
            "pre_opinion_confidence_1_to_7",
            "pre_ai_epistemic_trust_items_1_to_5",
            "pre_epistemic_autonomy_items_1_to_5",
            "opening_position_3_to_5_sentences",
            "five_conversation_exchanges",
            "post_opinion_likert_1_to_7",
            "post_opinion_confidence_1_to_7",
            "post_reconsideration_1_to_5",
            "post_epistemic_trust_items",
            "post_epistemic_autonomy_items",
            "open_ended_change_trust_autonomy_reflections",
        ],
        independent_variables=[
            "thinking_partner_condition_neutral_vs_steelman_vs_socratic",
        ],
        dependent_variables=[
            "opinion_change",
            "epistemic_trust",
            "perceived_autonomy",
        ],
        confounds_to_sample=[
            "age",
            "ai_literacy",
            "ai_trust",
            "education",
            "openness_to_new_information",
            "general_confidence",
            "reasoning_style",
            "initial_climate_lifestyle_view",
            "gender",
            "nationality",
        ],
    )


EXPERIMENT_SETUPS: dict[str, ExperimentSetup] = {
    "truth_source_unlabeled": ExperimentSetup(
        id="truth_source_unlabeled",
        name="Truth and source detection: unlabeled",
        description=(
            "Young adults judge whether AI-generated or human-generated statements "
            "are true, infer the likely source, rate confidence, and rate trustworthiness. "
            "The source label is not shown."
        ),
        default_criteria={"age": {"min": 18, "max": 25}},
        source_label_visibility="not_labeled",
        statement_count_per_run=20,
        response_questions=[
            "predicted_truthfulness_true_false_or_idk",
            "confidence_1_to_7",
            "perceived_source_1_definitely_human_to_7_definitely_ai",
            "trustworthiness_1_to_7",
        ],
        dependent_variables=[
            "predicted_truthfulness",
            "confidence",
            "perceived_source",
            "trustworthiness",
        ],
        independent_variables=[
            "statement_truthfulness",
            "statement_source",
            "source_label_visibility",
        ],
        confounds_to_sample=[
            "ai_literacy",
            "ai_trust",
            "education",
            "general_confidence",
            "knowledge_geography_history",
            "knowledge_science_health",
            "knowledge_entertainment_literature",
            "knowledge_technology_internet",
            "gender",
            "nationality",
        ],
    ),
    "truth_source_labeled": ExperimentSetup(
        id="truth_source_labeled",
        name="Truth and source detection: labeled",
        description=(
            "Young adults judge whether AI-generated or human-generated statements "
            "are true, rate confidence, and rate trustworthiness. The AI/human source "
            "label is shown."
        ),
        default_criteria={"age": {"min": 18, "max": 25}},
        source_label_visibility="labeled",
        statement_count_per_run=20,
        response_questions=[
            "predicted_truthfulness_true_false_or_idk",
            "confidence_1_to_7",
            "trustworthiness_1_to_7",
        ],
        dependent_variables=[
            "predicted_truthfulness",
            "confidence",
            "trustworthiness",
        ],
        independent_variables=[
            "statement_truthfulness",
            "statement_source",
            "source_label_visibility",
        ],
        confounds_to_sample=[
            "ai_literacy",
            "ai_trust",
            "education",
            "general_confidence",
            "knowledge_geography_history",
            "knowledge_science_health",
            "knowledge_entertainment_literature",
            "knowledge_technology_internet",
            "gender",
            "nationality",
        ],
    ),
    "ai_agent_literacy_intervention": ExperimentSetup(
        id="ai_agent_literacy_intervention",
        name="AI-agent literacy intervention: text and image detection",
        description=(
            "Within-subject repeated-measures intervention study. Each persona completes "
            "pre-intervention text detection, receives text-specific literacy guidance, "
            "completes post-intervention text detection, then repeats the pattern for "
            "image detection with image-specific literacy guidance. Each run contains "
            "40 total stimuli: 10 pre-text, 10 post-text, 10 pre-image, and 10 post-image. "
            "Each 10-stimulus set is balanced 50/50 AI-generated and human-created."
        ),
        default_criteria={},
        source_label_visibility="not_applicable",
        statement_count_per_run=40,
        response_questions=[
            "stimulus_id",
            "modality_text_or_image",
            "stage_pre_or_post_intervention",
            "judgement_ai_generated_or_human_created",
            "confidence_1_to_7",
            "difficulty_1_to_7",
            "short_reasoning",
        ],
        independent_variables=[
            "intervention_stage_pre_vs_post",
            "modality_text_vs_image",
        ],
        dependent_variables=[
            "detection_judgement",
            "confidence",
            "perceived_difficulty",
            "detection_accuracy",
            "text_improvement",
            "image_improvement",
        ],
        confounds_to_sample=[
            "ai_literacy_level",
            "prior_ai_use",
            "online_content_skepticism",
            "attention_to_detail",
            "prior_exposure_to_misinformation",
        ],
    ),
    "climate_thinking_partner_neutral": _climate_thinking_partner_setup(
        setup_id="climate_thinking_partner_neutral",
        name="Climate thinking partner: neutral information",
        partner_role="neutral information partner",
        role_description=(
            "The partner provides balanced factual context and both sides of the debate "
            "without challenging, questioning, advocating, or pushing back."
        ),
    ),
    "climate_thinking_partner_steelman": _climate_thinking_partner_setup(
        setup_id="climate_thinking_partner_steelman",
        name="Climate thinking partner: steelman",
        partner_role="steelman partner",
        role_description=(
            "The partner presents the strongest intellectually honest argument against "
            "the participant's position, engaging directly over five exchanges."
        ),
    ),
    "climate_thinking_partner_socratic": _climate_thinking_partner_setup(
        setup_id="climate_thinking_partner_socratic",
        name="Climate thinking partner: Socratic",
        partner_role="Socratic partner",
        role_description=(
            "The partner uses focused open-ended questions to probe assumptions and "
            "reasoning, asking no more than one question per turn."
        ),
    ),
}


def list_experiment_setups() -> list[dict[str, Any]]:
    return [setup.to_public_dict() for setup in EXPERIMENT_SETUPS.values()]


def get_experiment_setup(setup_id: str) -> ExperimentSetup:
    try:
        return EXPERIMENT_SETUPS[setup_id]
    except KeyError as exc:
        raise ValueError(f"unknown experiment_setup_id: {setup_id}") from exc


def merge_setup_criteria(
    setup_criteria: dict[str, Any],
    request_criteria: dict[str, Any],
) -> dict[str, Any]:
    merged = deepcopy(setup_criteria)
    for key, value in request_criteria.items():
        if key == "age" and key in merged:
            merged[key] = _intersect_age_criteria(merged[key], value)
        else:
            merged[key] = value
    return merged


def study_from_setup(
    setup: ExperimentSetup,
    request_study: dict[str, Any],
) -> dict[str, Any]:
    study = deepcopy(request_study)
    if study.get("name") == "Untitled study":
        study["name"] = setup.name
    study["description"] = "\n".join(
        part for part in [setup.description, study.get("description", "")] if part
    )
    setup_instructions = (
        f"Experiment setup id: {setup.id}. "
        f"Source label visibility: {setup.source_label_visibility}. "
        f"Each participant run contains {setup.statement_count_per_run} sequential statements. "
        f"Independent variables: {', '.join(setup.independent_variables)}. "
        f"Expected response variables: {', '.join(setup.response_questions)}."
    )
    study["instructions"] = "\n".join(
        part for part in [setup_instructions, study.get("instructions", "")] if part
    )
    return study


def _intersect_age_criteria(base: Any, requested: Any) -> Any:
    base_min, base_max = _age_bounds(base)
    req_min, req_max = _age_bounds(requested)
    min_age = max(base_min, req_min)
    max_age = min(base_max, req_max)
    if min_age > max_age:
        raise ValueError("requested age criteria do not overlap experiment setup age range")
    return {"min": min_age, "max": max_age}


def _age_bounds(criteria: Any) -> tuple[int, int]:
    if isinstance(criteria, dict):
        return int(criteria.get("min", 18)), int(criteria.get("max", 29))
    if isinstance(criteria, int):
        return criteria, criteria
    if isinstance(criteria, list) and criteria:
        ages = [int(age) for age in criteria]
        return min(ages), max(ages)
    return 18, 29
