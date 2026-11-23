"""Banco SQLite (biblioteca padrão, sem ORM) e configurações do usuário."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS dialogs (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    level       TEXT,
    description TEXT,
    builtin     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phrases (
    id        INTEGER PRIMARY KEY,
    dialog_id INTEGER NOT NULL REFERENCES dialogs(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL DEFAULT 0,
    speaker   TEXT,
    en        TEXT NOT NULL,
    pt        TEXT NOT NULL,
    en_alt    TEXT NOT NULL DEFAULT '[]',
    pt_alt    TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS phrase_progress (
    phrase_id      INTEGER PRIMARY KEY REFERENCES phrases(id) ON DELETE CASCADE,
    completed      INTEGER NOT NULL DEFAULT 0,
    mistakes       INTEGER NOT NULL DEFAULT 0,
    last_completed TEXT
);

CREATE TABLE IF NOT EXISTS texts (
    id         INTEGER PRIMARY KEY,
    title      TEXT,
    pt_text    TEXT NOT NULL,
    en_text    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',
    attempts   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    solved_at  TEXT,
    solved_text TEXT
);

CREATE TABLE IF NOT EXISTS text_attempts (
    id         INTEGER PRIMARY KEY,
    text_id    INTEGER NOT NULL REFERENCES texts(id) ON DELETE CASCADE,
    attempt    TEXT NOT NULL,
    accepted   INTEGER NOT NULL,
    feedback   TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS words (
    id          INTEGER PRIMARY KEY,
    word        TEXT NOT NULL UNIQUE,
    meaning_pt  TEXT,
    is_common   INTEGER NOT NULL DEFAULT 0,
    in_review   INTEGER NOT NULL DEFAULT 1,
    box         INTEGER NOT NULL DEFAULT 0,
    next_review TEXT,
    correct     INTEGER NOT NULL DEFAULT 0,
    wrong       INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS word_contexts (
    id          INTEGER PRIMARY KEY,
    word_id     INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_id   INTEGER,
    sentence    TEXT NOT NULL,
    UNIQUE (word_id, sentence)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- curso de gramática ------------------------------------------------------
CREATE TABLE IF NOT EXISTS lesson_progress (
    lesson_id    TEXT PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'started',   -- started | done
    best_score   INTEGER NOT NULL DEFAULT 0,        -- melhor nota do mini-teste (0-100)
    quiz_runs    INTEGER NOT NULL DEFAULT 0,
    started_at   TEXT NOT NULL,
    completed_at TEXT
);

-- exercícios que o aluno errou (ou concluiu) viram itens da revisão de gramática (Leitner)
CREATE TABLE IF NOT EXISTS grammar_items (
    ex_id       TEXT PRIMARY KEY,
    lesson_id   TEXT NOT NULL,
    box         INTEGER NOT NULL DEFAULT 0,
    next_review TEXT NOT NULL,
    correct     INTEGER NOT NULL DEFAULT 0,
    wrong       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reading_progress (
    reading_id TEXT PRIMARY KEY,
    best_score INTEGER NOT NULL DEFAULT 0,
    runs       INTEGER NOT NULL DEFAULT 0,
    done_at    TEXT
);

-- um registro por dia: segundos de estudo ativo e quantidade de exercícios feitos
CREATE TABLE IF NOT EXISTS study_days (
    day     TEXT PRIMARY KEY,
    seconds INTEGER NOT NULL DEFAULT 0,
    items   INTEGER NOT NULL DEFAULT 0
);

-- acertos e erros por lição (alimenta "pontos fracos" no painel)
CREATE TABLE IF NOT EXISTS lesson_stats (
    lesson_id TEXT PRIMARY KEY,
    correct   INTEGER NOT NULL DEFAULT 0,
    wrong     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pronunciation_log (
    id         INTEGER PRIMARY KEY,
    target     TEXT NOT NULL,
    spoken     TEXT NOT NULL,
    score      INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as conn:
        conn.executescript(SCHEMA)
        # migrações leves: bancos criados por versões anteriores ganham as colunas novas sem perder dados
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(words)")}
        if "tag" not in cols:
            conn.execute("ALTER TABLE words ADD COLUMN tag TEXT")  # 'ti' = vocabulário de desenvolvimento
        conn.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_in(*, days: float = 0, minutes: float = 0) -> str:
    t = datetime.now(timezone.utc) + timedelta(days=days, minutes=minutes)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- configurações
@dataclass
class Settings:
    ignore_accents: bool = False  # True: "voce" vale como "você"
    strict_exact: bool = False  # True: maiúsculas e pontuação também precisam estar iguais


def load_settings(db: sqlite3.Connection) -> Settings:
    rows = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings")}
    return Settings(
        ignore_accents=rows.get("ignore_accents") == "1",
        strict_exact=rows.get("strict_exact") == "1",
    )


def save_settings(db: sqlite3.Connection, s: Settings) -> None:
    with db:
        for k, v in asdict(s).items():
            db.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (k, "1" if v else "0"),
            )


# --------------------------------------------------------------------------- valores avulsos (texto/número)
def get_setting(db: sqlite3.Connection, key: str, default: Optional[str] = None) -> Optional[str]:
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def get_int(db: sqlite3.Connection, key: str, default: int) -> int:
    try:
        return int(get_setting(db, key, str(default)))
    except (TypeError, ValueError):
        return default


def set_setting(db: sqlite3.Connection, key: str, value) -> None:
    with db:
        db.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
