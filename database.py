"""Подключение SQLite и подготовка БД без удаления существующих данных."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# Отдельный путь позволяет проверять API на временной БД.
DB_PATH = Path(os.environ.get("TYPING_DB_PATH", str(BASE_DIR / "SQLiteDB.db")))


@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:  # Успех — commit, исключение — rollback.
            yield conn
    finally:
        conn.close()


def init_db():
    with connection() as conn:
        for filename in ("TableCreate.sql", "TriggerCreate.sql", "SeedDataEntry.sql"):
            conn.executescript((BASE_DIR / "sqlRequests" / filename).read_text(encoding="utf-8"))

        # ALTER TABLE нужен для БД, созданной до появления новых полей.
        additions = {
            "Users": {"nickname": "TEXT"},
            "StatsHistory": {
                "mode": "TEXT NOT NULL DEFAULT 'words'",
                "duration_seconds": "REAL NOT NULL DEFAULT 0",
                "xp_gained": "INTEGER NOT NULL DEFAULT 0",
            },
        }
        for table, columns in additions.items():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            for name, definition in columns.items():
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

        # Сессии переживают перезапуск сервера; в БД хранится только хеш токена.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            )
        """)
        conn.execute("INSERT OR IGNORE INTO Statistics (user_id) SELECT id FROM Users")
