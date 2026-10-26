import secrets
from datetime import timedelta
from typing import Optional, Tuple
from argon2 import Type, PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

from app.config import settings
from app.database import get_db
from app.utils.timezone import utc_now, utc_now_iso, parse_utc_iso

ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    type=Type.ID,
)


def hash_password(password: str) -> str:
    """Hash password menggunakan algoritma Argon2id."""
    return ph.hash(password)


def verify_password(password_hash: str, candidate_password: str) -> bool:
    """Verifikasi password dengan proteksi terhadap timing attack."""
    try:
        return ph.verify(password_hash, candidate_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def generate_token(nbytes: int = 32) -> str:
    """Generate cryptographically secure random token."""
    return secrets.token_urlsafe(nbytes)


def check_login_rate_limit(
    ip_address: str, username: str
) -> Tuple[bool, int]:
    """Periksa apakah (IP, username) terkunci karena rate limit."""
    lockout_minutes = settings.LOGIN_RATE_LIMIT_LOCKOUT_MINUTES
    max_attempts = settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
    cutoff_time = (
        utc_now() - timedelta(minutes=lockout_minutes)
    ).isoformat()

    query_sql = (
        "SELECT attempt_time FROM login_attempts "
        "WHERE ip_address = ? AND username = ? "
        "AND success = 0 AND attempt_time >= ? "
        "ORDER BY attempt_time DESC"
    )
    with get_db() as conn:
        cursor = conn.execute(
            query_sql, (ip_address, username, cutoff_time)
        )
        failed_attempts = cursor.fetchall()

        if len(failed_attempts) >= max_attempts:
            latest_iso = failed_attempts[0]["attempt_time"]
            latest_attempt = parse_utc_iso(latest_iso)
            unlock_time = latest_attempt + timedelta(
                minutes=lockout_minutes
            )
            now = utc_now()
            remaining = int((unlock_time - now).total_seconds())
            if remaining > 0:
                return False, remaining

    return True, 0


def record_login_attempt(
    ip_address: str, username: str, success: bool
) -> None:
    """Catat percobaan login untuk rate limiting."""
    insert_sql = (
        "INSERT INTO login_attempts "
        "(ip_address, username, attempt_time, success) "
        "VALUES (?, ?, ?, ?)"
    )
    with get_db() as conn:
        conn.execute(
            insert_sql,
            (ip_address, username, utc_now_iso(), 1 if success else 0),
        )


def create_session(
    user_id: int,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> Tuple[str, str]:
    """Buat sesi baru di database."""
    session_id = generate_token(32)
    csrf_token = generate_token(32)
    now = utc_now_iso()

    insert_sql = (
        "INSERT INTO sessions "
        "(session_id, user_id, csrf_token, created_at, "
        "last_active_at, ip_address, user_agent) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    with get_db() as conn:
        conn.execute(
            insert_sql,
            (
                session_id,
                user_id,
                csrf_token,
                now,
                now,
                ip_address or "",
                user_agent or "",
            ),
        )

    return session_id, csrf_token


def validate_session(session_id: str) -> Optional[dict]:
    """Validasi sesi dan cek idle timeout 30 menit."""
    if not session_id:
        return None

    timeout_minutes = settings.SESSION_IDLE_TIMEOUT_MINUTES
    now = utc_now()

    select_sql = (
        "SELECT s.session_id, s.user_id, s.csrf_token, s.created_at, "
        "s.last_active_at, s.ip_address, s.user_agent, u.username "
        "FROM sessions s JOIN users u ON s.user_id = u.id "
        "WHERE s.session_id = ?"
    )
    with get_db() as conn:
        cursor = conn.execute(select_sql, (session_id,))
        row = cursor.fetchone()

        if not row:
            return None

        last_active = parse_utc_iso(row["last_active_at"])
        if (now - last_active) > timedelta(minutes=timeout_minutes):
            conn.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            expired_sql = (
                "INSERT INTO audit_logs "
                "(timestamp, activity_type, original_filename, "
                "category_slug, ip_address, user_agent, details) "
                "VALUES (?, 'LOGOUT_EXPIRED', NULL, NULL, ?, ?, "
                "'Sesi otomatis berakhir karena idle > 30 menit')"
            )
            conn.execute(
                expired_sql,
                (utc_now_iso(), row["ip_address"], row["user_agent"]),
            )
            return None

        conn.execute(
            "UPDATE sessions SET last_active_at = ? WHERE session_id = ?",
            (now.isoformat(), session_id),
        )

        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "username": row["username"],
            "csrf_token": row["csrf_token"],
            "ip_address": row["ip_address"],
            "user_agent": row["user_agent"],
        }


def destroy_session(
    session_id: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Hapus sesi dan catat log LOGOUT_MANUAL."""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM sessions WHERE session_id = ?", (session_id,)
        )
        logout_sql = (
            "INSERT INTO audit_logs "
            "(timestamp, activity_type, original_filename, "
            "category_slug, ip_address, user_agent, details) "
            "VALUES (?, 'LOGOUT_MANUAL', NULL, NULL, ?, ?, "
            "'Logout manual oleh pengguna')"
        )
        conn.execute(
            logout_sql,
            (utc_now_iso(), ip_address or "", user_agent or ""),
        )


def log_activity(
    activity_type: str,
    original_filename: Optional[str] = None,
    category_slug: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[str] = None,
    connection=None,
) -> None:
    """Catat aktivitas audit log secara append-only."""
    query = (
        "INSERT INTO audit_logs "
        "(timestamp, activity_type, original_filename, "
        "category_slug, ip_address, user_agent, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    params = (
        utc_now_iso(),
        activity_type,
        original_filename,
        category_slug,
        ip_address or "",
        user_agent or "",
        details or "",
    )

    if connection is not None:
        connection.execute(query, params)
    else:
        with get_db() as conn:
            conn.execute(query, params)
