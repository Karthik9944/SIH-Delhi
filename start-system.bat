@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

set "BACKEND_DIR=%ROOT_DIR%"
set "FRONTEND_DIR=%ROOT_DIR%\cipherforge-dashboard"
if not defined BACKEND_PORT set "BACKEND_PORT=8000"
if not defined FRONTEND_PORT set "FRONTEND_PORT=4300"
if not defined DATABASE_URL set "DATABASE_URL=sqlite:///%ROOT_DIR:\=/%/cipherforge-dev.db"
if not defined WIPE_ENGINE_DRY_RUN set "WIPE_ENGINE_DRY_RUN=true"

echo ================================================
echo CipherForge System Startup
echo Root: %ROOT_DIR%
echo DATABASE_URL: %DATABASE_URL%
echo ================================================

call :start_postgres
call :start_backend
call :start_frontend

echo.
echo ================================================
echo Startup sequence completed.
echo FastAPI Backend: http://localhost:%BACKEND_PORT%
echo Angular UI    : http://localhost:%FRONTEND_PORT%
echo ================================================
exit /b 0

:start_postgres
echo.
echo [1/3] Checking PostgreSQL (port 5432)...
call :is_port_open 5432
if /I "!OPEN!"=="true" (
  echo PostgreSQL detected.
  echo Note: local startup now defaults to SQLite unless DATABASE_URL is overridden.
  exit /b 0
)

echo PostgreSQL not detected. Continuing with local SQLite default.
exit /b 0

:start_backend
echo.
echo [2/3] Checking FastAPI backend (port %BACKEND_PORT%)...
call :is_port_open %BACKEND_PORT%
if /I "!OPEN!"=="true" (
  echo FastAPI backend already running on port %BACKEND_PORT%.
  exit /b 0
)

if not exist "%BACKEND_DIR%\main.py" (
  echo ERROR: Backend main.py not found at "%BACKEND_DIR%\main.py"
  exit /b 1
)

echo Starting FastAPI backend...
start "CipherForge FastAPI Backend" cmd /k "cd /d ""%BACKEND_DIR%"" && set DATABASE_URL=%DATABASE_URL% && set WIPE_ENGINE_DRY_RUN=%WIPE_ENGINE_DRY_RUN% && python -m uvicorn main:app --host 0.0.0.0 --port %BACKEND_PORT%"
call :wait_for_port %BACKEND_PORT% 45
if !errorlevel! EQU 0 (
  echo FastAPI backend started on port %BACKEND_PORT%.
) else (
  echo WARNING: FastAPI backend did not open port %BACKEND_PORT% in time.
)
exit /b 0

:start_frontend
echo.
echo [3/3] Checking Angular frontend (port %FRONTEND_PORT%)...
call :is_port_open %FRONTEND_PORT%
if /I "!OPEN!"=="true" (
  echo Angular frontend already running on port %FRONTEND_PORT%.
  exit /b 0
)

if not exist "%FRONTEND_DIR%\angular.json" (
  echo ERROR: Frontend angular.json not found at "%FRONTEND_DIR%\angular.json"
  exit /b 1
)

echo Starting Angular frontend...
start "CipherForge Angular Frontend" cmd /k "cd /d ""%FRONTEND_DIR%"" && ng serve --port %FRONTEND_PORT%"
call :wait_for_port %FRONTEND_PORT% 60
if !errorlevel! EQU 0 (
  echo Angular frontend started on port %FRONTEND_PORT%.
) else (
  echo WARNING: Angular frontend did not open port %FRONTEND_PORT% in time.
)
exit /b 0

:is_port_open
set "OPEN=false"
for /f "tokens=1" %%A in ('netstat -ano ^| findstr /R /C:":%~1 .*LISTENING" 2^>nul') do (
  set "OPEN=true"
  goto :eof
)
exit /b 0

:wait_for_port
set /a WAIT_SECONDS=0
:wait_loop
call :is_port_open %~1
if /I "!OPEN!"=="true" exit /b 0
if !WAIT_SECONDS! GEQ %~2 exit /b 1
set /a WAIT_SECONDS+=1
timeout /t 1 /nobreak >nul
goto :wait_loop
