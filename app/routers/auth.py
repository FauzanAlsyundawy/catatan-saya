from pathlib import Path
from fastapi import APIRouter, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import get_db
from app.security import (
    verify_password,
    check_login_rate_limit,
    record_login_attempt,
    create_session,
    validate_session,
    destroy_session,
    log_activity,
    generate_token,
)

router = APIRouter(prefix="", tags=["Auth"])
templates_dir = (
    Path(__file__).resolve().parent.parent.parent / "templates"
)
templates = Jinja2Templates(directory=str(templates_dir))


def get_client_ip(request: Request) -> str:
    """Extract real client IP considering forward headers if present."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if session_id:
        user_session = validate_session(session_id)
        if user_session:
            return RedirectResponse(
                url="/", status_code=status.HTTP_302_FOUND
            )

    temp_csrf = generate_token(32)
    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"csrf_token": temp_csrf, "error_message": None},
    )
    response.set_cookie(
        key="temp_csrf_token",
        value=temp_csrf,
        httponly=True,
        samesite="strict",
        secure=settings.SESSION_COOKIE_SECURE,
    )
    return response


@router.post("/auth/login")
async def process_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    username_clean = username.strip()

    cookie_csrf = request.cookies.get("temp_csrf_token")
    if cookie_csrf and cookie_csrf != csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    is_allowed, remaining_sec = check_login_rate_limit(
        ip_address, username_clean
    )
    if not is_allowed:
        minutes_left = (remaining_sec // 60) + 1
        log_activity(
            activity_type="LOGIN_FAILED",
            original_filename=None,
            category_slug=None,
            ip_address=ip_address,
            user_agent=user_agent,
            details=(
                f"Login ditolak karena rate limit terkunci "
                f"(tersisa {minutes_left} menit)"
            ),
        )
        lock_msg = (
            f"Terlalu banyak percobaan gagal. "
            f"Akun dikunci sementara selama {minutes_left} menit."
        )
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"csrf_token": csrf_token, "error_message": lock_msg},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    with get_db() as conn:
        find_sql = (
            "SELECT id, username, password_hash "
            "FROM users WHERE username = ?"
        )
        cursor = conn.execute(find_sql, (username_clean,))
        user = cursor.fetchone()

    is_valid = False
    if user and verify_password(user["password_hash"], password):
        is_valid = True

    if not is_valid:
        record_login_attempt(ip_address, username_clean, success=False)
        log_activity(
            activity_type="LOGIN_FAILED",
            original_filename=None,
            category_slug=None,
            ip_address=ip_address,
            user_agent=user_agent,
            details=f"Percobaan login gagal untuk: {username_clean}",
        )
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": csrf_token,
                "error_message": "Username atau password salah",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    record_login_attempt(ip_address, username_clean, success=True)
    session_id, _ = create_session(user["id"], ip_address, user_agent)
    log_activity(
        activity_type="LOGIN_SUCCESS",
        original_filename=None,
        category_slug=None,
        ip_address=ip_address,
        user_agent=user_agent,
        details=f"Login berhasil untuk pengguna: {username_clean}",
    )

    resp = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE.lower(),
        secure=settings.SESSION_COOKIE_SECURE,
        max_age=settings.SESSION_IDLE_TIMEOUT_MINUTES * 60,
    )
    resp.delete_cookie("temp_csrf_token")
    return resp


@router.post("/auth/logout")
async def process_logout(request: Request, csrf_token: str = Form(...)):
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")

    if session_id:
        user_session = validate_session(session_id)
        if user_session and user_session["csrf_token"] == csrf_token:
            destroy_session(session_id, ip_address, user_agent)

    resp = RedirectResponse(
        url="/login", status_code=status.HTTP_302_FOUND
    )
    resp.delete_cookie(settings.SESSION_COOKIE_NAME)
    return resp
