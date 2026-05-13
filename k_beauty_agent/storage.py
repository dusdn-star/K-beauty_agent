from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import session_secret, sqlite_path_from_url

RETENTION_DAYS = 30


class SQLiteStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else sqlite_path_from_url()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init_db(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL DEFAULT '{}',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    query TEXT NOT NULL,
                    response_json TEXT,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    recommendation_id INTEGER,
                    target TEXT NOT NULL,
                    product_id TEXT,
                    feedback TEXT NOT NULL,
                    reason_tags TEXT NOT NULL DEFAULT '[]',
                    comment TEXT,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS openai_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    error TEXT,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS app_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_hash TEXT,
                    request_id TEXT,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    latency_ms INTEGER,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS selections (
                    session_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    list_type TEXT NOT NULL,
                    selected INTEGER NOT NULL DEFAULT 1,
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY (session_id, product_id, list_type)
                );
                CREATE INDEX IF NOT EXISTS idx_turns_session_created ON conversation_turns(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_feedback_session_created ON feedback(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_recommendations_created ON recommendations(created_at);
                CREATE INDEX IF NOT EXISTS idx_events_created ON app_events(created_at);
                CREATE INDEX IF NOT EXISTS idx_selections_session_type ON selections(session_id, list_type);
                """
            )

    def ensure_session(self, session_id: str) -> dict[str, Any]:
        now = _now()
        expires_at = now + RETENTION_DAYS * 86400
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO sessions(session_id, profile_json, created_at, updated_at, expires_at) VALUES (?, '{}', ?, ?, ?)",
                    (session_id, now, now, expires_at),
                )
                return {"session_id": session_id, "profile": {}, "created_at": now, "updated_at": now}
            connection.execute(
                "UPDATE sessions SET updated_at = ?, expires_at = ? WHERE session_id = ?",
                (now, expires_at, session_id),
            )
            return {
                "session_id": row["session_id"],
                "profile": json.loads(row["profile_json"] or "{}"),
                "created_at": row["created_at"],
                "updated_at": now,
            }

    def save_profile(self, session_id: str, profile: dict[str, Any]) -> None:
        now = _now()
        with self.connect() as connection:
            connection.execute(
                "UPDATE sessions SET profile_json = ?, updated_at = ? WHERE session_id = ?",
                (json.dumps(profile, ensure_ascii=False), now, session_id),
            )

    def recent_queries(self, session_id: str, limit: int = 5) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT query FROM conversation_turns WHERE session_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [row["query"] for row in reversed(rows)]

    def add_turn(self, session_id: str, role: str, query: str, response: dict[str, Any] | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO conversation_turns(session_id, role, query, response_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, query, json.dumps(response or {}, ensure_ascii=False), _now()),
            )

    def add_recommendation(
        self,
        session_id: str,
        query: str,
        decision: str,
        result: dict[str, Any],
        latency_ms: int,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO recommendations(session_id, query, decision, result_json, latency_ms, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, query, decision, json.dumps(result, ensure_ascii=False), latency_ms, _now()),
            )
            return int(cursor.lastrowid)

    def add_feedback(
        self,
        session_id: str,
        target: str,
        feedback: str,
        recommendation_id: int | None = None,
        product_id: str | None = None,
        reason_tags: list[str] | None = None,
        comment: str | None = None,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO feedback(session_id, recommendation_id, target, product_id, feedback, reason_tags, comment, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    recommendation_id,
                    target,
                    product_id,
                    feedback,
                    json.dumps(reason_tags or []),
                    comment,
                    _now(),
                ),
            )
            return int(cursor.lastrowid)

    def feedback_for_session(self, session_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM feedback WHERE session_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_selection(self, session_id: str, product_id: str, list_type: str, selected: bool) -> None:
        now = _now()
        with self.connect() as connection:
            if selected:
                connection.execute(
                    """
                    INSERT INTO selections(session_id, product_id, list_type, selected, updated_at)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(session_id, product_id, list_type)
                    DO UPDATE SET selected = 1, updated_at = excluded.updated_at
                    """,
                    (session_id, product_id, list_type, now),
                )
            else:
                connection.execute(
                    "DELETE FROM selections WHERE session_id = ? AND product_id = ? AND list_type = ?",
                    (session_id, product_id, list_type),
                )

    def selections_for_session(self, session_id: str) -> dict[str, list[str]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT product_id, list_type
                FROM selections
                WHERE session_id = ? AND selected = 1
                ORDER BY updated_at ASC
                """,
                (session_id,),
            ).fetchall()
        selections = {"saved": [], "compare": []}
        for row in rows:
            list_type = row["list_type"]
            if list_type in selections:
                selections[list_type].append(row["product_id"])
        return selections

    def record_openai_call(self, session_id: str | None, model: str, status: str, latency_ms: int, error: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO openai_calls(session_id, model, status, latency_ms, error, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, model, status, latency_ms, error, _now()),
            )

    def log_event(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
        latency_ms: int | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO app_events(session_hash, request_id, event_type, payload_json, latency_ms, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    hash_session(session_id) if session_id else None,
                    request_id,
                    event_type,
                    json.dumps(payload or {}, ensure_ascii=False),
                    latency_ms,
                    _now(),
                ),
            )

    def delete_session(self, session_id: str) -> None:
        with self.connect() as connection:
            for table in ("sessions", "conversation_turns", "recommendations", "feedback", "openai_calls", "selections"):
                connection.execute(f"DELETE FROM {table} WHERE session_id = ?", (session_id,))

    def cleanup_expired(self, retention_days: int = RETENTION_DAYS) -> int:
        cutoff = _now() - retention_days * 86400
        deleted = 0
        with self.connect() as connection:
            for table in ("conversation_turns", "recommendations", "feedback", "openai_calls", "app_events"):
                cursor = connection.execute(f"DELETE FROM {table} WHERE created_at < ?", (cutoff,))
                deleted += cursor.rowcount
            cursor = connection.execute("DELETE FROM selections WHERE updated_at < ?", (cutoff,))
            deleted += cursor.rowcount
            cursor = connection.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))
            deleted += cursor.rowcount
        return deleted

    def metrics(self) -> dict[str, Any]:
        with self.connect() as connection:
            total_sessions = _count(connection, "sessions")
            total_recommendations = _count(connection, "recommendations")
            fallback = _count_where(connection, "recommendations", "decision = 'fallback'")
            ask_more = _count_where(connection, "recommendations", "decision = 'ask_more'")
            liked = _count_where(connection, "feedback", "feedback = 'liked'")
            disliked = _count_where(connection, "feedback", "feedback = 'disliked'")
            openai_failures = _count_where(connection, "openai_calls", "status != 'ok'")
            latencies = [row["latency_ms"] for row in connection.execute("SELECT latency_ms FROM recommendations").fetchall()]
            recent_errors = [
                dict(row)
                for row in connection.execute(
                    "SELECT event_type, payload_json, created_at FROM app_events WHERE event_type LIKE '%error%' ORDER BY created_at DESC LIMIT 10"
                ).fetchall()
            ]
            top_feedback = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT product_id, feedback, COUNT(*) AS count
                    FROM feedback
                    WHERE product_id IS NOT NULL
                    GROUP BY product_id, feedback
                    ORDER BY count DESC
                    LIMIT 12
                    """
                ).fetchall()
            ]
        return {
            "total_sessions": total_sessions,
            "total_recommendations": total_recommendations,
            "fallback_rate": _rate(fallback, total_recommendations),
            "ask_more_rate": _rate(ask_more, total_recommendations),
            "liked_count": liked,
            "disliked_count": disliked,
            "openai_failure_count": openai_failures,
            "latency_p50_ms": _percentile(latencies, 50),
            "latency_p95_ms": _percentile(latencies, 95),
            "top_feedback": top_feedback,
            "recent_errors": recent_errors,
        }


def hash_session(session_id: str | None) -> str | None:
    if not session_id:
        return None
    return hmac.new(session_secret().encode("utf-8"), session_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def _now() -> int:
    return int(time.time())


def _count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"])


def _count_where(connection: sqlite3.Connection, table: str, where: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE {where}").fetchone()["count"])


def _rate(value: int, total: int) -> float:
    return round(value / total, 4) if total else 0.0


def _percentile(values: list[int], percentile: int) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((percentile / 100) * (len(ordered) - 1)))
    return int(ordered[index])
