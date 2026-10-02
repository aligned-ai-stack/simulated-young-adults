from __future__ import annotations

import unittest
import os
import subprocess
import sys

from app.causal import MODEL_FAMILIES, get_causal_model
from app.persona import PersonaSampler


class CausalGraphTests(unittest.TestCase):
    def test_randomized_condition_has_no_open_backdoor_path(self) -> None:
        model = get_causal_model("sycophancy_sycophantic")

        report = model.diagnostics()["adjustment"]

        self.assertEqual(report["identified_confounders"], [])
        self.assertTrue(report["valid_adjustment_set"])
        self.assertTrue(all(report["backdoor_d_separated"].values()))

    def test_conditioning_on_collider_opens_an_otherwise_closed_path(self) -> None:
        graph = get_causal_model("sycophancy_neutral").graph

        self.assertTrue(
            graph.d_separated("llm_condition", "openness_to_change")
        )
        self.assertFalse(
            graph.d_separated(
                "llm_condition",
                "openness_to_change",
                {"conversation_engagement"},
            )
        )

    def test_each_experiment_setup_resolves_to_a_study_model(self) -> None:
        for setup_id, family in MODEL_FAMILIES.items():
            with self.subTest(setup_id=setup_id):
                model = get_causal_model(setup_id)
                self.assertEqual(model.setup_id, setup_id)
                self.assertEqual(model.family, family)
                self.assertGreater(len(model.graph.nodes), 60)


class CausalPersonaTests(unittest.TestCase):
    def test_seed_is_reproducible_across_python_processes(self) -> None:
        code = (
            "import json; from app.persona import PersonaSampler; "
            "print(json.dumps(PersonaSampler().sample(random_seed=44).attributes, sort_keys=True))"
        )
        outputs = [
            subprocess.check_output(
                [sys.executable, "-c", code],
                env={**os.environ, "PYTHONHASHSEED": str(hash_seed)},
                text=True,
            )
            for hash_seed in (1, 2, 3)
        ]
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])

    def test_outcomes_mediators_and_colliders_cannot_define_personas(self) -> None:
        sampler = PersonaSampler()

        for blocked in ["trust_in_llm", "perceived_agreement", "conversation_engagement"]:
            with self.subTest(blocked=blocked), self.assertRaises(ValueError):
                sampler.sample(
                    experiment_setup_id="sycophancy_neutral",
                    conditioned_attributes={blocked: 7},
                    random_seed=20,
                )

    def test_baseline_intervention_propagates_to_descendants(self) -> None:
        sampler = PersonaSampler()
        low_use = sampler.sample(
            experiment_setup_id="truth_source_unlabeled",
            conditioned_attributes={"prior_ai_use": "none"},
            random_seed=44,
        )
        high_use = sampler.sample(
            experiment_setup_id="truth_source_unlabeled",
            conditioned_attributes={"prior_ai_use": "frequent"},
            random_seed=44,
        )

        self.assertEqual(low_use.attributes["prior_ai_use"], "none")
        self.assertEqual(high_use.attributes["prior_ai_use"], "frequent")
        self.assertGreater(
            high_use.attributes["ai_familiarity"],
            low_use.attributes["ai_familiarity"],
        )
        self.assertGreaterEqual(
            high_use.attributes["ai_literacy"],
            low_use.attributes["ai_literacy"],
        )

    def test_eligibility_is_sampled_as_evidence_not_overwritten(self) -> None:
        sample = PersonaSampler().sample(
            experiment_setup_id="cognitive_load_high_load",
            criteria={"ai_literacy": {"min": 6, "max": 7}},
            random_seed=81,
        )

        self.assertGreaterEqual(sample.attributes["ai_literacy"], 6)
        self.assertGreater(sample.causal_trace["attempts"], 0)
        self.assertEqual(
            sample.causal_trace["node_sources"]["ai_literacy"],
            "structural_equation",
        )

    def test_trace_keeps_latents_separate_from_public_persona(self) -> None:
        sample = PersonaSampler().sample(
            experiment_setup_id="climate_thinking_partner_socratic",
            random_seed=18,
        )

        self.assertNotIn("_family_ses", sample.attributes)
        self.assertIn("_family_ses", sample.causal_trace["latent_state"])
        self.assertEqual(
            sample.causal_trace["model_family"],
            "climate_partner",
        )


if __name__ == "__main__":
    unittest.main()
