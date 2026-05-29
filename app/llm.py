from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol
from urllib import request
from urllib.error import URLError

from app.config import Settings


@dataclass(frozen=True)
class ModelResult:
    response: str
    qualitative_thinking: str | None
    provider_trace: dict[str, Any]


class LLMProvider(Protocol):
    def complete(
        self,
        *,
        system_prompt: str,
        history: list[dict[str, str]],
        message: str,
        persona: dict[str, Any],
        capture_thinking: bool,
    ) -> ModelResult:
        ...


@dataclass
class MockProvider:
    """Development provider that returns a plausible but simple synthetic answer."""

    def complete(
        self,
        *,
        system_prompt: str,
        history: list[dict[str, str]],
        message: str,
        persona: dict[str, Any],
        capture_thinking: bool,
    ) -> ModelResult:
        style = persona.get("survey_style", "conversational")
        age = persona.get("age", "young adult")
        context = persona.get("living_situation", "my current setup")
        thinking = None
        if capture_thinking:
            thinking = (
                f"Used persona cues age={age}, living_situation={context}, "
                f"survey_style={style}, and visible_history_turns={len(history) // 2} "
                "to form a plausible participant response."
            )

        if style == "concise":
            response = f"I'd say it depends, but as a {age}-year-old in {context}, my answer is: {message}"
        elif style == "slightly_uncertain":
            response = f"I'm not totally sure how typical this is, but for me, {message.lower()}"
        elif style == "detail_oriented":
            response = f"For context, I'm {age} and living {context}. My honest response would be: {message}"
        else:
            response = f"Honestly, for me as a {age}-year-old living {context}, {message.lower()}"
        return ModelResult(
            response=response,
            qualitative_thinking=thinking,
            provider_trace={
                "provider": "mock",
                "history_message_count": len(history),
                "capture_thinking": capture_thinking,
            },
        )


@dataclass
class OllamaProvider:
    settings: Settings

    def complete(
        self,
        *,
        system_prompt: str,
        history: list[dict[str, str]],
        message: str,
        persona: dict[str, Any],
        capture_thinking: bool,
    ) -> ModelResult:
        messages = _provider_messages(system_prompt, history, message, capture_thinking)
        payload = {
            "model": self.settings.ollama_model,
            "messages": messages,
            "stream": False,
        }
        if capture_thinking:
            payload["format"] = "json"
        data = _post_json(
            f"{self.settings.ollama_base_url}/api/chat",
            payload,
            timeout_seconds=self.settings.llm_request_timeout_seconds,
        )
        raw_content = data.get("message", {}).get("content", "")
        parsed = _parse_model_output(raw_content, capture_thinking)
        return ModelResult(
            response=parsed["response"] or "",
            qualitative_thinking=parsed["qualitative_thinking"],
            provider_trace={
                "provider": "ollama",
                "model": self.settings.ollama_model,
                "base_url": self.settings.ollama_base_url,
                "raw_content": raw_content,
                "done": data.get("done"),
                "total_duration": data.get("total_duration"),
                "load_duration": data.get("load_duration"),
                "prompt_eval_count": data.get("prompt_eval_count"),
                "eval_count": data.get("eval_count"),
                "capture_thinking": capture_thinking,
            },
        )


@dataclass
class VLLMProvider:
    settings: Settings

    def complete(
        self,
        *,
        system_prompt: str,
        history: list[dict[str, str]],
        message: str,
        persona: dict[str, Any],
        capture_thinking: bool,
    ) -> ModelResult:
        messages = _provider_messages(system_prompt, history, message, capture_thinking)
        payload: dict[str, Any] = {
            "model": self.settings.vllm_model,
            "messages": messages,
            "temperature": 0.8,
        }
        if capture_thinking:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.settings.vllm_api_key}"}
        data = _post_json(
            f"{self.settings.vllm_base_url}/v1/chat/completions",
            payload,
            headers=headers,
            timeout_seconds=self.settings.llm_request_timeout_seconds,
        )
        choice = (data.get("choices") or [{}])[0]
        raw_content = choice.get("message", {}).get("content", "")
        parsed = _parse_model_output(raw_content, capture_thinking)
        usage = data.get("usage", {})
        return ModelResult(
            response=parsed["response"] or "",
            qualitative_thinking=parsed["qualitative_thinking"],
            provider_trace={
                "provider": "vllm",
                "model": self.settings.vllm_model,
                "base_url": self.settings.vllm_base_url,
                "response_id": data.get("id"),
                "finish_reason": choice.get("finish_reason"),
                "usage": usage,
                "raw_content": raw_content,
                "capture_thinking": capture_thinking,
            },
        )


def build_provider(settings: Settings) -> LLMProvider:
    if settings.provider == "mock":
        return MockProvider()
    if settings.provider == "ollama":
        return OllamaProvider(settings)
    if settings.provider == "vllm":
        return VLLMProvider(settings)
    raise ValueError(f"unsupported SIM_PROVIDER={settings.provider!r}")


def _provider_messages(
    system_prompt: str,
    history: list[dict[str, str]],
    message: str,
    capture_thinking: bool,
) -> list[dict[str, str]]:
    final_message = message
    if capture_thinking:
        final_message = (
            f"{message}\n\n"
            "Return valid JSON only, with exactly these keys: "
            "`qualitative_thinking` and `response`. "
            "`qualitative_thinking` must be a concise participant-style self-report "
            "rationale for qualitative coding and debugging, not hidden chain-of-thought. "
            "`response` must contain the final participant answer."
        )
    return [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": final_message},
    ]


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"provider request failed for {url}: {exc}") from exc


def _parse_model_output(output_text: str, capture_thinking: bool) -> dict[str, str | None]:
    if not capture_thinking:
        return {"response": output_text, "qualitative_thinking": None}
    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError:
        return {
            "response": output_text,
            "qualitative_thinking": "Model did not return structured qualitative thinking.",
        }
    response = parsed.get("response")
    qualitative_thinking = parsed.get("qualitative_thinking")
    if isinstance(response, (dict, list)):
        response = json.dumps(response, sort_keys=True)
    return {
        "response": response if isinstance(response, str) else output_text,
        "qualitative_thinking": (
            qualitative_thinking if isinstance(qualitative_thinking, str) else None
        ),
    }
