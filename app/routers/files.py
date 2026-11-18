from pathlib import Path
import re
from typing import Any

import aiofiles
from fastapi import (
    APIRouter,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.templating import Jinja2Templates

from app.config import CATEGORY_MAP, settings
from app.database import get_db
from app.dependencies import (
    get_client_ip,
    get_current_user_session,
    get_nav_categories,
    verify_csrf,
)
from app.security import log_activity, validate_session
from app.utils.storage import (
    format_file_size,
    generate_stored_filename,
    get_file_extension,
    get_file_icon,
    resolve_duplicate_filename,
    sanitize_filename,
)
from app.utils.timezone import format_wib, utc_now_iso

router = APIRouter(prefix="", tags=["Files"])
templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

MSG_CSRF_INVALID = "Token CSRF tidak valid"
MSG_FILE_NOT_FOUND = "Berkas tidak ditemukan"
MSG_PHYSICAL_FILE_NOT_FOUND = "Berkas fisik tidak ditemukan di server"


async def _save_upload_stream(
    file: UploadFile,
    target_path: Path,
    max_bytes: int,
) -> int:
    """Stream incoming upload file to disk asynchronously."""
    file_size = 0
    async with aiofiles.open(target_path, "wb") as f_out:
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            chunk_bytes = (
                chunk.encode("utf-8") if isinstance(chunk, str) else chunk
            )
            file_size += len(chunk_bytes)
            if file_size > max_bytes:
                await f_out.close()
                if target_path.exists():
                    target_path.unlink()
                max_mb = settings.MAX_UPLOAD_SIZE_MB
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"Ukuran berkas melebihi batas maksimal {max_mb} MB"
                    ),
                )
            await f_out.write(chunk_bytes)
    return file_size


def _save_file_record(
    clean_slug: str,
    original_name: str,
    stored_name: str,
    file_size: int,
    mime_type: str,
    ext: str,
    ip_addr: str,
    user_agent: str,
) -> tuple[int, str]:
    """Persist file metadata and write consistent audit log."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT original_filename FROM files WHERE category_slug = ?",
            (clean_slug,),
        )
        existing_names = {
            str(row["original_filename"]) for row in cursor.fetchall()
        }
        final_name = resolve_duplicate_filename(existing_names, original_name)

        now = utc_now_iso()
        insert_sql = (
            "INSERT INTO files "
            "(category_slug, original_filename, stored_filename, "
            "file_size, mime_type, extension, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        cursor = conn.execute(
            insert_sql,
            (
                clean_slug,
                final_name,
                stored_name,
                file_size,
                mime_type,
                ext,
                now,
            ),
        )
        new_file_id: int = int(cursor.lastrowid or 0)

        log_activity(
            activity_type="UPLOAD_FILE",
            original_filename=final_name,
            category_slug=clean_slug,
            ip_address=ip_addr,
            user_agent=user_agent,
            details=f"Ukuran: {format_file_size(file_size)}",
            connection=conn,
        )
    return new_file_id, final_name


@router.get(
    "/category/{slug}",
    response_class=HTMLResponse,
    responses={
        404: {"description": "Kategori tidak ditemukan"},
    },
)
async def category_detail(request: Request, slug: str):
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

    clean_slug = slug.strip().lower()
    if clean_slug not in CATEGORY_MAP:
        raise HTTPException(status_code=404, detail="Kategori tidak ditemukan")

    category_info = CATEGORY_MAP[clean_slug]

    select_sql = (
        "SELECT id, category_slug, original_filename, stored_filename, "
        "file_size, mime_type, extension, created_at FROM files "
        "WHERE category_slug = ? ORDER BY created_at DESC, id DESC"
    )
    with get_db() as conn:
        cursor = conn.execute(select_sql, (clean_slug,))
        db_files = cursor.fetchall()

        # Fetch tags for all files in this category in one query
        file_ids = [f["id"] for f in db_files]
        tags_by_file: dict[int, list[dict]] = {fid: [] for fid in file_ids}
        if file_ids:
            placeholders = ",".join("?" * len(file_ids))
            tags_cursor = conn.execute(
                f"SELECT id, file_id, tag_name, tag_color FROM file_tags "
                f"WHERE file_id IN ({placeholders}) ORDER BY id ASC",
                file_ids,
            )
            for tag_row in tags_cursor.fetchall():
                tags_by_file[tag_row["file_id"]].append(
                    {
                        "id": tag_row["id"],
                        "tag_name": tag_row["tag_name"],
                        "tag_color": tag_row["tag_color"],
                    }
                )

    files: list[dict[str, Any]] = []
    total_size = 0
    for f in db_files:
        size = int(f["file_size"])
        total_size += size
        files.append(
            {
                "id": f["id"],
                "original_filename": f["original_filename"],
                "file_size": size,
                "size_formatted": format_file_size(size),
                "extension": f["extension"],
                "icon": get_file_icon(str(f["extension"])),
                "created_at_wib": format_wib(f["created_at"]),
                "tags": tags_by_file.get(f["id"], []),
            }
        )

    nav_cats = get_nav_categories()

    return templates.TemplateResponse(
        request=request,
        name="category.html",
        context={
            "current_user": user_session,
            "csrf_token": user_session["csrf_token"],
            "active_nav": clean_slug,
            "nav_categories": nav_cats,
            "category": category_info,
            "files": files,
            "total_files": len(files),
            "total_size_formatted": format_file_size(total_size),
            "allowed_extensions": settings.ALLOWED_EXTENSIONS,
        },
    )


@router.post(
    "/api/files/upload",
    responses={
        400: {"description": "Permintaan berkas tidak valid"},
        403: {"description": "Token CSRF tidak valid"},
        413: {"description": "Ukuran berkas melebihi batas"},
        500: {"description": "Gagal menyimpan berkas"},
    },
)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    category_slug: str = Form(...),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    user_session = get_current_user_session(request)

    if not verify_csrf(user_session, x_csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MSG_CSRF_INVALID,
        )

    clean_slug = category_slug.strip().lower()
    if clean_slug not in CATEGORY_MAP:
        raise HTTPException(
            status_code=400, detail="Kategori berkas tidak valid"
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="Nama berkas kosong")

    sanitized_original = sanitize_filename(file.filename)
    ext = get_file_extension(sanitized_original)

    if ext not in settings.allowed_ext_set:
        allowed_list = settings.ALLOWED_EXTENSIONS
        raise HTTPException(
            status_code=400,
            detail=(
                f"Format berkas '{ext}' tidak diizinkan. "
                f"Ekstensi yang didukung: {allowed_list}"
            ),
        )

    upload_dir = settings.abs_upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_name = generate_stored_filename(sanitized_original)
    target_path = (upload_dir / stored_name).resolve()

    if not str(target_path).startswith(str(upload_dir.resolve())):
        raise HTTPException(status_code=400, detail="Akses path tidak valid")

    try:
        file_size = await _save_upload_stream(
            file, target_path, settings.max_upload_size_bytes
        )
    except HTTPException:
        raise
    except Exception as err:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menulis berkas ke penyimpanan: {err!s}",
        ) from err

    try:
        new_file_id, final_name = _save_file_record(
            clean_slug=clean_slug,
            original_name=sanitized_original,
            stored_name=stored_name,
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            ext=ext,
            ip_addr=get_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
        )
    except Exception as err:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mencatat berkas ke database: {err!s}",
        ) from err

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": f"Berkas '{final_name}' berhasil diunggah",
            "file": {
                "id": new_file_id,
                "original_filename": final_name,
                "size_formatted": format_file_size(file_size),
                "category_slug": clean_slug,
            },
        },
    )


@router.get(
    "/api/files/download/{file_id}",
    responses={
        404: {"description": "Berkas tidak ditemukan"},
    },
)
async def download_file(request: Request, file_id: int):
    _ = get_current_user_session(request)

    query_sql = (
        "SELECT id, category_slug, original_filename, "
        "stored_filename, file_size, mime_type FROM files WHERE id = ?"
    )
    with get_db() as conn:
        cursor = conn.execute(query_sql, (file_id,))
        record = cursor.fetchone()

    if record is None:
        raise HTTPException(status_code=404, detail=MSG_FILE_NOT_FOUND)

    file_path = (
        settings.abs_upload_dir / str(record["stored_filename"])
    ).resolve()
    base_dir = str(settings.abs_upload_dir.resolve())
    if not file_path.exists() or not str(file_path).startswith(base_dir):
        raise HTTPException(
            status_code=404,
            detail=MSG_PHYSICAL_FILE_NOT_FOUND,
        )

    original_filename = str(record["original_filename"])
    media_type = str(record["mime_type"])

    headers = {
        "Content-Disposition": f'attachment; filename="{original_filename}"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }

    return FileResponse(
        path=str(file_path),
        filename=original_filename,
        media_type=media_type,
        headers=headers,
    )


@router.get(
    "/api/files/view/{file_id}",
    responses={
        404: {"description": "Berkas tidak ditemukan"},
    },
)
async def view_file(request: Request, file_id: int):
    """View file directly in browser with inline disposition (no download)."""
    _ = get_current_user_session(request)

    query_sql = (
        "SELECT id, category_slug, original_filename, "
        "stored_filename, file_size, mime_type FROM files WHERE id = ?"
    )
    with get_db() as conn:
        cursor = conn.execute(query_sql, (file_id,))
        record = cursor.fetchone()

    if record is None:
        raise HTTPException(status_code=404, detail=MSG_FILE_NOT_FOUND)

    file_path = (
        settings.abs_upload_dir / str(record["stored_filename"])
    ).resolve()
    base_dir = str(settings.abs_upload_dir.resolve())
    if not file_path.exists() or not str(file_path).startswith(base_dir):
        raise HTTPException(
            status_code=404,
            detail=MSG_PHYSICAL_FILE_NOT_FOUND,
        )

    original_filename = str(record["original_filename"])
    ext = get_file_extension(original_filename)

    # Determine optimal media type for inline viewing in browser
    if ext in [
        ".txt", ".log", ".cfg", ".conf", ".ini", ".json",
        ".xml", ".yml", ".md", ".py", ".sh", ".sql", ".csv",
    ]:
        media_type = "text/plain; charset=utf-8"
    elif ext == ".pdf":
        media_type = "application/pdf"
    elif ext in [".png", ".jpg", ".jpeg"]:
        media_type = f"image/{ext.replace('.', '')}"
    else:
        media_type = str(record["mime_type"] or "application/octet-stream")

    headers = {
        "Content-Disposition": f'inline; filename="{original_filename}"',
        "Cache-Control": "no-cache",
        "X-Content-Type-Options": "nosniff",
    }

    return FileResponse(
        path=str(file_path),
        filename=original_filename,
        media_type=media_type,
        headers=headers,
    )


@router.delete(
    "/api/files/{file_id}",
    responses={
        403: {"description": "Token CSRF tidak valid"},
        404: {"description": "Berkas tidak ditemukan"},
    },
)
async def delete_file(
    request: Request,
    file_id: int,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    user_session = get_current_user_session(request)

    if not verify_csrf(user_session, x_csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MSG_CSRF_INVALID,
        )

    select_sql = (
        "SELECT id, category_slug, original_filename, "
        "stored_filename, file_size FROM files WHERE id = ?"
    )
    with get_db() as conn:
        cursor = conn.execute(select_sql, (file_id,))
        record = cursor.fetchone()

        if record is None:
            raise HTTPException(
                status_code=404, detail=MSG_FILE_NOT_FOUND
            )

        ip_address = get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        stored_name = str(record["stored_filename"])
        original_name = str(record["original_filename"])
        cat_slug = str(record["category_slug"])

        conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        log_activity(
            activity_type="DELETE_FILE",
            original_filename=original_name,
            category_slug=cat_slug,
            ip_address=ip_address,
            user_agent=user_agent,
            details="Berkas berhasil dihapus oleh pengguna",
            connection=conn,
        )

    file_path = settings.abs_upload_dir / stored_name
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            pass

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": f"Berkas '{original_name}' berhasil dihapus",
        },
    )


_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@router.post(
    "/api/files/{file_id}/tags",
    responses={
        400: {"description": "Nama atau warna tag tidak valid"},
        403: {"description": "Token CSRF tidak valid"},
        404: {"description": "Berkas tidak ditemukan"},
    },
)
async def add_file_tag(
    request: Request,
    file_id: int,
    tag_name: str = Form(...),
    tag_color: str = Form(default="#64748b"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    user_session = get_current_user_session(request)

    if not verify_csrf(user_session, x_csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MSG_CSRF_INVALID,
        )

    tag_name = tag_name.strip()
    if not tag_name or len(tag_name) > 30:
        raise HTTPException(
            status_code=400,
            detail="Nama tag wajib diisi dan maksimal 30 karakter",
        )
    if not _HEX_COLOR_RE.match(tag_color):
        raise HTTPException(
            status_code=400,
            detail="Warna tag harus format hex (#rrggbb)",
        )

    now = utc_now_iso()
    with get_db() as conn:
        # Verify file exists
        row = conn.execute(
            "SELECT id FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail=MSG_FILE_NOT_FOUND
            )

        cursor = conn.execute(
            "INSERT INTO file_tags (file_id, tag_name, tag_color, created_at) "
            "VALUES (?, ?, ?, ?)",
            (file_id, tag_name, tag_color, now),
        )
        new_tag_id = int(cursor.lastrowid or 0)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "tag": {
                "id": new_tag_id,
                "tag_name": tag_name,
                "tag_color": tag_color,
            },
        },
    )


@router.delete(
    "/api/files/{file_id}/tags/{tag_id}",
    responses={
        403: {"description": "Token CSRF tidak valid"},
        404: {"description": "Tag tidak ditemukan"},
    },
)
async def delete_file_tag(
    request: Request,
    file_id: int,
    tag_id: int,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    user_session = get_current_user_session(request)

    if not verify_csrf(user_session, x_csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MSG_CSRF_INVALID,
        )

    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM file_tags WHERE id = ? AND file_id = ?",
            (tag_id, file_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Tag tidak ditemukan")

        conn.execute("DELETE FROM file_tags WHERE id = ?", (tag_id,))

    return JSONResponse(
        status_code=200,
        content={"success": True},
    )
