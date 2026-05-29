from __future__ import annotations

import secrets
import uuid

from app.config import Settings
from app.experiments import get_experiment_setup, merge_setup_criteria, study_from_setup
from app.llm import LLMProvider
from app.persona import PersonaSampler
from app.prompting import build_system_prompt, history_to_messages
from app.schemas import CreateSessionRequest, PersonaPoolRequest, SingleTurnRequest, TurnRequest
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
            "seed": seed,
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
            session = {
                **session,
                "persona": persona,
                "seed": reset_seed,
                "persona_pool_member_id": persona_pool_member_id,
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
        )
        system_prompt = build_system_prompt(
            study=session["study"],
            persona=persona,
            response_mode=request.response_mode,
            trial_context=trial_context,
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
        self.store.add_trace_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_completed",
            event={
                "request": request.model_dump(),
                "trial_context": trial_context,
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
            "persona_pool_id": session["persona_pool_id"],
            "persona_pool_member_id": session["persona_pool_member_id"],
            "trial_id": request.trial_id,
            "reset_policy": request.reset_policy,
            "qualitative_thinking": response.qualitative_thinking,
            "persona": persona,
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

    def _next_reset_seed(self, current_seed: int) -> int:
        return (current_seed * 1103515245 + 12345) % (2**31)

    def _pool_member_seed(self, pool_seed: int, index: int) -> int:
        return (pool_seed + (index + 1) * 2654435761) % (2**63)

    def _build_trial_context(
        self,
        *,
        all_prior_turns: list[dict],
        visible_turns: list[dict],
        request: TurnRequest,
    ) -> dict[str, str | int | None]:
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

        return {
            "trial_id": request.trial_id,
            "trial_index": request.trial_index,
            "reset_policy": request.reset_policy,
            "reset_meaning": reset_note,
            "prior_session_turns": prior_turn_count,
            "visible_prior_turns": len(visible_turns),
            "completed_trials_seen_by_system": len(completed_trial_ids),
            "estimated_fatigue": fatigue,
        }
