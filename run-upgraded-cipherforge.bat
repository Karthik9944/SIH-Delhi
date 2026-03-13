@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

set "FRONTEND_DIR=%ROOT_DIR%\cipherforge-dashboard"
set "REQUIREMENTS_FILE=%ROOT_DIR%\requirements.txt"
if not defined BACKEND_PORT set "BACKEND_PORT=8000"
if not defined FRONTEND_PORT set "FRONTEND_PORT=4300"
if not defined DATABASE_URL set "DATABASE_URL=sqlite:///%ROOT_DIR:\=/%/cipherforge-dev.db"
if not defined WIPE_ENGINE_DRY_RUN set "WIPE_ENGINE_DRY_RUN=true"

call :resolve_python
if errorlevel 1 exit /b 1

echo ================================================
echo CipherForge Upgraded System Launcher
echo Root            : %ROOT_DIR%
echo Python          : %PYTHON_EXE%
echo Backend URL     : http://localhost:%BACKEND_PORT%
echo Frontend URL    : http://localhost:%FRONTEND_PORT%
echo DATABASE_URL    : %DATABASE_URL%
echo WIPE_ENGINE_DRY_RUN : %WIPE_ENGINE_DRY_RUN%
echo ================================================

call :start_postgres
call :ensure_backend_dependencies
call :ensure_frontend_dependencies
call :start_backend
call :start_frontend

echo.
echo ================================================
echo CipherForge upgraded stack is starting.
echo Backend health : http://localhost:%BACKEND_PORT%/health
echo Angular UI     : http://localhost:%FRONTEND_PORT%
echo Default login  : admin / admin12345
echo ================================================
exit /b 0

:resolve_python
if exist "%ROOT_DIR%\.venv\Scripts\python.exe" (
  set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
  exit /b 0
)
where python >nul 2>&1
if %errorlevel% EQU 0 (
  set "PYTHON_EXE=python"
  exit /b 0
)
echo ERROR: Python was not found. Install Python or create .venv first.
exit /b 1

:start_postgres
echo.
echo [1/5] Checking PostgreSQL (port 5432)...
call :is_port_open 5432
if /I "!OPEN!"=="true" (
  echo PostgreSQL detected.
  echo Note: local startup now defaults to SQLite unless DATABASE_URL is overridden.
  exit /b 0
)

echo PostgreSQL not detected. Continuing with local SQLite default.
exit /b 0

:ensure_backend_dependencies
echo.
echo [2/5] Checking backend Python dependencies...
%PYTHON_EXE% -c "import fastapi, sqlalchemy, uvicorn" >nul 2>&1
if %errorlevel% EQU 0 (
  echo Backend Python dependencies already available.
  exit /b 0
)

if not exist "%REQUIREMENTS_FILE%" (
  echo ERROR: requirements.txt not found at "%REQUIREMENTS_FILE%"
  exit /b 1
)

echo Installing backend dependencies from requirements.txt...
call "%PYTHON_EXE%" -m pip install -r "%REQUIREMENTS_FILE%"
if errorlevel 1 (
  echo ERROR: Backend dependency installation failed.
  exit /b 1
)
echo Backend dependencies installed.
exit /b 0

:ensure_frontend_dependencies
echo.
echo [3/5] Checking Angular dependencies...
if not exist "%FRONTEND_DIR%\package.json" (
  echo ERROR: Frontend package.json not found at "%FRONTEND_DIR%\package.json"
  exit /b 1
)
if exist "%FRONTEND_DIR%\node_modules" (
  echo Frontend dependencies already present.
  exit /b 0
)

echo Installing frontend dependencies with npm install...
pushd "%FRONTEND_DIR%"
call npm install
set "NPM_RESULT=%errorlevel%"
popd
if not "%NPM_RESULT%"=="0" (
  echo ERROR: npm install failed.
  exit /b 1
)
echo Frontend dependencies installed.
exit /b 0

:start_backend
echo.
echo [4/5] Checking FastAPI backend (port %BACKEND_PORT%)...
call :is_port_open %BACKEND_PORT%
if /I "!OPEN!"=="true" (
  echo FastAPI backend already running on port %BACKEND_PORT%.
  exit /b 0
)
if not exist "%ROOT_DIR%\main.py" (
  echo ERROR: main.py not found at "%ROOT_DIR%\main.py"
  exit /b 1
)

echo Starting FastAPI backend...
start "CipherForge FastAPI Backend" cmd /k "cd /d ""%ROOT_DIR%"" && set DATABASE_URL=%DATABASE_URL% && set WIPE_ENGINE_DRY_RUN=%WIPE_ENGINE_DRY_RUN% && %PYTHON_EXE% -m uvicorn main:app --host 0.0.0.0 --port %BACKEND_PORT%"
call :wait_for_port %BACKEND_PORT% 45
if !errorlevel! EQU 0 (
  echo FastAPI backend started on port %BACKEND_PORT%.
) else (
  echo WARNING: FastAPI backend did not open port %BACKEND_PORT% in time.
)
exit /b 0

:start_frontend
echo.
echo [5/5] Checking Angular frontend (port %FRONTEND_PORT%)...
call :is_port_open %FRONTEND_PORT%
if /I "!OPEN!"=="true" (
  echo Angular frontend already running on port %FRONTEND_PORT%.
  exit /b 0
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
