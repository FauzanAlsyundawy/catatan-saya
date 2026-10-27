import io
import re
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import settings
from app.database import init_db, get_db
from app.security import (
    hash_password,
    verify_password,
    record_login_attempt,
    check_login_rate_limit,
)
from app.utils.storage import (
    sanitize_filename,
    resolve_duplicate_filename,
)
from app.utils.timezone import format_wib, utc_now_iso


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure database and tables exist for testing."""
    init_db()


def test_argon2id_hashing():
    password = "SuperSecretPassword123!"
    pw_hash = hash_password(password)
    assert pw_hash.startswith("$argon2id$")
    assert verify_password(pw_hash, password) is True
    assert verify_password(pw_hash, "WrongPassword") is False


def test_filename_sanitization_and_duplicate():
    dirty = "../../../etc/passwd\x00malicious.docx"
    clean = sanitize_filename(dirty)
    assert ".." not in clean
    assert "/" not in clean
    assert "\x00" not in clean

    existing = {"catatan.docx", "catatan (1).docx"}
    candidate = resolve_duplicate_filename(existing, "catatan.docx")
    assert candidate == "catatan (2).docx"


def test_wib_timezone_formatting():
    iso_time = "2026-10-26T14:15:42+00:00"
    formatted = format_wib(iso_time)
    assert "26 Oktober 2026" in formatted
    assert "21:15:42 WIB" in formatted


def test_rate_limiting():
    ip = "192.168.1.99"
    user = "audit_test_user"

    with get_db() as conn:
        conn.execute(
            "DELETE FROM login_attempts WHERE ip_address = ?", (ip,)
        )

    for _ in range(4):
        record_login_attempt(ip, user, success=False)
    allowed, _ = check_login_rate_limit(ip, user)
    assert allowed is True

    record_login_attempt(ip, user, success=False)
    allowed, remaining = check_login_rate_limit(ip, user)
    assert allowed is False
    assert remaining > 0


@pytest.mark.asyncio
async def test_unauthenticated_redirect():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/login"

        response = await client.get("/category/word", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/login"

        response = await client.get("/audit-log", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/login"


@pytest.mark.asyncio
async def test_security_headers():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/login")
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "Content-Security-Policy" in response.headers
        assert "Cache-Control" in response.headers


@pytest.mark.asyncio
async def test_full_auth_and_file_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        test_user = "testadmin"
        test_pass = "AdminVault2026!"
        with get_db() as conn:
            conn.execute(
                "DELETE FROM users WHERE username = ?", (test_user,)
            )
            insert_user_sql = (
                "INSERT INTO users (username, password_hash, created_at) "
                "VALUES (?, ?, ?)"
            )
            conn.execute(
                insert_user_sql,
                (test_user, hash_password(test_pass), utc_now_iso()),
            )

        login_res = await client.get("/login")
        assert login_res.status_code == 200
        temp_csrf = client.cookies.get("temp_csrf_token")
        assert temp_csrf is not None

        fail_res = await client.post(
            "/auth/login",
            data={
                "username": test_user,
                "password": "WrongPassword!",
                "csrf_token": temp_csrf,
            },
        )
        assert fail_res.status_code == 400
        assert "Username atau password salah" in fail_res.text

        login_post = await client.post(
            "/auth/login",
            data={
                "username": test_user,
                "password": test_pass,
                "csrf_token": temp_csrf,
            },
            follow_redirects=False,
        )
        assert login_post.status_code == 302
        assert login_post.headers["location"] == "/"
        session_cookie = client.cookies.get(settings.SESSION_COOKIE_NAME)
        assert session_cookie is not None

        dash_res = await client.get("/")
        assert dash_res.status_code == 200
        assert "Catatan Saya" in dash_res.text
        assert "Word" in dash_res.text
        assert "Notepad++" in dash_res.text

        csrf_match = re.search(
            r'name="csrf-token" content="([^"]+)"', dash_res.text
        )
        assert csrf_match is not None
        user_csrf = csrf_match.group(1)

        bad_file = (
            "malicious.exe",
            io.BytesIO(b"executable data"),
            "application/octet-stream",
        )
        bad_upload = await client.post(
            "/api/files/upload",
            files={"file": bad_file},
            data={"category_slug": "word"},
            headers={"X-CSRF-Token": user_csrf},
        )
        assert bad_upload.status_code == 400
        assert "tidak diizinkan" in bad_upload.text

        doc_content = b"Dokumen penting catatan arsitektur enterprise 2026."
        valid_file = (
            "Catatan_Arsitektur.docx",
            io.BytesIO(doc_content),
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document",
        )
        upload_res = await client.post(
            "/api/files/upload",
            files={"file": valid_file},
            data={"category_slug": "word"},
            headers={"X-CSRF-Token": user_csrf},
        )
        assert upload_res.status_code == 200
        upload_data = upload_res.json()
        assert upload_data["success"] is True
        file_id = upload_data["file"]["id"]

        valid_file_dup = (
            "Catatan_Arsitektur.docx",
            io.BytesIO(doc_content),
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document",
        )
        dup_res = await client.post(
            "/api/files/upload",
            files={"file": valid_file_dup},
            data={"category_slug": "word"},
            headers={"X-CSRF-Token": user_csrf},
        )
        assert dup_res.status_code == 200
        dup_data = dup_res.json()
        assert (
            dup_data["file"]["original_filename"]
            == "Catatan_Arsitektur (1).docx"
        )
        dup_file_id = dup_data["file"]["id"]

        download_res = await client.get(f"/api/files/download/{file_id}")
        assert download_res.status_code == 200
        assert download_res.content == doc_content
        disposition = download_res.headers["Content-Disposition"]
        assert 'attachment; filename="Catatan_Arsitektur.docx"' in disposition

        del_res = await client.delete(
            f"/api/files/{file_id}", headers={"X-CSRF-Token": user_csrf}
        )
        assert del_res.status_code == 200
        assert del_res.json()["success"] is True

        await client.delete(
            f"/api/files/{dup_file_id}", headers={"X-CSRF-Token": user_csrf}
        )

        audit_res = await client.get("/audit-log")
        assert audit_res.status_code == 200
        assert (
            "UPLOAD_FILE" in audit_res.text
            or "Unggah Berkas" in audit_res.text
        )
        assert (
            "DELETE_FILE" in audit_res.text
            or "Hapus Berkas" in audit_res.text
        )
        assert "Catatan_Arsitektur.docx" in audit_res.text
        assert "WIB" in audit_res.text

        logout_res = await client.post(
            "/auth/logout",
            data={"csrf_token": user_csrf},
            follow_redirects=False,
        )
        assert logout_res.status_code == 302
        assert logout_res.headers["location"] == "/login"

        after_logout_res = await client.get("/", follow_redirects=False)
        assert after_logout_res.status_code == 302


@pytest.mark.asyncio
async def test_regular_user_cannot_access_audit_log():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        test_user = "test_regular_user"
        test_pass = "RegularUserPassword2026!"
        with get_db() as conn:
            conn.execute(
                "DELETE FROM users WHERE username = ?", (test_user,)
            )
            insert_user_sql = (
                "INSERT INTO users (username, password_hash, role, created_at) "
                "VALUES (?, ?, 'user', ?)"
            )
            conn.execute(
                insert_user_sql,
                (test_user, hash_password(test_pass), utc_now_iso()),
            )

        login_res = await client.get("/login")
        temp_csrf = client.cookies.get("temp_csrf_token")

        login_post = await client.post(
            "/auth/login",
            data={
                "username": test_user,
                "password": test_pass,
                "csrf_token": temp_csrf,
            },
            follow_redirects=False,
        )
        assert login_post.status_code == 302
        assert login_post.headers["location"] == "/"

        # Dashboard accessible, role shown as Pengguna, Log Aktivitas NOT in sidebar
        dash_res = await client.get("/")
        assert dash_res.status_code == 200
        assert "Log Aktivitas" not in dash_res.text
        assert "Pengguna" in dash_res.text

        # Direct access to /audit-log is blocked and redirected to /
        audit_res = await client.get("/audit-log", follow_redirects=False)
        assert audit_res.status_code == 302
        assert audit_res.headers["location"] == "/"

        # Verify activity was logged in audit_logs table
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT activity_type, details FROM audit_logs WHERE details LIKE ?",
                (f"%{test_user}%",),
            )
            logs = cursor.fetchall()
            assert len(logs) > 0
            assert any(r["activity_type"] == "LOGIN_SUCCESS" for r in logs)

