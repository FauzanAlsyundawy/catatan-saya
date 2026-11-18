#!/usr/bin/env python3
"""Restore utility for Catatan Saya - E-BOOK Enterprise.

Restores database and uploaded files from a selected backup ZIP.
"""

import sys
import zipfile
from pathlib import Path


def restore_backup(backup_zip_path: str):
    zip_path = Path(backup_zip_path).resolve()
    if not zip_path.exists():
        print(f"[x] File backup tidak ditemukan: {zip_path}")
        sys.exit(1)

    base_dir = Path(__file__).resolve().parent.parent

    print(f"[*] Memulihkan dari: {zip_path.name} ke {base_dir}")
    with zipfile.ZipFile(zip_path, "r") as zipf:
        zipf.extractall(base_dir)

    print("[✓] Pemulihan database dan file berhasil diselesaikan!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Penggunaan: python scripts/restore.py <path_ke_file_backup.zip>"
        )
        sys.exit(1)
    restore_backup(sys.argv[1])
