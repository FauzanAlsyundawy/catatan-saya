from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db, get_db
from app.security import hash_password
from app.utils.timezone import utc_now_iso
from app.routers import auth, dashboard, files, audit, users

BASE_DIR = Path(__file__).resolve().parent.parent


def seed_initial_users() -> None:
    """Ensure administrator and kencana default accounts exist."""
    users_to_seed = [
        ("administrator", "Fauzan@2026!", "admin"),
        ("kencana", "kencana@2026!", "user"),
    ]
    now = utc_now_iso()
    with get_db() as conn:
        for uname, pwd, role in users_to_seed:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?", (uname,)
            ).fetchone()
            if existing is None:
                pw_hash = hash_password(pwd)
                conn.execute(
                    "INSERT INTO users (username, password_hash, role, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (uname, pw_hash, role, now),
                )
            else:
                pw_hash = hash_password(pwd)
                conn.execute(
                    "UPDATE users SET password_hash = ?, role = ? WHERE id = ?",
                    (pw_hash, role, existing["id"]),
                )
            # Clear rate limit lockouts for these accounts
            conn.execute(
                "DELETE FROM login_attempts WHERE username = ?", (uname,)
            )


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

    csp = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )

    path = request.url.path
    if not path.startswith(("/static", "/assets", "/favicon.ico")):
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
    return RedirectResponse(
        url="/login", status_code=status.HTTP_302_FOUND
    )


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(files.router)
app.include_router(audit.router)
app.include_router(users.router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=False,
    )
