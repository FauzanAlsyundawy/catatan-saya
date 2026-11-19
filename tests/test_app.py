import io
import re

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import get_db, init_db
from app.main import app, seed_initial_users
from app.security import (
    check_login_rate_limit,
    hash_password,
    record_login_attempt,
    verify_password,
)
from app.utils.storage import (
    resolve_duplicate_filename,
    sanitize_filename,
)
from app.utils.timezone import format_wib, utc_now_iso


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Ensure database, tables, and seed users exist for testing."""
    test_db = tmp_path / "test.db"
    test_uploads = tmp_path / "uploads"
    test_uploads.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "DATABASE_PATH", str(test_db))
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(test_uploads))
    init_db()
    seed_initial_users()


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
        conn.execute("DELETE FROM login_attempts WHERE ip_address = ?", (ip,))

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
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
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
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/login")
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "Content-Security-Policy" in response.headers
        assert (
            "frame-ancestors 'none'"
            in response.headers["Content-Security-Policy"]
        )
        assert "Cache-Control" in response.headers


@pytest.mark.asyncio
async def test_full_auth_and_file_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        test_user = "testadmin"
        test_pass = "AdminVault2026!"
        with get_db() as conn:
            conn.execute("DELETE FROM users WHERE username = ?", (test_user,))
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
        assert "E-BOOK" in dash_res.text
        assert "Word" in dash_res.text
        assert "Notepad++" in dash_res.text

        csrf_match = re.search(r'name="csrf-token" content="([^"]+)"', dash_res.text)
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
            (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
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
            (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        dup_res = await client.post(
            "/api/files/upload",
            files={"file": valid_file_dup},
            data={"category_slug": "word"},
            headers={"X-CSRF-Token": user_csrf},
        )
        assert dup_res.status_code == 200
        dup_data = dup_res.json()
        assert dup_data["file"]["original_filename"] == "Catatan_Arsitektur (1).docx"
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
        assert "UPLOAD_FILE" in audit_res.text or "Unggah Berkas" in audit_res.text
        assert "DELETE_FILE" in audit_res.text or "Hapus Berkas" in audit_res.text
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
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        test_user = "test_regular_user"
        test_pass = "RegularUserPassword2026!"
        with get_db() as conn:
            conn.execute("DELETE FROM users WHERE username = ?", (test_user,))
            insert_user_sql = (
                "INSERT INTO users "
                "(username, password_hash, role, created_at) "
                "VALUES (?, ?, 'user', ?)"
            )
            conn.execute(
                insert_user_sql,
                (test_user, hash_password(test_pass), utc_now_iso()),
            )

        login_page_res = await client.get("/login")
        assert login_page_res.status_code == 200
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

        # Dashboard accessible, role shown as Pengguna.
        # Log Aktivitas NOT in sidebar
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
                "SELECT activity_type, details FROM audit_logs " "WHERE details LIKE ?",
                (f"%{test_user}%",),
            )
            logs = cursor.fetchall()
            assert len(logs) > 0
            assert any(r["activity_type"] == "LOGIN_SUCCESS" for r in logs)

        # Direct access to /users is also blocked for regular user
        users_res = await client.get("/users", follow_redirects=False)
        assert users_res.status_code == 302
        assert users_res.headers["location"] == "/"


@pytest.mark.asyncio
async def test_admin_user_management_and_active_session():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Login as administrator
        login_page_admin = await client.get("/login")
        assert login_page_admin.status_code == 200
        temp_csrf = client.cookies.get("temp_csrf_token")
        login_post = await client.post(
            "/auth/login",
            data={
                "username": "administrator",
                "password": "Fauzan@2026!",
                "csrf_token": temp_csrf,
            },
            follow_redirects=False,
        )
        assert login_post.status_code == 302

        # 2. Access /users page
        users_page = await client.get("/users")
        assert users_page.status_code == 200
        assert "Manajemen Pengguna" in users_page.text
        assert "administrator" in users_page.text
        assert "kencana" in users_page.text
        assert "Online / Aktif Sekarang" in users_page.text

        csrf_match = re.search(r'name="csrf-token" content="([^"]+)"', users_page.text)
        assert csrf_match is not None
        admin_csrf = csrf_match.group(1)

        # 3. Create a new user via API
        create_res = await client.post(
            "/api/users",
            data={
                "username": "tester_baru",
                "password": "PasswordBaru123!",
                "role": "user",
                "csrf_token": admin_csrf,
            },
        )
        assert create_res.status_code == 200
        assert create_res.json()["success"] is True

        with get_db() as conn:
            new_u = conn.execute(
                "SELECT id, username, role FROM users " "WHERE username = 'tester_baru'"
            ).fetchone()
            assert new_u is not None
            assert new_u["role"] == "user"
            new_uid = new_u["id"]

        # 4. Reset password
        reset_res = await client.post(
            f"/api/users/{new_uid}/reset-password",
            data={
                "new_password": "NewResetPassword2026!",
                "csrf_token": admin_csrf,
            },
        )
        assert reset_res.status_code == 200
        assert reset_res.json()["success"] is True

        # 5. Change role to admin
        role_res = await client.post(
            f"/api/users/{new_uid}/role",
            data={
                "role": "admin",
                "csrf_token": admin_csrf,
            },
        )
        assert role_res.status_code == 200
        assert role_res.json()["success"] is True

        # 6. Delete user
        del_res = await client.delete(
            f"/api/users/{new_uid}",
            headers={"X-CSRF-Token": admin_csrf},
        )
        assert del_res.status_code == 200
        assert del_res.json()["success"] is True


@pytest.mark.asyncio
async def test_search_and_tag_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Unauthenticated search fails
        unauth_search = await client.get("/api/search?q=test")
        assert unauth_search.status_code == 401

        # 2. Login as admin
        await client.get("/login")
        csrf = client.cookies.get("temp_csrf_token")
        login_res = await client.post(
            "/auth/login",
            data={
                "username": "administrator",
                "password": "Fauzan@2026!",
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert login_res.status_code == 302

        # 3. Check storage info
        storage_res = await client.get("/api/storage-info")
        assert storage_res.status_code == 200
        assert "total_bytes" in storage_res.json()

        # 4. Search with < 2 chars returns empty list
        short_search = await client.get("/api/search?q=a")
        assert short_search.status_code == 200
        assert short_search.json()["results"] == []

        # 5. Upload a test file to test tagging
        dash_res = await client.get("/")
        csrf_match = re.search(r'name="csrf-token" content="([^"]+)"', dash_res.text)
        assert csrf_match is not None
        user_csrf = csrf_match.group(1)

        doc_content = b"Content for tagging test."
        upload_res = await client.post(
            "/api/files/upload",
            files={"file": ("Test_Doc.txt", io.BytesIO(doc_content), "text/plain")},
            data={"category_slug": "notepadpp"},
            headers={"X-CSRF-Token": user_csrf},
        )
        assert upload_res.status_code == 200
        file_id = upload_res.json()["file"]["id"]

        # 6. Search finds the file
        search_res = await client.get("/api/search?q=Test_Doc")
        assert search_res.status_code == 200
        results = search_res.json()["results"]
        assert len(results) >= 1
        assert any(r["id"] == file_id for r in results)

        # 7. Add tag to file
        tag_res = await client.post(
            f"/api/files/{file_id}/tags",
            data={"tag_name": "Penting", "tag_color": "#e11d48"},
            headers={"X-CSRF-Token": user_csrf},
        )
        assert tag_res.status_code == 200
        tag_data = tag_res.json()
        assert tag_data["success"] is True
        tag_id = tag_data["tag"]["id"]

        # 8. Test inline file view without download
        view_res = await client.get(f"/api/files/view/{file_id}")
        assert view_res.status_code == 200
        assert "inline" in view_res.headers["content-disposition"]
        assert view_res.headers["X-Frame-Options"] == "SAMEORIGIN"
        assert (
            "frame-ancestors 'self'"
            in view_res.headers["Content-Security-Policy"]
        )
        assert view_res.content == doc_content

        # 9. Delete tag
        del_tag = await client.delete(
            f"/api/files/{file_id}/tags/{tag_id}",
            headers={"X-CSRF-Token": user_csrf},
        )
        assert del_tag.status_code == 200
        assert del_tag.json()["success"] is True

        # Clean up file
        await client.delete(
            f"/api/files/{file_id}",
            headers={"X-CSRF-Token": user_csrf},
        )
