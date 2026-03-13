@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
if not defined DATABASE_URL set "DATABASE_URL=sqlite:///%ROOT_DIR:\=/%/cipherforge-dev.db"
if not defined WIPE_ENGINE_DRY_RUN set "WIPE_ENGINE_DRY_RUN=true"

cd /d "%ROOT_DIR%"
python -m uvicorn main:app --host 0.0.0.0 --port 8000
