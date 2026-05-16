import sqlite3
import os
from contextlib import contextmanager

DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "game.db")


def get_connection() -> sqlite3.Connection:
    """Get a new SQLite connection with row_factory set."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_x_id INTEGER NOT NULL,
                player_o TEXT DEFAULT 'computer',
                status TEXT NOT NULL DEFAULT 'in_progress',
                board TEXT NOT NULL DEFAULT '["","","","","","","","",""]',
                current_turn TEXT NOT NULL DEFAULT 'X',
                winner TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                finished_at TEXT,
                FOREIGN KEY (player_x_id) REFERENCES users(id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db():
    """Context manager that yields a database connection and closes it afterwards."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
