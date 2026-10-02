from __future__ import annotations

import random
import secrets
import uuid
from dataclasses import dataclass
from typing import Any

from app.causal import CausalPersonaGenerator, get_causal_model


YOUNG_ADULT_AGE_MIN = 18
YOUNG_ADULT_AGE_MAX = 29


@dataclass(frozen=True)
class PersonaSample:
    persona_id: str
    seed: int
    attributes: dict[str, Any]
    causal_trace: dict[str, Any]


class PersonaSampler:
    """Samples personas from an executable study-specific structural causal model."""

    def __init__(self) -> None:
        self.generator = CausalPersonaGenerator()

    def sample(
        self,
        criteria: dict[str, Any] | None = None,
        conditioned_attributes: dict[str, Any] | None = None,
        random_seed: int | None = None,
        experiment_setup_id: str | None = None,
    ) -> PersonaSample:
        seed = random_seed if random_seed is not None else secrets.randbits(63)
        rng = random.Random(seed)
        criteria = criteria or {}
        conditioned_attributes = conditioned_attributes or {}

        age = conditioned_attributes.get("age")
        if age is not None and not YOUNG_ADULT_AGE_MIN <= int(age) <= YOUNG_ADULT_AGE_MAX:
            raise ValueError("conditioned age must be between 18 and 29")

        result = self.generator.sample(
            model=get_causal_model(experiment_setup_id),
            criteria=criteria,
            interventions=conditioned_attributes,
            rng=rng,
        )
        return PersonaSample(
            persona_id=f"persona_{uuid.uuid4().hex[:12]}",
            seed=seed,
            attributes=result.attributes,
            causal_trace=result.trace,
        )
