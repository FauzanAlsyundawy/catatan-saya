from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status

from app.config import settings, CATEGORIES
from app.database import get_db
from app.security import validate_session


def get_client_ip(request: Request) -> str:
    """Extract real client IP."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


async def get_current_user_session(request: Request) -> Dict[str, Any]:
    """Dependency untuk memvalidasi sesi aktif pengguna."""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Otentikasi diperlukan",
        )

    user_session = validate_session(session_id)
    if not user_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi telah kadaluarsa atau tidak valid",
        )

    return user_session


def verify_csrf(session: Dict[str, Any], token: Optional[str]) -> bool:
    """Verifikasi token CSRF secara konstan."""
    if not token or not session.get("csrf_token"):
        return False
    return token == session["csrf_token"]


def get_nav_categories() -> list[dict[str, Any]]:
    """Mengambil 5 kategori dengan live file count untuk sidebar."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT category_slug, COUNT(id) as count "
            "FROM files GROUP BY category_slug"
        )
        counts = {
            row["category_slug"]: row["count"] for row in cursor.fetchall()
        }

    result = []
    for cat in CATEGORIES:
        item = dict(cat)
        item["file_count"] = counts.get(cat["slug"], 0)
        result.append(item)
    return result
