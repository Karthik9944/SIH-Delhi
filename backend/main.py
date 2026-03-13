from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from .config import get_settings
from .database import get_session_factory, init_db
from .models.wipe_job import User, UserRole
from .routers.admin_router import router as admin_router
from .routers.certificate_router import router as certificate_router
from .routers.device_router import router as device_router
from .routers.filesystem_router import router as filesystem_router
from .routers.wipe_router import router as wipe_router
from .services import (
    CertificateGeneratorService,
    DeviceDetectorService,
    FileWiperService,
    ForensicVerifierService,
    ProgressConnectionManager,
    WipeManager,
)
from .utils.logger import configure_logging
from .utils.system_utils import hash_password

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("cipherforge.backend.app")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Unified FastAPI backend for CipherForge.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

progress_manager = ProgressConnectionManager()
device_detector = DeviceDetectorService()
file_wiper = FileWiperService()
certificate_generator = CertificateGeneratorService()
forensic_verifier = ForensicVerifierService()
wipe_manager = WipeManager(
    settings=settings,
    session_factory=get_session_factory(),
    device_detector=device_detector,
    certificate_generator=certificate_generator,
    forensic_verifier=forensic_verifier,
    progress_manager=progress_manager,
)

app.state.progress_manager = progress_manager
app.state.device_detector = device_detector
app.state.file_wiper = file_wiper
app.state.wipe_manager = wipe_manager

app.include_router(device_router)
app.include_router(filesystem_router)
app.include_router(wipe_router)
app.include_router(certificate_router)
app.include_router(admin_router)


@app.on_event("startup")
async def startup() -> None:
    progress_manager.bind_loop(asyncio.get_running_loop())
    try:
        init_db()
        _seed_default_users()
        logger.info("CipherForge backend initialized successfully.")
    except Exception:
        logger.exception("Database initialization failed.")
        if settings.strict_database_startup:
            raise


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "message": "Validation failed."})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled backend exception", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "CipherForge backend running"}


@app.websocket("/ws/progress")
async def progress_websocket(websocket: WebSocket) -> None:
    await progress_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        progress_manager.disconnect(websocket)



def _seed_default_users() -> None:
    session_factory = get_session_factory()
    with session_factory() as db:
        _ensure_user(
            db=db,
            username=settings.default_admin_username,
            email="admin@cipherforge.local",
            password=settings.default_admin_password,
            role=UserRole.ADMIN,
        )
        _ensure_user(
            db=db,
            username=settings.default_operator_username,
            email="operator@cipherforge.local",
            password=settings.default_operator_password,
            role=UserRole.OPERATOR,
        )



def _ensure_user(*, db, username: str, email: str, password: str, role: UserRole) -> None:
    existing = db.scalar(select(User).where(User.username == username))
    if existing is None:
        existing = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        db.add(existing)
    else:
        existing.email = existing.email or email
        existing.role = role
        existing.password_hash = hash_password(password)
    db.commit()
