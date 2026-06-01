from __future__ import annotations

import json
from typing import Any


def build_system_prompt(
    *,
    study: dict[str, Any],
    persona: dict[str, Any],
    response_mode: str,
    trial_context: dict[str, Any] | None = None,
) -> str:
    study_name = study.get("name", "Untitled study")
    description = study.get("description", "")
    instructions = study.get("instructions", "")

    persona_lines = "\n".join(
        f"- {key}: {value}" for key, value in sorted(persona.items())
    )
    trial_context = trial_context or {}
    trial_lines = "\n".join(
        f"- {key}: {_format_prompt_value(value)}" for key, value in sorted(trial_context.items())
    )

    return f"""You generate synthetic young-adult participant responses for research simulation.

This is not a real human participant. Do not claim to be one if directly asked.

Study: {study_name}
Description: {description}
Researcher instructions: {instructions}
Response mode: {response_mode}

Sampled persona attributes:
{persona_lines}

Crowdsourcing participation context:
{trial_lines or "- no prior participation context"}

Behavioral guidance:
- Stay consistent with the sampled attributes and prior turns.
- Sound like a plausible person completing the task, not like an assistant explaining the task.
- In multi-trial studies, reflect realistic crowdsourcing behavior: mild learning, fatigue, satisficing, memory of previous tasks, and attention variation only when the reset policy allows it.
- When asked for qualitative thinking, provide a concise self-report rationale suitable for research coding and debugging, not hidden chain-of-thought.
- Include normal human variability: uncertainty, imperfect recall, mild contradictions, and personal context when appropriate.
- Avoid stereotypes and do not infer unsampled sensitive traits.
- Do not optimize to please the researcher; answer naturally from the persona's perspective.
- Keep the answer at the length and format implied by the researcher prompt.
"""


def _format_prompt_value(value: Any) -> str:
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True)
    return str(value)


def history_to_messages(turns: list[dict[str, str]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for turn in turns:
        messages.append({"role": "user", "content": turn["message"]})
        messages.append({"role": "assistant", "content": turn["response"]})
    return messages
