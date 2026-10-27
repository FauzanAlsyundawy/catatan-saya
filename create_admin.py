#!/usr/bin/env python3
"""Skrip CLI interaktif untuk membuat atau memperbarui akun Administrator
untuk website Catatan Saya.
Kredensial di-hash dengan Argon2id dan disimpan di SQLite.
"""

import argparse
import getpass
import sys

from app.database import get_db, init_db
from app.security import hash_password
from app.utils.timezone import utc_now_iso


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inisialisasi akun Administrator Catatan Saya"
    )
    parser.add_argument(
        "--username",
        help="Username admin (opsional, jika ingin non-interaktif)",
        default=None,
    )
    parser.add_argument(
        "--password",
        help="Password admin (opsional, jika ingin non-interaktif)",
        default=None,
    )
    parser.add_argument(
        "--role",
        help="Role pengguna ('admin' atau 'user', default: 'admin')",
        default="admin",
        choices=["admin", "user"],
    )
    args = parser.parse_args()

    role = args.role.strip().lower()

    print("=" * 60)
    print("  CATATAN SAYA - INISIALISASI PENGGUNA & ROLE (ENTERPRISE)")
    print("=" * 60)

    # Inisialisasi skema DB jika belum ada
    init_db()

    raw_user: str | None = args.username
    if not raw_user:
        try:
            raw_user = input("Masukkan Username: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[!] Dibatalkan oleh pengguna.")
            sys.exit(1)

    username: str = raw_user.strip()
    if len(username) < 3:
        print("[X] Error: Username minimal harus 3 karakter.")
        sys.exit(1)

    raw_pass: str | None = args.password
    if not raw_pass:
        try:
            input_pass = getpass.getpass("Masukkan Password: ")
            confirm_pass = getpass.getpass("Konfirmasi Password: ")
        except (KeyboardInterrupt, EOFError):
            print("\n[!] Dibatalkan oleh pengguna.")
            sys.exit(1)

        if input_pass != confirm_pass:
            print("[X] Error: Konfirmasi password tidak cocok!")
            sys.exit(1)
        raw_pass = input_pass

    admin_secret: str = raw_pass
    if len(admin_secret) < 8:
        print(
            "[X] Error: Password minimal harus 8 karakter "
            "untuk standar keamanan."
        )
        sys.exit(1)

    print("[*] Melakukan hashing password dengan Argon2id...")
    pw_hash = hash_password(admin_secret)
    now = utc_now_iso()

    with get_db() as conn:
        find_sql = "SELECT id, username FROM users WHERE username = ?"
        cursor = conn.execute(find_sql, (username,))
        existing = cursor.fetchone()

        if existing is not None:
            user_id = existing["id"]
            conn.execute(
                "UPDATE users SET password_hash = ?, role = ? WHERE id = ?",
                (pw_hash, role, user_id),
            )
            print(
                f"[OK] Akun '{username}' berhasil diperbarui "
                f"dengan role '{role}'."
            )
        else:
            insert_sql = (
                "INSERT INTO users (username, password_hash, role, created_at) "
                "VALUES (?, ?, ?, ?)"
            )
            conn.execute(insert_sql, (username, pw_hash, role, now))
            print(
                f"[OK] Pengguna '{username}' (role: {role}) "
                f"berhasil didaftarkan ke sistem."
            )

    print("=" * 60)
    print("Inisialisasi selesai. Anda dapat menjalankan aplikasi sekarang.")
    print("=" * 60)


if __name__ == "__main__":
    main()
