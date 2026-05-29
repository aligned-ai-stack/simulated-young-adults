from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    provider: str = os.getenv("SIM_PROVIDER", "mock").lower()
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", os.getenv("SIM_MODEL", "llama3.1"))
    vllm_base_url: str = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8001")
    vllm_model: str = os.getenv("VLLM_MODEL", os.getenv("SIM_MODEL", "meta-llama/Llama-3.1-8B-Instruct"))
    vllm_api_key: str = os.getenv("VLLM_API_KEY", "EMPTY")
    llm_request_timeout_seconds: int = int(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "600"))
    database_path: Path = Path(os.getenv("SIM_DB_PATH", "data/simulation.sqlite3"))


def get_settings() -> Settings:
    return Settings()
