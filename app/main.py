import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import get_db, init_db
from app.routers import audit, auth, dashboard, files, users
from app.security import hash_password, validate_session
from app.utils.storage import format_file_size
from app.utils.timezone import utc_now_iso

BASE_DIR = Path(__file__).resolve().parent.parent


def seed_initial_users() -> None:
    """Ensure administrator and kencana default accounts exist safely
    with multiple workers.
    """
    users_to_seed = [
        ("administrator", "Fauzan@2026!", "admin"),
        ("kencana", "kencana@2026!", "user"),
    ]
    now = utc_now_iso()
    try:
        with get_db() as conn:
            for uname, pwd, role in users_to_seed:
                pw_hash = hash_password(pwd)
                conn.execute(
                    """
                    INSERT INTO users (
                        username, password_hash, role, created_at
                    )
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(username) DO UPDATE SET
                        password_hash = excluded.password_hash,
                        role = excluded.role;
                    """,
                    (uname, pw_hash, role, now),
                )
                conn.execute(
                    "DELETE FROM login_attempts WHERE username = ?", (uname,)
                )
    except sqlite3.IntegrityError:
        pass
    except (sqlite3.Error, OSError) as exc:
        print(f"Warning during seed_initial_users: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inisialisasi basis data SQLite dan struktur folder
    init_db()
    seed_initial_users()
    yield


app = FastAPI(
    title="Catatan Saya",
    description="Penyimpanan Berkas Catatan Pribadi & Log Audit",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

static_path = str(BASE_DIR / "static")
assets_path = str(BASE_DIR / "assets")
app.mount("/static", StaticFiles(directory=static_path), name="static")
app.mount("/assets", StaticFiles(directory=assets_path), name="assets")


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)

    is_file_preview = request.url.path.startswith("/api/files/view/")
    frame_ancestors = "'self'" if is_file_preview else "'none'"
    csp = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        f"frame-ancestors {frame_ancestors}; "
        "base-uri 'self'; "
        "form-action 'self';"
    )

    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Frame-Options"] = (
        "SAMEORIGIN" if is_file_preview else "DENY"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )

    path = request.url.path
    if path.startswith(("/static", "/assets", "/favicon.ico")):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    else:
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"

    return response


@app.exception_handler(status.HTTP_401_UNAUTHORIZED)
async def unauthorized_handler(request: Request, exc):
    accept = request.headers.get("accept", "")
    if "application/json" in accept or request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Otentikasi diperlukan"},
        )
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(files.router)
app.include_router(audit.router)
app.include_router(users.router)


@app.get("/api/search")
async def api_search(request: Request, q: str = Query(default="")):
    """Search files by name across all categories. Requires valid session."""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Otentikasi diperlukan"},
        )
    user_session = validate_session(session_id)
    if not user_session:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Otentikasi diperlukan"},
        )

    q = q.strip()
    if len(q) < 2:
        return JSONResponse(content={"results": []})

    search_sql = (
        "SELECT id, category_slug, original_filename, file_size, "
        "extension, created_at FROM files WHERE original_filename LIKE ? "
        "ORDER BY created_at DESC LIMIT 20"
    )
    with get_db() as conn:
        cursor = conn.execute(search_sql, (f"%{q}%",))
        rows = cursor.fetchall()

    results = [
        {
            "id": row["id"],
            "category_slug": row["category_slug"],
            "original_filename": row["original_filename"],
            "size_formatted": format_file_size(int(row["file_size"])),
            "extension": row["extension"],
        }
        for row in rows
    ]
    return JSONResponse(content={"results": results})


@app.get("/api/storage-info")
async def api_storage_info(request: Request):
    """Return total storage used across all files."""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id or not validate_session(session_id):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Otentikasi diperlukan"},
        )
    with get_db() as conn:
        cursor = conn.execute("SELECT COALESCE(SUM(file_size), 0) FROM files")
        total_bytes = int(cursor.fetchone()[0])
    return JSONResponse(
        content={
            "total_bytes": total_bytes,
            "total_formatted": format_file_size(total_bytes),
        }
    )

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=False,
    )
