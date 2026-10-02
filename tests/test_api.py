from __future__ import annotations

import importlib.util
import os
import sys
import unittest


@unittest.skipIf(importlib.util.find_spec("fastapi") is None, "FastAPI is not installed")
class ApiTests(unittest.TestCase):
    def build_client(self):
        os.environ["SIM_PROVIDER"] = "mock"
        sys.modules.pop("app.main", None)

        from fastapi.testclient import TestClient
        from app.main import app

        return TestClient(app)

    def test_single_turn_response_includes_audit_fields(self) -> None:
        client = self.build_client()
        response = client.post(
            "/v1/respond",
            json={
                "study": {
                    "name": "Campus transport",
                    "description": "Assess commuting habits.",
                    "instructions": "Give a concise open-ended survey answer.",
                },
                "message": "How did you get to campus this week?",
                "criteria": {"age": {"min": 18, "max": 29}},
                "random_seed": 11,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["synthetic"])
        self.assertNotIn("seed", body)
        self.assertEqual(body["reset_policy"], "carryover")
        self.assertIn("session_id", body)
        self.assertNotIn("persona", body)
        self.assertNotIn("persona_pool_id", body)
        self.assertNotIn("persona_pool_member_id", body)
        self.assertNotIn("seed", body)
        self.assertIn("response", body)
        self.assertIn("qualitative_thinking", body)

        turns = client.get(f"/v1/sessions/{body['session_id']}/turns")
        self.assertEqual(turns.status_code, 200)
        stored_turn = turns.json()[0]
        self.assertEqual(stored_turn["turn_id"], body["turn_id"])
        self.assertEqual(stored_turn["request"]["capture_thinking"], True)
        self.assertIn("system_prompt", stored_turn)

        traces = client.get(f"/v1/sessions/{body['session_id']}/traces")
        self.assertEqual(traces.status_code, 200)
        self.assertGreaterEqual(len(traces.json()), 2)

    def test_session_demographics_endpoint_persists_payload(self) -> None:
        client = self.build_client()
        session = client.post(
            "/v1/sessions",
            json={
                "study": {"name": "Demographics study"},
                "random_seed": 12,
            },
        )
        self.assertEqual(session.status_code, 200)
        session_id = session.json()["session_id"]

        response = client.post(
            f"/v1/sessions/{session_id}/demographics",
            json={
                "demographics": {
                    "age": 24,
                    "gender": "nonbinary",
                    "country": "CA",
                }
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["session_id"], session_id)
        self.assertEqual(body["demographics"]["country"], "CA")
        self.assertIn("persona", body)

    def test_persona_endpoint_returns_requested_count_and_setup_policy(self) -> None:
        client = self.build_client()
        response = client.post(
            "/v1/personas",
            json={
                "experiment_setup_id": "cognitive_load_high_load",
                "count": 100,
                "compact": True,
                "study": {
                    "name": "Cognitive load misinformation task",
                    "description": "Generate personas for a high-load study.",
                },
                "criteria": {"age": {"min": 18, "max": 25}},
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["experiment_setup_id"], "cognitive_load_high_load")
        self.assertEqual(body["count"], 100)
        self.assertEqual(len(body["personas"]), 100)
        self.assertNotIn("criteria", body)
        self.assertNotIn("conditioned_attributes", body)
        self.assertNotIn("causal_policy", body)
        self.assertIn("resilience_under_distraction", body["personas"][0])
        self.assertNotIn("street_address", body["personas"][0])

    def test_new_image_text_setup_is_available(self) -> None:
        client = self.build_client()
        response = client.get("/v1/experiment-setups")

        self.assertEqual(response.status_code, 200)
        setup_ids = {setup["id"] for setup in response.json()}
        self.assertIn("image_text_ai_generated_intervention", setup_ids)
        self.assertIn("cognitive_load_no_load", setup_ids)
        self.assertIn("cognitive_load_low_load", setup_ids)
        self.assertIn("cognitive_load_high_load", setup_ids)

    def test_persona_endpoint_rejects_post_treatment_conditioning(self) -> None:
        client = self.build_client()
        response = client.post(
            "/v1/personas",
            json={
                "experiment_setup_id": "sycophancy_neutral",
                "count": 1,
                "study": {"name": "Collider guard"},
                "conditioned_attributes": {"conversation_engagement": 7},
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("blocked causal nodes", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
