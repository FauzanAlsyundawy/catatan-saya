from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Any
from fastapi import APIRouter, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import get_db
from app.dependencies import get_nav_categories, get_client_ip
from app.security import (
    validate_session,
    hash_password,
    log_activity,
)
from app.utils.timezone import format_wib, parse_utc_iso, utc_now, utc_now_iso

router = APIRouter(prefix="", tags=["Users"])
templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _check_admin(request: Request) -> Optional[dict[str, Any]]:
    """Verify session and verify user has admin role."""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id:
        return None
    user_session = validate_session(session_id)
    if not user_session or user_session.get("role") != "admin":
        return None
    return user_session


@router.get("/users", response_class=HTMLResponse)
async def list_users(request: Request):
    """Admin view to manage users and view active/idle sessions."""
    admin_session = _check_admin(request)
    if not admin_session:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    timeout_minutes = settings.SESSION_IDLE_TIMEOUT_MINUTES
    now = utc_now()

    with get_db() as conn:
        # Fetch all users
        users_rows = conn.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id ASC"
        ).fetchall()

        # Fetch active sessions
        sessions_rows = conn.execute(
            "SELECT session_id, user_id, last_active_at, ip_address, user_agent "
            "FROM sessions"
        ).fetchall()

    # Map user_id to active session info
    active_sessions_map: dict[int, dict[str, Any]] = {}
    for s in sessions_rows:
        try:
            last_active = parse_utc_iso(s["last_active_at"])
            diff = now - last_active
            if diff <= timedelta(minutes=timeout_minutes):
                minutes_ago = max(0, int(diff.total_seconds() // 60))
                active_sessions_map[s["user_id"]] = {
                    "session_id": s["session_id"],
                    "ip_address": s["ip_address"] or "-",
                    "user_agent": s["user_agent"] or "-",
                    "last_active_wib": format_wib(s["last_active_at"]),
                    "minutes_ago": minutes_ago,
                }
        except Exception:
            continue

    users_list = []
    online_count = 0
    admin_count = 0
    regular_count = 0

    for u in users_rows:
        uid = u["id"]
        role = u["role"] or "user"
        if role == "admin":
            admin_count += 1
        else:
            regular_count += 1

        is_online = uid in active_sessions_map
        if is_online:
            online_count += 1

        session_info = active_sessions_map.get(uid)

        users_list.append({
            "id": uid,
            "username": u["username"],
            "role": role,
            "is_online": is_online,
            "session": session_info,
            "created_at_wib": format_wib(u["created_at"]),
            "is_self": uid == admin_session["user_id"],
        })

    nav_categories = get_nav_categories()

    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={
            "users": users_list,
            "total_users": len(users_list),
            "online_count": online_count,
            "admin_count": admin_count,
            "regular_count": regular_count,
            "nav_categories": nav_categories,
            "current_user": admin_session,
            "active_nav": "users",
            "csrf_token": admin_session["csrf_token"],
        },
    )


@router.post("/api/users")
async def create_new_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
    csrf_token: str = Form(...),
):
    """Admin API to create a new user account."""
    admin_session = _check_admin(request)
    if not admin_session:
        raise HTTPException(status_code=403, detail="Akses ditolak")

    if csrf_token != admin_session["csrf_token"]:
        raise HTTPException(status_code=403, detail="CSRF token tidak valid")

    clean_user = username.strip()
    if len(clean_user) < 3:
        raise HTTPException(status_code=400, detail="Username minimal 3 karakter")

    clean_pass = password.strip()
    if len(clean_pass) < 8:
        raise HTTPException(status_code=400, detail="Password minimal 8 karakter")

    clean_role = role.strip().lower()
    if clean_role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Role tidak valid")

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (clean_user,)
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=400, detail=f"Username '{clean_user}' sudah terdaftar"
            )

        pw_hash = hash_password(clean_pass)
        now = utc_now_iso()
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) "
            "VALUES (?, ?, ?, ?)",
            (clean_user, pw_hash, clean_role, now),
        )

        ip = get_client_ip(request)
        ua = request.headers.get("user-agent", "")
        log_activity(
            activity_type="USER_CREATED",
            original_filename=None,
            category_slug=None,
            ip_address=ip,
            user_agent=ua,
            details=f"Admin '{admin_session['username']}' membuat akun: '{clean_user}' (role: {clean_role})",
            connection=conn,
        )

    return JSONResponse(
        status_code=200,
        content={"success": True, "message": f"Pengguna '{clean_user}' berhasil dibuat"},
    )


@router.post("/api/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    request: Request,
    new_password: str = Form(...),
    csrf_token: str = Form(...),
):
    """Admin API to reset password for a user."""
    admin_session = _check_admin(request)
    if not admin_session:
        raise HTTPException(status_code=403, detail="Akses ditolak")

    if csrf_token != admin_session["csrf_token"]:
        raise HTTPException(status_code=403, detail="CSRF token tidak valid")

    clean_pass = new_password.strip()
    if len(clean_pass) < 8:
        raise HTTPException(status_code=400, detail="Password baru minimal 8 karakter")

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan")

        pw_hash = hash_password(clean_pass)
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (pw_hash, user_id),
        )
        # Clear any brute force rate limiting for that user
        conn.execute(
            "DELETE FROM login_attempts WHERE username = ?", (user["username"],)
        )

        ip = get_client_ip(request)
        ua = request.headers.get("user-agent", "")
        log_activity(
            activity_type="USER_PASSWORD_RESET",
            original_filename=None,
            category_slug=None,
            ip_address=ip,
            user_agent=ua,
            details=f"Admin '{admin_session['username']}' mereset password akun '{user['username']}'",
            connection=conn,
        )

    return JSONResponse(
        status_code=200,
        content={"success": True, "message": f"Password untuk '{user['username']}' berhasil diubah"},
    )


@router.post("/api/users/{user_id}/role")
async def change_user_role(
    user_id: int,
    request: Request,
    role: str = Form(...),
    csrf_token: str = Form(...),
):
    """Admin API to change user role."""
    admin_session = _check_admin(request)
    if not admin_session:
        raise HTTPException(status_code=403, detail="Akses ditolak")

    if csrf_token != admin_session["csrf_token"]:
        raise HTTPException(status_code=403, detail="CSRF token tidak valid")

    clean_role = role.strip().lower()
    if clean_role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Role tidak valid")

    if user_id == admin_session["user_id"] and clean_role != "admin":
        raise HTTPException(
            status_code=400,
            detail="Anda tidak dapat menurunkan role akun Anda sendiri!",
        )

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan")

        conn.execute(
            "UPDATE users SET role = ? WHERE id = ?", (clean_role, user_id)
        )

        ip = get_client_ip(request)
        ua = request.headers.get("user-agent", "")
        log_activity(
            activity_type="USER_ROLE_CHANGED",
            original_filename=None,
            category_slug=None,
            ip_address=ip,
            user_agent=ua,
            details=f"Admin '{admin_session['username']}' mengubah role '{user['username']}' menjadi '{clean_role}'",
            connection=conn,
        )

    return JSONResponse(
        status_code=200,
        content={"success": True, "message": f"Role '{user['username']}' berhasil diubah ke '{clean_role}'"},
    )


@router.post("/api/users/{user_id}/kick")
async def kick_user_session(
    user_id: int,
    request: Request,
    csrf_token: str = Form(...),
):
    """Admin API to kick (force logout) active sessions of a user."""
    admin_session = _check_admin(request)
    if not admin_session:
        raise HTTPException(status_code=403, detail="Akses ditolak")

    if csrf_token != admin_session["csrf_token"]:
        raise HTTPException(status_code=403, detail="CSRF token tidak valid")

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan")

        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

        ip = get_client_ip(request)
        ua = request.headers.get("user-agent", "")
        log_activity(
            activity_type="USER_SESSION_KICKED",
            original_filename=None,
            category_slug=None,
            ip_address=ip,
            user_agent=ua,
            details=f"Admin '{admin_session['username']}' memutus sesi aktif pengguna '{user['username']}'",
            connection=conn,
        )

    return JSONResponse(
        status_code=200,
        content={"success": True, "message": f"Sesi aktif untuk '{user['username']}' berhasil diputus"},
    )


@router.delete("/api/users/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
):
    """Admin API to delete a user account."""
    admin_session = _check_admin(request)
    if not admin_session:
        raise HTTPException(status_code=403, detail="Akses ditolak")

    csrf_header = request.headers.get("X-CSRF-Token")
    if not csrf_header or csrf_header != admin_session["csrf_token"]:
        raise HTTPException(status_code=403, detail="CSRF token tidak valid")

    if user_id == admin_session["user_id"]:
        raise HTTPException(
            status_code=400, detail="Anda tidak dapat menghapus akun Anda sendiri!"
        )

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan")

        uname = user["username"]
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

        ip = get_client_ip(request)
        ua = request.headers.get("user-agent", "")
        log_activity(
            activity_type="USER_DELETED",
            original_filename=None,
            category_slug=None,
            ip_address=ip,
            user_agent=ua,
            details=f"Admin '{admin_session['username']}' menghapus akun pengguna '{uname}'",
            connection=conn,
        )

    return JSONResponse(
        status_code=200,
        content={"success": True, "message": f"Pengguna '{uname}' berhasil dihapus"},
    )
