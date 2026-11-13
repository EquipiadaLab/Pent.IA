"""Persistencia SQLite da Plataforma (Trilho B).

Tabelas: campaigns, moves, events, audit.
- ``events`` e ``audit`` sao append-only (nunca UPDATE/DELETE).
- ``campaigns`` e ``moves`` guardam o estado corrente (upsert).
Objetos ricos do contrato sao serializados como JSON; colunas "planas"
existem so para consultas/ordenacao.

sqlite3 e sincrono; para nao travar o event loop as operacoes rodam em
``asyncio.to_thread`` e uma unica conexao (check_same_thread=False) e
protegida por um lock.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.models import (
    AuditEntry,
    Campaign,
    CampaignConfig,
    CampaignState,
    Event,
    Move,
    Score,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    id          TEXT PRIMARY KEY,
    state       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    finished_at TEXT,
    config_json TEXT NOT NULL,
    score_json  TEXT
);

CREATE TABLE IF NOT EXISTS moves (
    campaign_id TEXT NOT NULL,
    move        INTEGER NOT NULL,
    approval    TEXT NOT NULL,
    status      TEXT,
    grade       TEXT,
    move_json   TEXT NOT NULL,
    PRIMARY KEY (campaign_id, move),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE IF NOT EXISTS events (
    seq         INTEGER NOT NULL,
    campaign_id TEXT NOT NULL,
    type        TEXT NOT NULL,
    at          TEXT NOT NULL,
    event_json  TEXT NOT NULL,
    PRIMARY KEY (campaign_id, seq)
);

CREATE TABLE IF NOT EXISTS audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    at          TEXT NOT NULL,
    entry_json  TEXT NOT NULL
);

-- Autenticacao: contas criadas pelo sistema (admin), nunca por cadastro aberto.
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'operator',
    created_at    TEXT NOT NULL
);

-- Configuracoes mutaveis geridas pelo admin (ex.: alvos autorizados, escopos bloqueados).
CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Database:
    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- infra -----------------------------------------------------------
    async def _run(self, fn, *args):
        return await asyncio.to_thread(self._sync, fn, *args)

    def _sync(self, fn, *args):
        with self._lock:
            result = fn(self._conn, *args)
            self._conn.commit()
            return result

    # ---- campaigns -------------------------------------------------------
    async def create_campaign(self, campaign: Campaign) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO campaigns (id, state, created_at, finished_at, config_json, score_json)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    campaign.id,
                    campaign.state.value,
                    campaign.created_at.isoformat(),
                    campaign.finished_at.isoformat() if campaign.finished_at else None,
                    campaign.config.model_dump_json(),
                    campaign.score.model_dump_json() if campaign.score else None,
                ),
            )

        await self._run(_do)

    async def set_state(
        self, campaign_id: str, state: CampaignState, *, finished: bool = False
    ) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            if finished:
                conn.execute(
                    "UPDATE campaigns SET state = ?, finished_at = ? WHERE id = ?",
                    (state.value, _utcnow().isoformat(), campaign_id),
                )
            else:
                conn.execute(
                    "UPDATE campaigns SET state = ? WHERE id = ?",
                    (state.value, campaign_id),
                )

        await self._run(_do)

    async def set_score(self, campaign_id: str, score: Score) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE campaigns SET score_json = ? WHERE id = ?",
                (score.model_dump_json(), campaign_id),
            )

        await self._run(_do)

    async def get_state(self, campaign_id: str) -> CampaignState | None:
        def _do(conn: sqlite3.Connection) -> CampaignState | None:
            row = conn.execute(
                "SELECT state FROM campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()
            return CampaignState(row["state"]) if row else None

        return await self._run(_do)

    async def get_campaign(self, campaign_id: str) -> Campaign | None:
        def _do(conn: sqlite3.Connection) -> Campaign | None:
            row = conn.execute(
                "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
            ).fetchone()
            if row is None:
                return None
            moves = [
                Move.model_validate_json(m["move_json"])
                for m in conn.execute(
                    "SELECT move_json FROM moves WHERE campaign_id = ? ORDER BY move",
                    (campaign_id,),
                ).fetchall()
            ]
            return _row_to_campaign(row, moves)

        return await self._run(_do)

    async def list_campaigns(self) -> list[Campaign]:
        def _do(conn: sqlite3.Connection) -> list[Campaign]:
            rows = conn.execute(
                "SELECT * FROM campaigns ORDER BY created_at DESC"
            ).fetchall()
            out: list[Campaign] = []
            for row in rows:
                moves = [
                    Move.model_validate_json(m["move_json"])
                    for m in conn.execute(
                        "SELECT move_json FROM moves WHERE campaign_id = ? ORDER BY move",
                        (row["id"],),
                    ).fetchall()
                ]
                out.append(_row_to_campaign(row, moves))
            return out

        return await self._run(_do)

    # ---- moves -----------------------------------------------------------
    async def upsert_move(self, campaign_id: str, move: Move) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO moves (campaign_id, move, approval, status, grade, move_json)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(campaign_id, move) DO UPDATE SET"
                " approval=excluded.approval, status=excluded.status,"
                " grade=excluded.grade, move_json=excluded.move_json",
                (
                    campaign_id,
                    move.move,
                    move.approval.value,
                    move.status.value if move.status else None,
                    move.grade.value if move.grade else None,
                    move.model_dump_json(),
                ),
            )

        await self._run(_do)

    async def get_move(self, campaign_id: str, move_no: int) -> Move | None:
        def _do(conn: sqlite3.Connection) -> Move | None:
            row = conn.execute(
                "SELECT move_json FROM moves WHERE campaign_id = ? AND move = ?",
                (campaign_id, move_no),
            ).fetchone()
            return Move.model_validate_json(row["move_json"]) if row else None

        return await self._run(_do)

    async def list_moves(self, campaign_id: str) -> list[Move]:
        def _do(conn: sqlite3.Connection) -> list[Move]:
            rows = conn.execute(
                "SELECT move_json FROM moves WHERE campaign_id = ? ORDER BY move",
                (campaign_id,),
            ).fetchall()
            return [Move.model_validate_json(r["move_json"]) for r in rows]

        return await self._run(_do)

    # ---- events (append-only) -------------------------------------------
    async def append_event(self, event: Event) -> int:
        """Atribui ``seq`` monotonico por campanha e grava. Retorna o seq."""

        def _do(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 AS next FROM events WHERE campaign_id = ?",
                (event.campaign_id,),
            ).fetchone()
            seq = int(row["next"])
            event.seq = seq
            conn.execute(
                "INSERT INTO events (seq, campaign_id, type, at, event_json)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    seq,
                    event.campaign_id,
                    event.type.value,
                    event.at.isoformat(),
                    event.model_dump_json(),
                ),
            )
            return seq

        return await self._run(_do)

    async def list_events(self, campaign_id: str, since_seq: int = 0) -> list[Event]:
        def _do(conn: sqlite3.Connection) -> list[Event]:
            rows = conn.execute(
                "SELECT event_json FROM events WHERE campaign_id = ? AND seq > ? ORDER BY seq",
                (campaign_id, since_seq),
            ).fetchall()
            return [Event.model_validate_json(r["event_json"]) for r in rows]

        return await self._run(_do)

    # ---- audit (append-only) --------------------------------------------
    async def append_audit(self, entry: AuditEntry) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO audit (campaign_id, at, entry_json) VALUES (?, ?, ?)",
                (entry.campaign_id, entry.at.isoformat(), entry.model_dump_json()),
            )

        await self._run(_do)

    # ---- status (leve) ---------------------------------------------------
    async def ping(self) -> dict[str, int]:
        """Checa o banco e conta campanhas por estado (sem carregar lances)."""

        def _do(conn: sqlite3.Connection) -> dict[str, int]:
            rows = conn.execute("SELECT state, COUNT(*) AS n FROM campaigns GROUP BY state").fetchall()
            return {r["state"]: r["n"] for r in rows}

        return await self._run(_do)

    async def last_seq(self, campaign_id: str) -> int:
        def _do(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "SELECT MAX(seq) AS s FROM events WHERE campaign_id = ?", (campaign_id,)
            ).fetchone()
            return int(row["s"] or 0)

        return await self._run(_do)

    async def list_audit(self, campaign_id: str) -> list[AuditEntry]:
        def _do(conn: sqlite3.Connection) -> list[AuditEntry]:
            rows = conn.execute(
                "SELECT entry_json FROM audit WHERE campaign_id = ? ORDER BY id",
                (campaign_id,),
            ).fetchall()
            return [AuditEntry.model_validate_json(r["entry_json"]) for r in rows]

        return await self._run(_do)

    # ---- users (autenticacao) -------------------------------------------
    async def create_user(
        self, user_id: str, username: str, password_hash: str, role: str
    ) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, role, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (user_id, username, password_hash, role, _utcnow().isoformat()),
            )

        await self._run(_do)

    async def get_user_by_username(self, username: str) -> dict | None:
        def _do(conn: sqlite3.Connection) -> dict | None:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

        return await self._run(_do)

    async def count_users(self) -> int:
        def _do(conn: sqlite3.Connection) -> int:
            return int(conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"])

        return await self._run(_do)

    async def list_users(self) -> list[dict]:
        def _do(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                "SELECT id, username, role, created_at FROM users ORDER BY created_at"
            ).fetchall()
            return [dict(r) for r in rows]

        return await self._run(_do)

    # ---- app_settings (config mutavel do admin) --------------------------
    async def get_setting(self, key: str) -> object | None:
        def _do(conn: sqlite3.Connection) -> object | None:
            row = conn.execute(
                "SELECT value_json FROM app_settings WHERE key = ?", (key,)
            ).fetchone()
            return json.loads(row["value_json"]) if row else None

        return await self._run(_do)

    async def set_setting(self, key: str, value: object) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO app_settings (key, value_json, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,"
                " updated_at=excluded.updated_at",
                (key, json.dumps(value), _utcnow().isoformat()),
            )

        await self._run(_do)

    def all_settings_sync(self) -> dict[str, object]:
        """Leitura sincrona de todas as configuracoes (uso no startup)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, value_json FROM app_settings"
            ).fetchall()
        return {r["key"]: json.loads(r["value_json"]) for r in rows}


def _row_to_campaign(row: sqlite3.Row, moves: list[Move]) -> Campaign:
    return Campaign(
        id=row["id"],
        config=CampaignConfig.model_validate_json(row["config_json"]),
        state=CampaignState(row["state"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        finished_at=(
            datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None
        ),
        score=Score.model_validate_json(row["score_json"]) if row["score_json"] else None,
        moves=moves,
    )
