from __future__ import annotations

import unittest

from app.config import Settings
from app.llm import MockProvider, OllamaProvider, VLLMProvider, _parse_model_output, build_provider


class ProviderSelectionTests(unittest.TestCase):
    def test_self_hosted_providers_are_supported(self) -> None:
        self.assertIsInstance(build_provider(Settings(provider="ollama")), OllamaProvider)
        self.assertIsInstance(build_provider(Settings(provider="vllm")), VLLMProvider)

    def test_mock_is_only_dev_provider(self) -> None:
        self.assertIsInstance(build_provider(Settings(provider="mock")), MockProvider)

    def test_external_openai_provider_is_not_supported(self) -> None:
        with self.assertRaises(ValueError):
            build_provider(Settings(provider="openai"))

    def test_structured_response_is_separated_from_qualitative_thinking(self) -> None:
        parsed = _parse_model_output(
            '{"qualitative_thinking":"rationale","response":{"truth":"true","confidence":6}}',
            True,
        )

        self.assertEqual(parsed["qualitative_thinking"], "rationale")
        self.assertEqual(parsed["response"], '{"confidence": 6, "truth": "true"}')


if __name__ == "__main__":
    unittest.main()
