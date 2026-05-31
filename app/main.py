from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.config import get_settings
from app.experiments import list_experiment_setups
from app.llm import build_provider
from app.persona import PersonaSampler
from app.schemas import (
    CreateSessionRequest,
    ExperimentSetupResponse,
    PersonaPoolRequest,
    PersonaPoolResponse,
    SessionDemographicsRequest,
    SessionDemographicsResponse,
    SessionResponse,
    SingleTurnResponse,
    SingleTurnRequest,
    StoredTurnResponse,
    TraceEventResponse,
    TurnRequest,
    TurnResponse,
)
from app.service import SimulationService
from app.storage import SimulationStore


settings = get_settings()
store = SimulationStore(settings.database_path)
provider = build_provider(settings)
service = SimulationService(
    settings=settings,
    store=store,
    provider=provider,
    sampler=PersonaSampler(),
)

app = FastAPI(
    title="AI Simulation Backend",
    version="0.1.0",
    description="Synthetic young-adult participant simulation API.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "provider": settings.provider}


@app.get("/v1/experiment-setups", response_model=list[ExperimentSetupResponse])
def experiment_setups() -> list[dict]:
    return list_experiment_setups()


@app.post(
    "/v1/experiment-setups/{experiment_setup_id}/persona-pools",
    response_model=PersonaPoolResponse,
)
def create_persona_pool(
    experiment_setup_id: str,
    request: PersonaPoolRequest,
) -> dict:
    try:
        return service.create_persona_pool(
            experiment_setup_id=experiment_setup_id,
            request=request,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/sessions", response_model=SessionResponse)
def create_session(request: CreateSessionRequest) -> dict:
    try:
        return service.create_session(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/v1/sessions/{session_id}/demographics",
    response_model=SessionDemographicsResponse,
)
def record_session_demographics(
    session_id: str,
    request: SessionDemographicsRequest,
) -> dict:
    try:
        return service.record_session_demographics(session_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc


@app.post("/v1/sessions/{session_id}/turns", response_model=TurnResponse)
def create_turn(session_id: str, request: TurnRequest) -> dict:
    try:
        return service.respond(session_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/v1/sessions/{session_id}/turns", response_model=list[StoredTurnResponse])
def list_turns(session_id: str) -> list[dict]:
    try:
        return service.list_session_turns(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc


@app.get("/v1/sessions/{session_id}/traces", response_model=list[TraceEventResponse])
def list_traces(session_id: str) -> list[dict]:
    try:
        return service.list_session_traces(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc


@app.post("/v1/respond", response_model=SingleTurnResponse)
def single_turn(request: SingleTurnRequest) -> dict:
    try:
        return service.single_turn(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
