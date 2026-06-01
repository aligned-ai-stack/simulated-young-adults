from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StudySpec(BaseModel):
    name: str = Field(default="Untitled study")
    description: str = ""
    instructions: str = ""


class CreateSessionRequest(BaseModel):
    study: StudySpec
    experiment_setup_id: str | None = None
    criteria: dict[str, Any] = Field(default_factory=dict)
    conditioned_attributes: dict[str, Any] = Field(default_factory=dict)
    random_seed: int | None = None
    persona_pool_size: int = Field(default=100, ge=1, le=10000)


class PersonaListRequest(BaseModel):
    study: StudySpec
    experiment_setup_id: str | None = None
    count: int = Field(default=1, ge=1, le=500)
    criteria: dict[str, Any] = Field(default_factory=dict)
    conditioned_attributes: dict[str, Any] = Field(default_factory=dict)
    compact: bool = False


class PersonaListResponse(BaseModel):
    synthetic: bool = True
    experiment_setup_id: str | None = None
    count: int
    personas: list[dict[str, Any]]


class SessionResponse(BaseModel):
    session_id: str
    synthetic: bool = True
    experiment_setup_id: str | None = None
    persona: dict[str, Any]
    demographics: dict[str, Any] = Field(default_factory=dict)


class TurnRequest(BaseModel):
    message: str
    stimulus: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    trial_id: str | None = None
    trial_index: int | None = None
    reset_policy: Literal["carryover", "trial", "full"] = "carryover"
    response_mode: Literal["survey", "interview", "chat", "experiment"] = "survey"
    capture_thinking: bool = True


class TurnResponse(BaseModel):
    session_id: str
    turn_id: int
    synthetic: bool = True
    experiment_setup_id: str | None = None
    trial_id: str | None = None
    reset_policy: Literal["carryover", "trial", "full"]
    qualitative_thinking: str | None = None
    response: str


class SingleTurnResponse(TurnResponse):
    pass


class SingleTurnRequest(CreateSessionRequest):
    message: str
    stimulus: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    trial_id: str | None = None
    trial_index: int | None = None
    response_mode: Literal["survey", "interview", "chat", "experiment"] = "survey"
    capture_thinking: bool = True


class SessionDemographicsRequest(BaseModel):
    demographics: dict[str, Any] = Field(default_factory=dict)


class SessionDemographicsResponse(BaseModel):
    session_id: str
    synthetic: bool = True
    persona: dict[str, Any]
    demographics: dict[str, Any]


class ExperimentSetupResponse(BaseModel):
    id: str
    name: str
    description: str
    default_criteria: dict[str, Any]
    statement_count_per_run: int
    response_questions: list[str]


class PersonaPoolRequest(BaseModel):
    criteria: dict[str, Any] = Field(default_factory=dict)
    conditioned_attributes: dict[str, Any] = Field(default_factory=dict)
    pool_size: int = Field(default=100, ge=1, le=10000)
    random_seed: int | None = None


class PersonaPoolResponse(BaseModel):
    persona_pool_id: str
    experiment_setup_id: str
    size: int


class StoredTurnResponse(BaseModel):
    turn_id: int
    session_id: str
    created_at: str
    message: str
    stimulus: dict[str, Any]
    metadata: dict[str, Any]
    response: str
    qualitative_thinking: str | None = None
    trial_id: str | None = None
    trial_index: int | None = None
    reset_policy: str
    response_mode: str
    persona: dict[str, Any] | None = None
    request: dict[str, Any]
    trial_context: dict[str, Any]
    visible_history: list[dict[str, Any]]
    system_prompt: str
    provider_trace: dict[str, Any]


class TraceEventResponse(BaseModel):
    trace_id: int
    session_id: str
    turn_id: int | None = None
    created_at: str
    event_type: str
    event: dict[str, Any]


class SessionExportResponse(BaseModel):
    session: dict[str, Any]
    experiment_setup: dict[str, Any] | None = None
    persona: dict[str, Any]
    demographics: dict[str, Any]
    turns: list[StoredTurnResponse]
    traces: list[TraceEventResponse]
