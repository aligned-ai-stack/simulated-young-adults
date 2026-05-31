from __future__ import annotations

import importlib.util
import unittest


@unittest.skipIf(importlib.util.find_spec("fastapi") is None, "FastAPI is not installed")
class ApiTests(unittest.TestCase):
    def test_single_turn_response_includes_audit_fields(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
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
        self.assertEqual(body["seed"], 11)
        self.assertEqual(body["reset_policy"], "carryover")
        self.assertIn("session_id", body)
        self.assertIn("persona", body)
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
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
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


if __name__ == "__main__":
    unittest.main()
