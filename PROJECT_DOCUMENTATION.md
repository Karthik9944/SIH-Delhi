# CipherForge Documentation

## Architecture

CipherForge now runs as a unified Python system:

Angular Dashboard
-> FastAPI Backend
-> Python wipe engine modules
-> Database (SQLite by default for local startup, PostgreSQL via DATABASE_URL when configured)

## Repository Layout

- `backend/` - FastAPI application, routers, services, SQLAlchemy models, config, and startup wiring.
- `cipherforge-dashboard/` - Angular dashboard.
- `wipe_engine_service/` - Reused wipe engine modules for device detection, secure erase, filesystem browsing, certificate generation, and forensic verification.
- `data_wipe.py` - Legacy desktop wipe utility retained as a standalone tool.
- `certificates/` - Generated wipe evidence output.
- `main.py` - Root ASGI entrypoint that exposes `backend.main:app` as `main:app`.
- `cipherforge-dev.db` - Local SQLite database created automatically for development startup.

## Local Startup

1. Install backend dependencies:
   - `pip install -r requirements.txt`
2. Start the backend:
   - `python -m uvicorn main:app --host 0.0.0.0 --port 8000`
3. Start the Angular app from `cipherforge-dashboard/`:
   - `npm install`
   - `ng serve --port 4300`

You can also use `run-upgraded-cipherforge.bat` to install dependencies and start the stack.

## Database Modes

### Default local mode

If `DATABASE_URL` is not set, CipherForge uses:

- `sqlite:///.../cipherforge-dev.db`

This is the recommended local setup for immediate startup.

### PostgreSQL mode

To use PostgreSQL, set a valid `DATABASE_URL` before launching the backend. Example:

- `postgresql+psycopg://postgres:YOUR_REAL_PASSWORD@localhost:5432/cipherforge`

## Default Credentials

- Admin: `admin` / `admin12345`
- Operator: `operator` / `operator12345`

## Primary API Endpoints

- `GET /health`
- `POST /auth/login`
- `GET /devices`
- `GET /drives`
- `GET /filesystem?path=C:\\Users`
- `GET /wipe/methods`
- `POST /wipe/start`
- `POST /wipe/device`
- `GET /wipe/status/{job_id}`
- `GET /wipe/jobs`
- `POST /wipe/file`
- `POST /wipe/folder`
- `POST /wipe/folder/start`
- `GET /wipe/folder/status/{job_id}`
- `GET /certificates`
- `GET /certificate/{id}`
- `GET /certificate/download/{job_id}`
- `GET /certificate/download-json/{job_id}`
- `GET /verify/{certificate_id}`
- `GET /admin/stats`
- `WS /ws/progress`

## Notes

- Device wipes run through the Python wipe engine in background worker threads.
- For safety, device wipes default to dry-run mode unless `WIPE_ENGINE_DRY_RUN=false` is set.
- Certificate generation uses `reportlab` when available and writes JSON/PDF evidence into `certificates/`.
- Forensic verification attempts to use `photorec` and `testdisk` when installed.
