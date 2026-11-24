"""Conexão, estrutura e atualizações do banco de dados SQLite."""

import sqlite3
from pathlib import Path

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    first_name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    program TEXT NOT NULL DEFAULT 'BIU MLP',
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT
);
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    message_template TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT
);
CREATE TABLE IF NOT EXISTS sends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'opened', 'sent', 'skip')),
    opened_at TEXT,
    sent_at TEXT,
    UNIQUE(campaign_id, student_id),
    FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
    FOREIGN KEY(student_id) REFERENCES students(id)
);
CREATE TABLE IF NOT EXISTS weekly_goals (
    week_start TEXT NOT NULL,
    day INTEGER NOT NULL CHECK(day BETWEEN 0 AND 3),
    target INTEGER NOT NULL CHECK(target >= 0),
    completed INTEGER NOT NULL DEFAULT 0 CHECK(completed >= 0),
    PRIMARY KEY (week_start, day)
);
"""


def database_path():
    """Retorna o local persistente do banco de dados do projeto."""
    return Path(current_app.root_path).parent / "data" / "outreaches.db"


def get_db():
    """Retorna a conexão SQLite da requisição atual."""
    if "db" not in g:
        path = database_path()
        path.parent.mkdir(exist_ok=True)
        g.db = sqlite3.connect(path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    """Fecha a conexão SQLite ao final da requisição."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Cria as tabelas e aplica atualizações compatíveis ao banco existente."""
    db = get_db()
    db.executescript(SCHEMA)
    columns = {row[1] for row in db.execute("PRAGMA table_info(campaigns)")}
    if "status" not in columns:
        db.execute("ALTER TABLE campaigns ADD COLUMN status TEXT NOT NULL DEFAULT 'open'")
    db.commit()


def init_app(app):
    """Registra a manutenção do banco na aplicação Flask."""
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
