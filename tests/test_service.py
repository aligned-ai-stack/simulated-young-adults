from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from app.config import Settings
from app.llm import ModelResult
from app.schemas import CreateSessionRequest, StudySpec, TurnRequest
from app.service import SimulationService
from app.storage import SimulationStore


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        *,
        system_prompt: str,
        history: list[dict[str, str]],
        message: str,
        persona: dict[str, Any],
        capture_thinking: bool,
    ) -> ModelResult:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "history": history,
                "message": message,
                "persona": persona,
                "capture_thinking": capture_thinking,
            }
        )
        return ModelResult(
            response=f"history={len(history)}",
            qualitative_thinking="I compared the statement to what I know and chose a rating.",
            provider_trace={"provider": "test", "history_message_count": len(history)},
        )


class ServiceResetTests(unittest.TestCase):
    def build_service(self) -> tuple[SimulationService, RecordingProvider]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        provider = RecordingProvider()
        service = SimulationService(
            settings=Settings(provider="mock", database_path=Path(temp_dir.name) / "db.sqlite3"),
            store=SimulationStore(Path(temp_dir.name) / "db.sqlite3"),
            provider=provider,  # type: ignore[arg-type]
        )
        return service, provider

    def test_trial_reset_only_exposes_same_trial_history(self) -> None:
        service, provider = self.build_service()
        session = service.create_session(
            CreateSessionRequest(
                study=StudySpec(name="Sequential task"),
                random_seed=2,
            )
        )

        service.respond(
            session["session_id"],
            TurnRequest(message="Trial A first", trial_id="A"),
        )
        service.respond(
            session["session_id"],
            TurnRequest(message="Trial B first", trial_id="B"),
        )
        response = service.respond(
            session["session_id"],
            TurnRequest(message="Trial A second", trial_id="A", reset_policy="trial"),
        )

        self.assertEqual(response["reset_policy"], "trial")
        self.assertEqual(response["persona"]["persona_id"], session["persona"]["persona_id"])
        self.assertEqual(len(provider.calls[-1]["history"]), 2)
        self.assertIn("only this trial's content is visible", provider.calls[-1]["system_prompt"])

    def test_full_reset_replaces_persona_and_hides_history(self) -> None:
        service, provider = self.build_service()
        session = service.create_session(
            CreateSessionRequest(
                study=StudySpec(name="Between-subject task"),
                random_seed=5,
            )
        )

        service.respond(
            session["session_id"],
            TurnRequest(message="First participant trial", trial_id="1"),
        )
        response = service.respond(
            session["session_id"],
            TurnRequest(message="New participant trial", trial_id="2", reset_policy="full"),
        )

        self.assertEqual(response["reset_policy"], "full")
        self.assertNotEqual(response["persona"]["persona_id"], session["persona"]["persona_id"])
        self.assertEqual(provider.calls[-1]["history"], [])
        self.assertIn("fresh participant reset", provider.calls[-1]["system_prompt"])

    def test_experiment_setups_get_separate_persona_pools(self) -> None:
        service, _ = self.build_service()

        unlabeled = service.create_session(
            CreateSessionRequest(
                study=StudySpec(),
                experiment_setup_id="truth_source_unlabeled",
                persona_pool_size=3,
                random_seed=10,
            )
        )
        unlabeled_again = service.create_session(
            CreateSessionRequest(
                study=StudySpec(),
                experiment_setup_id="truth_source_unlabeled",
                persona_pool_size=3,
                random_seed=999,
            )
        )
        labeled = service.create_session(
            CreateSessionRequest(
                study=StudySpec(),
                experiment_setup_id="truth_source_labeled",
                persona_pool_size=3,
                random_seed=10,
            )
        )

        self.assertEqual(
            unlabeled["persona_pool_id"],
            unlabeled_again["persona_pool_id"],
        )
        self.assertNotEqual(unlabeled["persona_pool_id"], labeled["persona_pool_id"])
        self.assertEqual(unlabeled["experiment_setup_id"], "truth_source_unlabeled")
        self.assertEqual(labeled["experiment_setup_id"], "truth_source_labeled")
        self.assertLessEqual(unlabeled["persona"]["age"], 25)

    def test_second_experiment_uses_its_own_pool_and_attributes(self) -> None:
        service, _ = self.build_service()

        first_experiment = service.create_session(
            CreateSessionRequest(
                study=StudySpec(),
                experiment_setup_id="truth_source_unlabeled",
                persona_pool_size=3,
                random_seed=50,
            )
        )
        intervention = service.create_session(
            CreateSessionRequest(
                study=StudySpec(),
                experiment_setup_id="ai_agent_literacy_intervention",
                persona_pool_size=3,
                random_seed=50,
            )
        )

        self.assertNotEqual(
            first_experiment["persona_pool_id"],
            intervention["persona_pool_id"],
        )
        self.assertEqual(
            intervention["experiment_setup_id"],
            "ai_agent_literacy_intervention",
        )
        self.assertIn("ai_literacy_level", intervention["persona"])
        self.assertIn("prior_ai_use", intervention["persona"])
        self.assertIn("online_content_skepticism", intervention["persona"])
        self.assertIn("attention_to_detail", intervention["persona"])
        self.assertIn("prior_exposure_to_misinformation", intervention["persona"])

        stored = service.store.get_session(intervention["session_id"])
        self.assertIsNotNone(stored)
        self.assertIn("pre-intervention text detection", stored["study"]["description"])
        self.assertIn("intervention_stage_pre_vs_post", stored["study"]["instructions"])

    def test_third_experiment_conditions_have_separate_pools(self) -> None:
        service, _ = self.build_service()

        neutral = service.create_session(
            CreateSessionRequest(
                study=StudySpec(),
                experiment_setup_id="climate_thinking_partner_neutral",
                persona_pool_size=3,
                random_seed=70,
            )
        )
        steelman = service.create_session(
            CreateSessionRequest(
                study=StudySpec(),
                experiment_setup_id="climate_thinking_partner_steelman",
                persona_pool_size=3,
                random_seed=70,
            )
        )
        socratic = service.create_session(
            CreateSessionRequest(
                study=StudySpec(),
                experiment_setup_id="climate_thinking_partner_socratic",
                persona_pool_size=3,
                random_seed=70,
            )
        )

        self.assertNotEqual(neutral["persona_pool_id"], steelman["persona_pool_id"])
        self.assertNotEqual(steelman["persona_pool_id"], socratic["persona_pool_id"])
        self.assertNotEqual(neutral["persona_pool_id"], socratic["persona_pool_id"])
        self.assertIn("openness_to_new_information", neutral["persona"])
        self.assertIn("reasoning_style", neutral["persona"])
        self.assertIn("initial_climate_lifestyle_view", neutral["persona"])

        stored = service.store.get_session(socratic["session_id"])
        self.assertIsNotNone(stored)
        self.assertIn("Socratic partner", stored["study"]["description"])
        self.assertIn(
            "thinking_partner_condition_neutral_vs_steelman_vs_socratic",
            stored["study"]["instructions"],
        )

    def test_existing_pool_expands_when_larger_size_is_requested(self) -> None:
        service, _ = self.build_service()
        first = service.create_session(
            CreateSessionRequest(
                study=StudySpec(),
                experiment_setup_id="truth_source_unlabeled",
                persona_pool_size=2,
                random_seed=88,
            )
        )
        second = service.create_session(
            CreateSessionRequest(
                study=StudySpec(),
                experiment_setup_id="truth_source_unlabeled",
                persona_pool_size=5,
                random_seed=999,
            )
        )
        pool = service.store.get_persona_pool(first["persona_pool_id"])

        self.assertEqual(first["persona_pool_id"], second["persona_pool_id"])
        self.assertIsNotNone(pool)
        self.assertEqual(pool["size"], 5)

    def test_full_reset_in_experiment_session_draws_from_same_pool(self) -> None:
        service, _ = self.build_service()
        session = service.create_session(
            CreateSessionRequest(
                study=StudySpec(),
                experiment_setup_id="truth_source_unlabeled",
                persona_pool_size=3,
                random_seed=77,
            )
        )

        response = service.respond(
            session["session_id"],
            TurnRequest(message="Statement 1", reset_policy="full"),
        )

        self.assertEqual(response["persona_pool_id"], session["persona_pool_id"])
        self.assertNotEqual(
            response["persona_pool_member_id"],
            session["persona_pool_member_id"],
        )

    def test_turn_trace_is_persisted_for_analysis_and_debugging(self) -> None:
        service, provider = self.build_service()
        session = service.create_session(
            CreateSessionRequest(
                study=StudySpec(name="Trace study"),
                random_seed=123,
            )
        )

        response = service.respond(
            session["session_id"],
            TurnRequest(
                message="Statement: The Eiffel Tower is in Paris.",
                stimulus={"statement_id": "s1", "source": "human", "truth": True},
                metadata={"batch": "debug"},
                trial_id="trial_s1",
                trial_index=1,
            ),
        )

        self.assertIn("qualitative_thinking", response)
        self.assertTrue(provider.calls[-1]["capture_thinking"])

        turns = service.list_session_turns(session["session_id"])
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["turn_id"], response["turn_id"])
        self.assertEqual(turns[0]["stimulus"]["statement_id"], "s1")
        self.assertEqual(turns[0]["metadata"]["batch"], "debug")
        self.assertIn("Trace study", turns[0]["system_prompt"])
        self.assertEqual(turns[0]["request"]["capture_thinking"], True)
        self.assertEqual(turns[0]["provider_trace"]["provider"], "test")
        self.assertIn("compared the statement", turns[0]["qualitative_thinking"])

        traces = service.list_session_traces(session["session_id"])
        event_types = [trace["event_type"] for trace in traces]
        self.assertIn("session_created", event_types)
        self.assertIn("turn_completed", event_types)


if __name__ == "__main__":
    unittest.main()
