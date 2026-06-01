from __future__ import annotations

import json
import secrets
import uuid

from app.config import Settings
from app.experiments import get_experiment_setup, merge_setup_criteria, study_from_setup
from app.llm import LLMProvider
from app.persona import PersonaSampler
from app.prompting import build_system_prompt, history_to_messages
from app.schemas import (
    CreateSessionRequest,
    PersonaListRequest,
    PersonaPoolRequest,
    SessionDemographicsRequest,
    SingleTurnRequest,
    TurnRequest,
)
from app.storage import SimulationStore


class SimulationService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: SimulationStore,
        provider: LLMProvider,
        sampler: PersonaSampler | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.provider = provider
        self.sampler = sampler or PersonaSampler()

    def create_session(self, request: CreateSessionRequest) -> dict:
        experiment_setup_id = request.experiment_setup_id
        study = request.study.model_dump()
        criteria = request.criteria
        conditioned_attributes = request.conditioned_attributes
        persona_pool_id = None
        persona_pool_member_id = None

        if experiment_setup_id:
            setup = get_experiment_setup(experiment_setup_id)
            criteria = merge_setup_criteria(setup.default_criteria, request.criteria)
            study = study_from_setup(setup, study)
            pool = self.ensure_persona_pool(
                experiment_setup_id=experiment_setup_id,
                criteria=criteria,
                conditioned_attributes=conditioned_attributes,
                pool_size=request.persona_pool_size,
                random_seed=request.random_seed,
            )
            allocation = self.store.allocate_persona_from_pool(pool["persona_pool_id"])
            persona = allocation["persona"]
            seed = allocation["seed"]
            persona_pool_id = allocation["pool_id"]
            persona_pool_member_id = allocation["id"]
        else:
            sample = self.sampler.sample(
                criteria=criteria,
                conditioned_attributes=conditioned_attributes,
                random_seed=request.random_seed,
            )
            persona = {"persona_id": sample.persona_id, **sample.attributes}
            seed = sample.seed

        session_id = f"session_{uuid.uuid4().hex}"
        self.store.create_session(
            session_id=session_id,
            experiment_setup_id=experiment_setup_id,
            persona_pool_id=persona_pool_id,
            persona_pool_member_id=persona_pool_member_id,
            study=study,
            criteria=criteria,
            conditioned_attributes=conditioned_attributes,
            persona=persona,
            seed=seed,
            provider=self.settings.provider,
        )
        self.store.add_trace_event(
            session_id=session_id,
            turn_id=None,
            event_type="session_created",
            event={
                "experiment_setup_id": experiment_setup_id,
                "persona_pool_id": persona_pool_id,
                "persona_pool_member_id": persona_pool_member_id,
                "seed": seed,
                "criteria": criteria,
                "conditioned_attributes": conditioned_attributes,
                "persona": persona,
            },
        )
        return {
            "session_id": session_id,
            "experiment_setup_id": experiment_setup_id,
            "persona_pool_id": persona_pool_id,
            "persona_pool_member_id": persona_pool_member_id,
            "persona": persona,
            "demographics": {},
            "seed": seed,
        }

    def generate_personas(self, request: PersonaListRequest) -> dict:
        setup = None
        criteria = request.criteria
        if request.experiment_setup_id:
            setup = get_experiment_setup(request.experiment_setup_id)
            criteria = merge_setup_criteria(setup.default_criteria, request.criteria)

        personas = []
        for _ in range(request.count):
            sample = self.sampler.sample(
                criteria=criteria,
                conditioned_attributes=request.conditioned_attributes,
            )
            persona = {"persona_id": sample.persona_id, **sample.attributes}
            if request.compact:
                persona = self._compact_persona(persona, setup)
            personas.append(persona)

        return {
            "synthetic": True,
            "experiment_setup_id": request.experiment_setup_id,
            "count": len(personas),
            "personas": personas,
        }

    def ensure_persona_pool(
        self,
        *,
        experiment_setup_id: str,
        criteria: dict,
        conditioned_attributes: dict,
        pool_size: int,
        random_seed: int | None,
    ) -> dict:
        existing = self.store.find_persona_pool(
            experiment_setup_id=experiment_setup_id,
            criteria=criteria,
            conditioned_attributes=conditioned_attributes,
        )
        if existing is not None:
            if existing["size"] < pool_size:
                self._expand_persona_pool(
                    pool_id=existing["id"],
                    criteria=criteria,
                    conditioned_attributes=conditioned_attributes,
                    pool_seed=existing["seed"],
                    start_index=existing["size"],
                    target_size=pool_size,
                )
                existing = {**existing, "size": pool_size}
            return {
                "persona_pool_id": existing["id"],
                "experiment_setup_id": existing["experiment_setup_id"],
                "size": existing["size"],
                "seed": existing["seed"],
                "criteria": existing["criteria"],
                "conditioned_attributes": existing["conditioned_attributes"],
            }

        seed = random_seed if random_seed is not None else secrets.randbits(63)
        pool_id = f"pool_{experiment_setup_id}_{uuid.uuid4().hex[:12]}"
        members = []
        for index in range(pool_size):
            member_seed = self._pool_member_seed(seed, index)
            sample = self.sampler.sample(
                criteria=criteria,
                conditioned_attributes=conditioned_attributes,
                random_seed=member_seed,
            )
            members.append(
                {
                    "id": f"member_{uuid.uuid4().hex[:12]}",
                    "seed": member_seed,
                    "persona": {"persona_id": sample.persona_id, **sample.attributes},
                }
            )
        self.store.create_persona_pool(
            pool_id=pool_id,
            experiment_setup_id=experiment_setup_id,
            criteria=criteria,
            conditioned_attributes=conditioned_attributes,
            seed=seed,
            members=members,
        )
        return {
            "persona_pool_id": pool_id,
            "experiment_setup_id": experiment_setup_id,
            "size": pool_size,
            "seed": seed,
            "criteria": criteria,
            "conditioned_attributes": conditioned_attributes,
        }

    def _expand_persona_pool(
        self,
        *,
        pool_id: str,
        criteria: dict,
        conditioned_attributes: dict,
        pool_seed: int,
        start_index: int,
        target_size: int,
    ) -> None:
        members = []
        for index in range(start_index, target_size):
            member_seed = self._pool_member_seed(pool_seed, index)
            sample = self.sampler.sample(
                criteria=criteria,
                conditioned_attributes=conditioned_attributes,
                random_seed=member_seed,
            )
            members.append(
                {
                    "id": f"member_{uuid.uuid4().hex[:12]}",
                    "seed": member_seed,
                    "persona": {"persona_id": sample.persona_id, **sample.attributes},
                }
            )
        self.store.add_persona_pool_members(pool_id=pool_id, members=members)

    def create_persona_pool(
        self,
        *,
        experiment_setup_id: str,
        request: PersonaPoolRequest,
    ) -> dict:
        setup = get_experiment_setup(experiment_setup_id)
        criteria = merge_setup_criteria(setup.default_criteria, request.criteria)
        return self.ensure_persona_pool(
            experiment_setup_id=experiment_setup_id,
            criteria=criteria,
            conditioned_attributes=request.conditioned_attributes,
            pool_size=request.pool_size,
            random_seed=request.random_seed,
        )

    def respond(self, session_id: str, request: TurnRequest) -> dict:
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)

        persona = session["persona"]
        if request.reset_policy == "full":
            persona_pool_member_id = None
            if session.get("persona_pool_id"):
                allocation = self.store.allocate_persona_from_pool(session["persona_pool_id"])
                reset_seed = allocation["seed"]
                persona = allocation["persona"]
                persona_pool_member_id = allocation["id"]
            else:
                reset_seed = self._next_reset_seed(session["seed"])
                sample = self.sampler.sample(
                    criteria=session["criteria"],
                    conditioned_attributes=session["conditioned_attributes"],
                    random_seed=reset_seed,
                )
                persona = {"persona_id": sample.persona_id, **sample.attributes}
            self.store.replace_session_persona(
                session_id=session_id,
                persona=persona,
                seed=reset_seed,
                persona_pool_member_id=persona_pool_member_id,
            )
            self.store.update_session_state(session_id=session_id, session_state={})
            session = {
                **session,
                "persona": persona,
                "seed": reset_seed,
                "persona_pool_member_id": persona_pool_member_id,
                "session_state": {},
            }

        if request.reset_policy == "carryover":
            turns = self.store.list_turns(session_id)
        elif request.reset_policy == "trial":
            turns = self.store.list_turns(session_id, trial_id=request.trial_id)
        else:
            turns = []

        all_prior_turns = self.store.list_turns(session_id)
        trial_context = self._build_trial_context(
            all_prior_turns=all_prior_turns,
            visible_turns=turns,
            request=request,
            session_state=session.get("session_state", {}),
            experiment_setup_id=session.get("experiment_setup_id"),
        )
        prompt_trial_context = {
            key: value
            for key, value in trial_context.items()
            if key not in {"trial_id"}
        }
        system_prompt = build_system_prompt(
            study=session["study"],
            persona=persona,
            response_mode=request.response_mode,
            trial_context=prompt_trial_context,
        )
        response = self.provider.complete(
            system_prompt=system_prompt,
            history=history_to_messages(turns),
            message=request.message,
            persona=persona,
            capture_thinking=request.capture_thinking,
        )
        turn_id = self.store.add_turn(
            session_id=session_id,
            message=request.message,
            stimulus=request.stimulus,
            metadata=request.metadata,
            response=response.response,
            qualitative_thinking=response.qualitative_thinking,
            trial_id=request.trial_id,
            trial_index=request.trial_index,
            reset_policy=request.reset_policy,
            persona=persona,
            response_mode=request.response_mode,
            request=request.model_dump(),
            system_prompt=system_prompt,
            visible_history=turns,
            trial_context=trial_context,
            provider_trace=response.provider_trace,
        )
        updated_session_state = self._update_session_state(
            current_state=session.get("session_state", {}),
            session=session,
            request=request,
            response_text=response.response,
            qualitative_thinking=response.qualitative_thinking,
            turn_id=turn_id,
        )
        if updated_session_state != session.get("session_state", {}):
            self.store.update_session_state(
                session_id=session_id,
                session_state=updated_session_state,
            )
        self.store.add_trace_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_completed",
            event={
                "request": request.model_dump(),
                "trial_context": trial_context,
                "session_state": updated_session_state,
                "visible_history_turns": len(turns),
                "persona": persona,
                "qualitative_thinking": response.qualitative_thinking,
                "response": response.response,
                "provider_trace": response.provider_trace,
            },
        )
        return {
            "session_id": session_id,
            "turn_id": turn_id,
            "experiment_setup_id": session["experiment_setup_id"],
            "trial_id": request.trial_id,
            "reset_policy": request.reset_policy,
            "qualitative_thinking": response.qualitative_thinking,
            "response": response.response,
        }

    def single_turn(self, request: SingleTurnRequest) -> dict:
        session = self.create_session(
            CreateSessionRequest(
                study=request.study,
                experiment_setup_id=request.experiment_setup_id,
                criteria=request.criteria,
                conditioned_attributes=request.conditioned_attributes,
                random_seed=request.random_seed,
                persona_pool_size=request.persona_pool_size,
            )
        )
        turn = self.respond(
            session["session_id"],
            TurnRequest(
                message=request.message,
                stimulus=request.stimulus,
                metadata=request.metadata,
                trial_id=request.trial_id,
                trial_index=request.trial_index,
                response_mode=request.response_mode,
                capture_thinking=request.capture_thinking,
            ),
        )
        return {**turn, "seed": session["seed"]}

    def list_session_turns(self, session_id: str) -> list[dict]:
        if self.store.get_session(session_id) is None:
            raise KeyError(session_id)
        return self.store.list_turns(session_id)

    def list_session_traces(self, session_id: str) -> list[dict]:
        if self.store.get_session(session_id) is None:
            raise KeyError(session_id)
        return self.store.list_trace_events(session_id)

    def export_session(self, session_id: str) -> dict:
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)

        experiment_setup = None
        if session.get("experiment_setup_id"):
            experiment_setup = get_experiment_setup(session["experiment_setup_id"]).to_public_dict()

        return {
            "session": session,
            "experiment_setup": experiment_setup,
            "persona": session["persona"],
            "demographics": session["demographics"],
            "turns": self.store.list_turns(session_id),
            "traces": self.store.list_trace_events(session_id),
        }

    def record_session_demographics(
        self,
        session_id: str,
        request: SessionDemographicsRequest,
    ) -> dict:
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)

        demographics = request.demographics
        self.store.update_session_demographics(
            session_id=session_id,
            demographics=demographics,
        )
        self.store.add_trace_event(
            session_id=session_id,
            turn_id=None,
            event_type="session_demographics_recorded",
            event={"demographics": demographics},
        )
        return {
            "session_id": session_id,
            "synthetic": True,
            "persona": session["persona"],
            "demographics": demographics,
        }

    def _next_reset_seed(self, current_seed: int) -> int:
        return (current_seed * 1103515245 + 12345) % (2**31)

    def _pool_member_seed(self, pool_seed: int, index: int) -> int:
        return (pool_seed + (index + 1) * 2654435761) % (2**63)

    def _compact_persona(self, persona: dict, setup) -> dict:
        keys = [
            "persona_id",
            "age",
            "gender",
            "sex",
            "race",
            "ethnicity",
            "country",
            "state",
            "education",
            "student_status",
        ]
        if setup is not None:
            keys.extend(setup.confounds_to_sample)
        return {
            key: persona[key]
            for key in dict.fromkeys(keys)
            if key in persona
        }

    def _build_trial_context(
        self,
        *,
        all_prior_turns: list[dict],
        visible_turns: list[dict],
        request: TurnRequest,
        session_state: dict | None = None,
        experiment_setup_id: str | None = None,
    ) -> dict:
        completed_trial_ids = {
            turn["trial_id"]
            for turn in all_prior_turns
            if turn.get("trial_id") is not None
        }
        prior_turn_count = len(all_prior_turns)
        fatigue = "low"
        if prior_turn_count >= 20:
            fatigue = "high"
        elif prior_turn_count >= 8:
            fatigue = "medium"

        reset_note = {
            "carryover": "same participant; all previous session content is visible",
            "trial": "same participant; only this trial's content is visible",
            "full": "fresh participant reset; no previous session content is visible",
        }[request.reset_policy]

        context = {
            "trial_id": request.trial_id,
            "trial_index": request.trial_index,
            "reset_policy": request.reset_policy,
            "reset_meaning": reset_note,
            "prior_session_turns": prior_turn_count,
            "visible_prior_turns": len(visible_turns),
            "completed_trials_seen_by_system": len(completed_trial_ids),
            "estimated_fatigue": fatigue,
        }
        if (
            session_state
            and request.reset_policy != "full"
            and experiment_setup_id != "image_text_ai_generated_intervention"
        ):
            context["session_state_summary"] = session_state
        return context

    def _update_session_state(
        self,
        *,
        current_state: dict,
        session: dict,
        request: TurnRequest,
        response_text: str,
        qualitative_thinking: str | None,
        turn_id: int,
    ) -> dict:
        experiment_setup_id = session.get("experiment_setup_id")
        if experiment_setup_id == "image_text_ai_generated_intervention":
            return current_state

        state = json.loads(json.dumps(current_state or {}))
        if not state:
            state = {
                "persona_summary": self._state_persona_summary(session["persona"]),
                "pre_survey": {},
                "post_survey": {},
                "task_summary": {
                    "completed_trials": 0,
                    "phase_counts": {},
                    "truth_response_counts": {},
                    "uncertain_trials": 0,
                    "confidence_values": [],
                    "trustworthiness_values": [],
                    "perceived_source_ai_values": [],
                    "sharing_likelihood_values": [],
                    "conversation_exchanges": 0,
                    "behavioral_notes": [],
                },
            }

        phase = str(request.metadata.get("phase") or request.response_mode or "turn")
        parsed = self._parse_response_json(response_text)
        response_payload = parsed if isinstance(parsed, dict) else {"raw_response": response_text}

        if "pre" in phase and "survey" in phase or phase == "pre_interaction":
            state["pre_survey"].update(response_payload)
        elif "post" in phase and "survey" in phase or phase == "post_interaction":
            state["post_survey"].update(response_payload)
        else:
            self._update_task_summary(
                state["task_summary"],
                phase=phase,
                request=request,
                response_payload=response_payload,
                qualitative_thinking=qualitative_thinking,
                turn_id=turn_id,
            )

        state["fatigue"] = self._state_fatigue(state["task_summary"].get("completed_trials", 0))
        return self._trim_session_state(state)

    def _state_persona_summary(self, persona: dict) -> dict:
        keys = [
            "age",
            "gender",
            "education",
            "student_status",
            "ai_literacy",
            "ai_literacy_level",
            "ai_trust",
            "baseline_trust_in_ai",
            "ai_skepticism",
            "online_content_skepticism",
            "general_confidence",
            "attention_to_detail",
            "attention_level",
            "reasoning_style",
            "survey_style",
            "openness_to_new_information",
            "openness_to_change",
            "topic_familiarity",
            "initial_climate_lifestyle_view",
            "initial_opinion_strength",
            "initial_opinion_confidence",
            "resilience_under_distraction",
            "cognitive_capacity",
            "working_memory",
        ]
        return {key: persona[key] for key in keys if key in persona}

    def _update_task_summary(
        self,
        summary: dict,
        *,
        phase: str,
        request: TurnRequest,
        response_payload: dict,
        qualitative_thinking: str | None,
        turn_id: int,
    ) -> None:
        summary["completed_trials"] = int(summary.get("completed_trials", 0)) + 1
        phase_counts = summary.setdefault("phase_counts", {})
        phase_counts[phase] = int(phase_counts.get(phase, 0)) + 1

        if "exchange" in phase or request.response_mode in {"chat", "interview"}:
            summary["conversation_exchanges"] = int(summary.get("conversation_exchanges", 0)) + 1

        truth = response_payload.get("predicted_truthfulness") or response_payload.get("veracity")
        if truth is not None:
            normalized_truth = str(truth).lower()
            counts = summary.setdefault("truth_response_counts", {})
            counts[normalized_truth] = int(counts.get(normalized_truth, 0)) + 1
            if normalized_truth in {"unsure", "idk", "not sure"}:
                summary["uncertain_trials"] = int(summary.get("uncertain_trials", 0)) + 1

        for field, bucket in [
            ("confidence_1_to_7", "confidence_values"),
            ("trustworthiness_1_to_7", "trustworthiness_values"),
            ("perceived_source_1_human_to_7_ai", "perceived_source_ai_values"),
            ("sharing_likelihood_1_to_7", "sharing_likelihood_values"),
        ]:
            value = response_payload.get(field)
            if isinstance(value, int) and not isinstance(value, bool):
                summary.setdefault(bucket, []).append(value)

        notes = summary.setdefault("behavioral_notes", [])
        note = response_payload.get("one_sentence_reason") or qualitative_thinking
        if isinstance(note, str) and note.strip():
            notes.append({"turn_id": turn_id, "phase": phase, "note": note.strip()[:240]})
            del notes[:-5]

        summary["average_confidence"] = self._average(summary.get("confidence_values", []))
        summary["average_trustworthiness"] = self._average(summary.get("trustworthiness_values", []))
        summary["average_perceived_source_ai"] = self._average(summary.get("perceived_source_ai_values", []))
        summary["average_sharing_likelihood"] = self._average(summary.get("sharing_likelihood_values", []))

    def _trim_session_state(self, state: dict) -> dict:
        task_summary = state.get("task_summary", {})
        for key in [
            "confidence_values",
            "trustworthiness_values",
            "perceived_source_ai_values",
            "sharing_likelihood_values",
        ]:
            values = task_summary.get(key)
            if isinstance(values, list) and len(values) > 25:
                task_summary[key] = values[-25:]
        return state

    def _parse_response_json(self, response_text: str):
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return None

    def _average(self, values: list) -> float | None:
        numeric = [
            value for value in values
            if isinstance(value, int | float) and not isinstance(value, bool)
        ]
        if not numeric:
            return None
        return round(sum(numeric) / len(numeric), 2)

    def _state_fatigue(self, completed_trials: int) -> dict:
        if completed_trials >= 20:
            level = "high"
        elif completed_trials >= 8:
            level = "medium"
        else:
            level = "low"
        return {"completed_task_turns": completed_trials, "level": level}
