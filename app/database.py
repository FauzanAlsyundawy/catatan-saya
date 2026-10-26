import sqlite3
from contextlib import contextmanager
from typing import Generator
from app.config import settings


def get_connection() -> sqlite3.Connection:
    """Create a configured SQLite connection."""
    db_path = settings.abs_database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(db_path), timeout=10.0, check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite database transactions."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database tables, indexes and verify schema."""
    upload_dir = settings.abs_upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                csrf_token TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_active_at TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_slug TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT UNIQUE NOT NULL,
                file_size INTEGER NOT NULL,
                mime_type TEXT NOT NULL,
                extension TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)

        # 4. Audit Logs table (Read-only, append-only)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                original_filename TEXT,
                category_slug TEXT,
                ip_address TEXT,
                user_agent TEXT,
                details TEXT
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                username TEXT NOT NULL,
                attempt_time TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 0
            );
        """)

        # Indexes for fast querying
        conn.execute(
            "CREATE INDEX IF NOT EXISTS "
            "idx_files_cat ON files(category_slug);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS "
            "idx_files_time ON files(created_at DESC);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS "
            "idx_audit_time ON audit_logs(timestamp DESC);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS "
            "idx_audit_act ON audit_logs(activity_type);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS "
            "idx_login_att ON login_attempts("
            "ip_address, username, attempt_time);"
        )
