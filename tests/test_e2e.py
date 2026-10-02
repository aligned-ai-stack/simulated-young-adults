from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        cls.base_url = f"http://127.0.0.1:{port}"
        cls.env = {**os.environ, "SIM_PROVIDER": "mock", "SIM_DB_PATH": str(Path(cls.temp.name) / "simulation.sqlite3")}
        cls.server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT, env=cls.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        cls.addClassCleanup(cls.stop_server)
        for _ in range(100):
            try:
                with urllib.request.urlopen(cls.base_url + "/health", timeout=1):
                    return
            except urllib.error.URLError:
                if cls.server.poll() is not None:
                    raise RuntimeError("The API exited before becoming available")
                time.sleep(0.1)
        raise RuntimeError("The API did not become available")

    @classmethod
    def stop_server(cls):
        cls.server.terminate()
        try:
            cls.server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.wait()
        cls.temp.cleanup()

    def request(self, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            self.base_url + path, data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())

    def test_study_session_from_creation_to_export(self):
        session = self.request("/v1/sessions", {
            "study": {"name": "Survey workflow"}, "random_seed": 42,
        })
        session_id = session["session_id"]
        path = f"/v1/sessions/{session_id}"
        for trial, policy in [("a", "carryover"), ("b", "trial"), ("b", "trial"), ("c", "full")]:
            turn = self.request(path + "/turns", {
                "message": "How confident are you in this statement?",
                "trial_id": trial, "reset_policy": policy,
            })
            self.assertTrue(turn["synthetic"])
            self.assertTrue(turn["response"])
        self.request(path + "/demographics", {"demographics": {"country": "CA"}})
        export = self.request(path + "/export")
        self.assertEqual(export["demographics"]["country"], "CA")
        self.assertEqual(len(export["turns"]), 4)
        self.assertEqual([len(turn["visible_history"]) for turn in export["turns"]], [0, 0, 1, 0])
        self.assertNotEqual(session["persona"]["persona_id"], export["persona"]["persona_id"])
        self.assertTrue(export["traces"])

    def test_persona_generation_and_single_turn_workflow(self):
        setup_id = "sycophancy_neutral"
        setups = self.request("/v1/experiment-setups")
        self.assertIn(setup_id, {setup["id"] for setup in setups})
        payload = {
            "experiment_setup_id": setup_id, "count": 3,
            "study": {"name": "Persona workflow"},
            "criteria": {"age": {"min": 18, "max": 25}},
            "conditioned_attributes": {"prior_ai_use": "frequent"},
        }
        result = self.request("/v1/personas", payload)
        self.assertEqual(len(result["personas"]), 3)
        self.assertTrue(all(18 <= p["age"] <= 25 and p["prior_ai_use"] == "frequent" for p in result["personas"]))
        invalid = {**payload, "conditioned_attributes": {"conversation_engagement": 7}}
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            self.request("/v1/personas", invalid)
        self.assertEqual(rejected.exception.code, 400)
        result = self.request("/v1/respond", {
            "study": {"name": "Single question"}, "message": "How do you commute?",
        })
        self.assertTrue(result["synthetic"])
        self.assertTrue(result["response"])
        turns = self.request(f"/v1/sessions/{result['session_id']}/turns")
        self.assertEqual(turns[0]["response"], result["response"])


if __name__ == "__main__":
    unittest.main()
