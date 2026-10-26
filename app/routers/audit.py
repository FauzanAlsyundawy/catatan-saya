import math
from pathlib import Path
from typing import Optional, Any
from fastapi import APIRouter, Request, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings, CATEGORY_MAP
from app.database import get_db
from app.dependencies import get_nav_categories
from app.security import validate_session
from app.utils.timezone import format_wib

router = APIRouter(prefix="", tags=["Audit"])
templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

PAGE_SIZE = 25


def _build_audit_conditions(
    activity_type: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple[list[str], list[Any]]:
    """Build WHERE clause conditions and parameters for audit log query."""
    conditions: list[str] = []
    params: list[Any] = []

    if activity_type and activity_type.strip():
        conditions.append("activity_type = ?")
        params.append(activity_type.strip())

    if start_date and start_date.strip():
        conditions.append("timestamp >= ?")
        params.append(start_date.strip() + "T00:00:00")

    if end_date and end_date.strip():
        conditions.append("timestamp <= ?")
        params.append(end_date.strip() + "T23:59:59")

    return conditions, params


@router.get("/audit-log", response_class=HTMLResponse)
async def view_audit_log(
    request: Request,
    page: int = Query(1, ge=1),
    activity_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
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

    conditions, params = _build_audit_conditions(
        activity_type, start_date, end_date
    )

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    count_query = "SELECT COUNT(id) as total FROM audit_logs" + where_clause
    select_query = (
        "SELECT id, timestamp, activity_type, original_filename, "
        "category_slug, ip_address, user_agent, details "
        "FROM audit_logs" + where_clause + " "
        "ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?"
    )

    with get_db() as conn:
        count_cursor = conn.execute(count_query, params)
        count_row = count_cursor.fetchone()
        total_count = int(count_row["total"]) if count_row else 0

        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        current_page = min(page, total_pages)
        offset = (current_page - 1) * PAGE_SIZE

        select_params = list(params)
        select_params.extend([PAGE_SIZE, offset])
        cursor = conn.execute(select_query, select_params)
        rows = cursor.fetchall()

    logs: list[dict[str, Any]] = []
    for r in rows:
        cat_slug = str(r["category_slug"]) if r["category_slug"] else None
        cat_info = CATEGORY_MAP.get(cat_slug, {}) if cat_slug else {}
        cat_name = cat_info.get("name", cat_slug) if cat_slug else None
        logs.append(
            {
                "id": r["id"],
                "timestamp_wib": format_wib(r["timestamp"]),
                "activity_type": r["activity_type"],
                "original_filename": r["original_filename"],
                "category_name": cat_name,
                "ip_address": r["ip_address"],
                "user_agent": r["user_agent"],
                "details": r["details"],
            }
        )

    nav_cats = get_nav_categories()

    return templates.TemplateResponse(
        request=request,
        name="audit_log.html",
        context={
            "current_user": user_session,
            "csrf_token": user_session["csrf_token"],
            "active_nav": "audit",
            "nav_categories": nav_cats,
            "logs": logs,
            "current_page": current_page,
            "total_pages": total_pages,
            "total_count": total_count,
            "selected_type": activity_type,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
