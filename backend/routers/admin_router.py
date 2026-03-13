from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models.certificate import Certificate
from ..models.wipe_job import User, UserRole, WipeJob, WipeJobStatus
from ..utils.system_utils import create_jwt, hash_password, verify_password

router = APIRouter(tags=["admin"])


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)

    @field_validator("username", "password")
    @classmethod
    def _normalize(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized


class AuthRegisterRequest(BaseModel):
    username: str = Field(min_length=1)
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    role: UserRole = UserRole.OPERATOR

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("username must not be empty")
        return normalized

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("email must be a valid email address")
        return normalized


class AuthResponse(BaseModel):
    token: str
    username: str
    role: UserRole


class StatsResponse(BaseModel):
    devices_wiped: int
    certificates_generated: int
    failed_jobs: int
    active_jobs: int


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: AuthLoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    settings = get_settings()
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    token = create_jwt(
        subject=user.username,
        role=user.role.value,
        secret_key=settings.secret_key,
        expires_minutes=settings.jwt_exp_minutes,
    )
    return AuthResponse(token=token, username=user.username, role=user.role)


@router.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: AuthRegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    settings = get_settings()
    existing_username = db.scalar(select(User).where(User.username == payload.username))
    if existing_username is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is already taken.")

    existing_email = db.scalar(select(User).where(User.email == payload.email))
    if existing_email is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_jwt(
        subject=user.username,
        role=user.role.value,
        secret_key=settings.secret_key,
        expires_minutes=settings.jwt_exp_minutes,
    )
    return AuthResponse(token=token, username=user.username, role=user.role)


@router.get("/admin/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)) -> StatsResponse:
    devices_wiped = len(list(db.scalars(select(WipeJob).where(WipeJob.status == WipeJobStatus.COMPLETED))))
    certificates_generated = len(list(db.scalars(select(Certificate))))
    failed_jobs = len(list(db.scalars(select(WipeJob).where(WipeJob.status == WipeJobStatus.FAILED))))
    active_jobs = len(
        list(
            db.scalars(
                select(WipeJob).where(WipeJob.status.in_([WipeJobStatus.QUEUED, WipeJobStatus.RUNNING]))
            )
        )
    )
    return StatsResponse(
        devices_wiped=devices_wiped,
        certificates_generated=certificates_generated,
        failed_jobs=failed_jobs,
        active_jobs=active_jobs,
    )
