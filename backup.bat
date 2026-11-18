@echo off
title Catatan Saya - Backup Utility
echo ===================================================
echo   Membuat Cadangan Database dan File Upload...
echo ===================================================
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" scripts\backup.py
) else (
    python scripts\backup.py
)
pause
