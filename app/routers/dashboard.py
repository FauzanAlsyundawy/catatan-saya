from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import CATEGORIES, settings
from app.database import get_db
from app.dependencies import get_nav_categories
from app.security import validate_session
from app.utils.storage import format_file_size
from app.utils.timezone import format_wib

router = APIRouter(prefix="", tags=["Dashboard"])
templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id:
        return RedirectResponse(
            url="/login", status_code=status.HTTP_302_FOUND
        )

    user_session = validate_session(session_id)
    if not user_session:
        return RedirectResponse(
            url="/login", status_code=status.HTTP_302_FOUND
        )

    # Hitung metrik per kategori (file_count, total_size)
    metrics_query = (
        "SELECT category_slug, COUNT(id) as file_count, "
        "COALESCE(SUM(file_size), 0) as total_size "
        "FROM files GROUP BY category_slug"
    )
    recent_files_query = (
        "SELECT id, category_slug, original_filename, file_size, "
        "extension, created_at FROM files ORDER BY created_at DESC, "
        "id DESC LIMIT 5"
    )
    storage_total_query = "SELECT COALESCE(SUM(file_size), 0) FROM files"

    with get_db() as conn:
        cursor = conn.execute(metrics_query)
        metrics = {row["category_slug"]: row for row in cursor.fetchall()}

        cursor = conn.execute(recent_files_query)
        raw_recent = cursor.fetchall()

        cursor = conn.execute(storage_total_query)
        storage_total_bytes: int = int(cursor.fetchone()[0])

    recent_files = [
        {
            "id": r["id"],
            "category_slug": r["category_slug"],
            "original_filename": r["original_filename"],
            "size_formatted": format_file_size(int(r["file_size"])),
            "extension": r["extension"],
            "created_at_wib": format_wib(r["created_at"]),
        }
        for r in raw_recent
    ]

    bento_categories: list[dict[str, Any]] = []
    for cat in CATEGORIES:
        slug = cat["slug"]
        m = metrics.get(slug, {"file_count": 0, "total_size": 0})
        total_size = int(m["total_size"])
        bento_categories.append(
            {
                "slug": slug,
                "name": cat["name"],
                "description": cat["description"],
                "icon": cat["icon"],
                "file_count": int(m["file_count"]),
                "total_size": total_size,
                "total_size_formatted": format_file_size(total_size),
            }
        )

    nav_cats = get_nav_categories()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "current_user": user_session,
            "csrf_token": user_session["csrf_token"],
            "active_nav": "dashboard",
            "nav_categories": nav_cats,
            "categories": bento_categories,
            "recent_files": recent_files,
            "storage_total_bytes": storage_total_bytes,
            "storage_total_formatted": format_file_size(storage_total_bytes),
        },
    )
