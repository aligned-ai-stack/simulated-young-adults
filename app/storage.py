from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from typing import Any


class SimulationStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    experiment_setup_id TEXT,
                    persona_pool_id TEXT,
                    persona_pool_member_id TEXT,
                    study_json TEXT NOT NULL,
                    criteria_json TEXT NOT NULL,
                    conditioned_json TEXT NOT NULL,
                    persona_json TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    provider TEXT NOT NULL
                )
                """
            )
            self._ensure_session_column(conn, "experiment_setup_id", "TEXT")
            self._ensure_session_column(conn, "persona_pool_id", "TEXT")
            self._ensure_session_column(conn, "persona_pool_member_id", "TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    message TEXT NOT NULL,
                    stimulus_json TEXT NOT NULL DEFAULT '{}',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    response TEXT NOT NULL,
                    qualitative_thinking TEXT,
                    trial_id TEXT,
                    trial_index INTEGER,
                    reset_policy TEXT NOT NULL DEFAULT 'carryover',
                    persona_json TEXT,
                    response_mode TEXT NOT NULL,
                    request_json TEXT NOT NULL DEFAULT '{}',
                    system_prompt TEXT NOT NULL DEFAULT '',
                    visible_history_json TEXT NOT NULL DEFAULT '[]',
                    trial_context_json TEXT NOT NULL DEFAULT '{}',
                    provider_trace_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
                """
            )
            self._ensure_turn_column(conn, "stimulus_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_turn_column(conn, "metadata_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_turn_column(conn, "qualitative_thinking", "TEXT")
            self._ensure_turn_column(conn, "trial_id", "TEXT")
            self._ensure_turn_column(conn, "trial_index", "INTEGER")
            self._ensure_turn_column(conn, "reset_policy", "TEXT NOT NULL DEFAULT 'carryover'")
            self._ensure_turn_column(conn, "persona_json", "TEXT")
            self._ensure_turn_column(conn, "request_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_turn_column(conn, "system_prompt", "TEXT NOT NULL DEFAULT ''")
            self._ensure_turn_column(conn, "visible_history_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_turn_column(conn, "trial_context_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_turn_column(conn, "provider_trace_json", "TEXT NOT NULL DEFAULT '{}'")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trace_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id),
                    FOREIGN KEY(turn_id) REFERENCES turns(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS persona_pools (
                    id TEXT PRIMARY KEY,
                    experiment_setup_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    criteria_json TEXT NOT NULL,
                    conditioned_json TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    size INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS persona_pool_members (
                    id TEXT PRIMARY KEY,
                    pool_id TEXT NOT NULL,
                    persona_json TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    assigned_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(pool_id) REFERENCES persona_pools(id)
                )
                """
            )

    def _ensure_session_column(
        self,
        conn: sqlite3.Connection,
        column_name: str,
        column_type: str,
    ) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
        }
        if column_name not in columns:
            conn.execute(f"ALTER TABLE sessions ADD COLUMN {column_name} {column_type}")

    def _ensure_turn_column(
        self,
        conn: sqlite3.Connection,
        column_name: str,
        column_type: str,
    ) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(turns)").fetchall()
        }
        if column_name not in columns:
            conn.execute(f"ALTER TABLE turns ADD COLUMN {column_name} {column_type}")

    def create_session(
        self,
        *,
        session_id: str,
        experiment_setup_id: str | None,
        persona_pool_id: str | None,
        persona_pool_member_id: str | None,
        study: dict[str, Any],
        criteria: dict[str, Any],
        conditioned_attributes: dict[str, Any],
        persona: dict[str, Any],
        seed: int,
        provider: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    id, experiment_setup_id, persona_pool_id, persona_pool_member_id,
                    study_json, criteria_json, conditioned_json, persona_json, seed, provider
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    experiment_setup_id,
                    persona_pool_id,
                    persona_pool_member_id,
                    json.dumps(study),
                    json.dumps(criteria),
                    json.dumps(conditioned_attributes),
                    json.dumps(persona),
                    seed,
                    provider,
                ),
            )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "experiment_setup_id": row["experiment_setup_id"],
            "persona_pool_id": row["persona_pool_id"],
            "persona_pool_member_id": row["persona_pool_member_id"],
            "study": json.loads(row["study_json"]),
            "criteria": json.loads(row["criteria_json"]),
            "conditioned_attributes": json.loads(row["conditioned_json"]),
            "persona": json.loads(row["persona_json"]),
            "seed": row["seed"],
            "provider": row["provider"],
        }

    def add_turn(
        self,
        *,
        session_id: str,
        message: str,
        stimulus: dict[str, Any],
        metadata: dict[str, Any],
        response: str,
        qualitative_thinking: str | None,
        trial_id: str | None,
        trial_index: int | None,
        reset_policy: str,
        persona: dict[str, Any],
        response_mode: str,
        request: dict[str, Any],
        system_prompt: str,
        visible_history: list[dict[str, Any]],
        trial_context: dict[str, Any],
        provider_trace: dict[str, Any],
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO turns (
                    session_id, message, stimulus_json, metadata_json, response,
                    qualitative_thinking, trial_id, trial_index, reset_policy,
                    persona_json, response_mode, request_json, system_prompt,
                    visible_history_json, trial_context_json, provider_trace_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    message,
                    json.dumps(stimulus, sort_keys=True),
                    json.dumps(metadata, sort_keys=True),
                    response,
                    qualitative_thinking,
                    trial_id,
                    trial_index,
                    reset_policy,
                    json.dumps(persona),
                    response_mode,
                    json.dumps(request, sort_keys=True),
                    system_prompt,
                    json.dumps(visible_history, sort_keys=True),
                    json.dumps(trial_context, sort_keys=True),
                    json.dumps(provider_trace, sort_keys=True),
                ),
            )
            return int(cursor.lastrowid)

    def list_turns(
        self,
        session_id: str,
        *,
        trial_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT id, session_id, message, stimulus_json, metadata_json, response,
                   qualitative_thinking, response_mode, created_at, trial_id,
                   trial_index, reset_policy, persona_json, request_json,
                   system_prompt, visible_history_json, trial_context_json,
                   provider_trace_json
            FROM turns
            WHERE session_id = ?
        """
        params: list[Any] = [session_id]
        if trial_id is not None:
            query += " AND trial_id = ?"
            params.append(trial_id)
        query += " ORDER BY id ASC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "turn_id": row["id"],
                "session_id": row["session_id"],
                "message": row["message"],
                "stimulus": json.loads(row["stimulus_json"]),
                "metadata": json.loads(row["metadata_json"]),
                "response": row["response"],
                "qualitative_thinking": row["qualitative_thinking"],
                "response_mode": row["response_mode"],
                "created_at": row["created_at"],
                "trial_id": row["trial_id"],
                "trial_index": row["trial_index"],
                "reset_policy": row["reset_policy"],
                "persona": json.loads(row["persona_json"]) if row["persona_json"] else None,
                "request": json.loads(row["request_json"]),
                "system_prompt": row["system_prompt"],
                "visible_history": json.loads(row["visible_history_json"]),
                "trial_context": json.loads(row["trial_context_json"]),
                "provider_trace": json.loads(row["provider_trace_json"]),
            }
            for row in rows
        ]

    def add_trace_event(
        self,
        *,
        session_id: str,
        turn_id: int | None,
        event_type: str,
        event: dict[str, Any],
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO trace_events (session_id, turn_id, event_type, event_json)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, turn_id, event_type, json.dumps(event, sort_keys=True)),
            )
            return int(cursor.lastrowid)

    def list_trace_events(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, turn_id, created_at, event_type, event_json
                FROM trace_events
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        return [
            {
                "trace_id": row["id"],
                "session_id": row["session_id"],
                "turn_id": row["turn_id"],
                "created_at": row["created_at"],
                "event_type": row["event_type"],
                "event": json.loads(row["event_json"]),
            }
            for row in rows
        ]

    def replace_session_persona(
        self,
        *,
        session_id: str,
        persona: dict[str, Any],
        seed: int,
        persona_pool_member_id: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET persona_json = ?, seed = ?, persona_pool_member_id = ?
                WHERE id = ?
                """,
                (json.dumps(persona), seed, persona_pool_member_id, session_id),
            )

    def create_persona_pool(
        self,
        *,
        pool_id: str,
        experiment_setup_id: str,
        criteria: dict[str, Any],
        conditioned_attributes: dict[str, Any],
        seed: int,
        members: list[dict[str, Any]],
    ) -> None:
        criteria_json = _stable_json(criteria)
        conditioned_json = _stable_json(conditioned_attributes)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO persona_pools (
                    id, experiment_setup_id, criteria_json, conditioned_json, seed, size
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    pool_id,
                    experiment_setup_id,
                    criteria_json,
                    conditioned_json,
                    seed,
                    len(members),
                ),
            )
            conn.executemany(
                """
                INSERT INTO persona_pool_members (id, pool_id, persona_json, seed)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        member["id"],
                        pool_id,
                        json.dumps(member["persona"], sort_keys=True),
                        member["seed"],
                    )
                    for member in members
                ],
            )

    def add_persona_pool_members(
        self,
        *,
        pool_id: str,
        members: list[dict[str, Any]],
    ) -> None:
        if not members:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO persona_pool_members (id, pool_id, persona_json, seed)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        member["id"],
                        pool_id,
                        json.dumps(member["persona"], sort_keys=True),
                        member["seed"],
                    )
                    for member in members
                ],
            )
            conn.execute(
                """
                UPDATE persona_pools
                SET size = size + ?
                WHERE id = ?
                """,
                (len(members), pool_id),
            )

    def find_persona_pool(
        self,
        *,
        experiment_setup_id: str,
        criteria: dict[str, Any],
        conditioned_attributes: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM persona_pools
                WHERE experiment_setup_id = ?
                  AND criteria_json = ?
                  AND conditioned_json = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (
                    experiment_setup_id,
                    _stable_json(criteria),
                    _stable_json(conditioned_attributes),
                ),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "experiment_setup_id": row["experiment_setup_id"],
            "criteria": json.loads(row["criteria_json"]),
            "conditioned_attributes": json.loads(row["conditioned_json"]),
            "seed": row["seed"],
            "size": row["size"],
        }

    def get_persona_pool(self, pool_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM persona_pools WHERE id = ?",
                (pool_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "experiment_setup_id": row["experiment_setup_id"],
            "criteria": json.loads(row["criteria_json"]),
            "conditioned_attributes": json.loads(row["conditioned_json"]),
            "seed": row["seed"],
            "size": row["size"],
        }

    def allocate_persona_from_pool(self, pool_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM persona_pool_members
                WHERE pool_id = ?
                ORDER BY assigned_count ASC, id ASC
                LIMIT 1
                """,
                (pool_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"persona pool has no members: {pool_id}")
            conn.execute(
                """
                UPDATE persona_pool_members
                SET assigned_count = assigned_count + 1
                WHERE id = ?
                """,
                (row["id"],),
            )
        return {
            "id": row["id"],
            "pool_id": row["pool_id"],
            "persona": json.loads(row["persona_json"]),
            "seed": row["seed"],
            "assigned_count": row["assigned_count"],
        }


def _stable_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
