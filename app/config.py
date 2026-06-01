from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    provider: str = field(default_factory=lambda: os.getenv("SIM_PROVIDER", "ollama").lower())
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", os.getenv("SIM_MODEL", "llama3.1"))
    )
    vllm_base_url: str = field(
        default_factory=lambda: os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8001")
    )
    vllm_model: str = field(
        default_factory=lambda: os.getenv(
            "VLLM_MODEL",
            os.getenv("SIM_MODEL", "meta-llama/Llama-3.1-8B-Instruct"),
        )
    )
    vllm_api_key: str = field(default_factory=lambda: os.getenv("VLLM_API_KEY", "EMPTY"))
    llm_request_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "600"))
    )
    database_path: Path = field(
        default_factory=lambda: Path(os.getenv("SIM_DB_PATH", "data/simulation.sqlite3"))
    )


def get_settings() -> Settings:
    return Settings()
