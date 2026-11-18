#!/usr/bin/env python3
"""Backup utility for Catatan Saya - E-BOOK Enterprise.

Creates a timestamped ZIP archive containing database and uploaded files.
"""

import os
import zipfile
from datetime import datetime
from pathlib import Path


def create_backup():
    base_dir = Path(__file__).resolve().parent.parent
    backups_dir = base_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{timestamp}.zip"
    backup_path = backups_dir / backup_filename

    db_path = base_dir / "data" / "app.db"
    uploads_dir = base_dir / "uploads"

    print(f"[*] Memulai proses pencadangan ke: {backup_path.name}")

    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        if db_path.exists():
            zipf.write(db_path, arcname="data/app.db")
            print("[+] Basis data berhasil dicadangkan: data/app.db")
        else:
            print("[!] Basis data data/app.db tidak ditemukan, dilewati.")

        if uploads_dir.exists():
            file_count = 0
            for root, _, files in os.walk(uploads_dir):
                for f in files:
                    if f == ".gitkeep":
                        continue
                    full_p = Path(root) / f
                    arc_p = Path("uploads") / full_p.relative_to(uploads_dir)
                    zipf.write(full_p, arcname=str(arc_p))
                    file_count += 1
            print(f"[+] Total {file_count} berkas berhasil dicadangkan.")

    size_mb = backup_path.stat().st_size / (1024 * 1024)
    print(f"[✓] Arsip dibuat: {size_mb:.2f} MB")
    print(f"[✓] Lokasi: {backup_path}")
    return backup_path


if __name__ == "__main__":
    create_backup()
