@echo off
title Catatan Saya - E-BOOK Vault Server
echo ===================================================
echo   Menjalankan Server E-BOOK Vault di Port 8000...
echo   Akses: http://127.0.0.1:8000
echo ===================================================
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
) else (
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
)
pause
