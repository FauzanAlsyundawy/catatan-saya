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
    with get_db() as conn:
        cursor = conn.execute(metrics_query)
        metrics = {row["category_slug"]: row for row in cursor.fetchall()}

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
        },
    )
