from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter(tags=["wipe"])


class DeviceWipeRequest(BaseModel):
    device: str = Field(min_length=1)
    method: str = Field(min_length=1)

    @field_validator("device", "method")
    @classmethod
    def _normalize(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized


class FileWipeRequest(BaseModel):
    path: str = Field(min_length=1)
    method: str = Field(min_length=1)

    @field_validator("path", "method")
    @classmethod
    def _normalize(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized


class FolderWipeRequest(BaseModel):
    path: str = Field(min_length=1)
    method: str | None = None

    @field_validator("path")
    @classmethod
    def _normalize_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("path must not be empty")
        return normalized


class WipeJobResponse(BaseModel):
    job_id: str
    engine_job_id: str
    device: str
    wipe_method: str
    status: str
    progress: float
    start_time: str | None = None
    end_time: str | None = None
    certificate_id: str | None = None
    error: str | None = None
    last_message: str | None = None


class FileWipeResponse(BaseModel):
    status: str
    deleted_files: int = 0
    passes: int | None = None
    verified: bool | None = None
    last_message: str | None = None
    stage_logs: list[str] = Field(default_factory=list)
    free_space_cleanup: str | None = None


class FolderWipeStatusResponse(BaseModel):
    job_id: str
    path: str
    method: str
    status: str
    progress: float
    total_files: int
    processed_files: int
    deleted_files: int
    failed_files: int
    current_file: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    last_message: str | None = None
    error: str | None = None


@router.get("/wipe/methods", response_model=list[str])
def get_supported_methods(request: Request) -> list[str]:
    manager = request.app.state.wipe_manager
    return manager.supported_methods()


@router.get("/wipe/jobs", response_model=list[WipeJobResponse])
def list_jobs(
    request: Request,
    db: Session = Depends(get_db),
) -> list[WipeJobResponse]:
    manager = request.app.state.wipe_manager
    jobs = manager.list_jobs(db)
    return [WipeJobResponse.model_validate(manager.serialize_job_payload(job)) for job in jobs]


@router.get("/wipe/status/{job_id}", response_model=WipeJobResponse)
def get_job_status(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> WipeJobResponse:
    manager = request.app.state.wipe_manager
    job = manager.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Wipe job not found: {job_id}")
    return WipeJobResponse.model_validate(manager.serialize_job_payload(job))


@router.post("/wipe/device", response_model=WipeJobResponse, status_code=status.HTTP_202_ACCEPTED)
@router.post("/wipe/start", response_model=WipeJobResponse, status_code=status.HTTP_202_ACCEPTED)
def start_device_wipe(
    payload: DeviceWipeRequest,
    request: Request,
) -> WipeJobResponse:
    manager = request.app.state.wipe_manager
    try:
        job = manager.start_device_wipe(device=payload.device, method=payload.method)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WipeJobResponse.model_validate(manager.serialize_job_payload(job))


@router.post("/wipe/file", response_model=FileWipeResponse)
def wipe_file(payload: FileWipeRequest, request: Request) -> FileWipeResponse:
    file_wiper = request.app.state.file_wiper
    try:
        result = file_wiper.wipe_file(payload.path, payload.method)
    except (ValueError, FileNotFoundError, IsADirectoryError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return FileWipeResponse.model_validate(result)


@router.post("/wipe/folder")
def wipe_folder(payload: FolderWipeRequest, request: Request) -> dict:
    file_wiper = request.app.state.file_wiper
    try:
        return file_wiper.wipe_folder(payload.path, payload.method)
    except (ValueError, FileNotFoundError, NotADirectoryError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/wipe/folder/start", response_model=FolderWipeStatusResponse, status_code=status.HTTP_202_ACCEPTED)
def start_folder_wipe(payload: FolderWipeRequest, request: Request) -> FolderWipeStatusResponse:
    file_wiper = request.app.state.file_wiper
    try:
        job = file_wiper.start_folder_wipe(payload.path, payload.method)
    except (ValueError, FileNotFoundError, NotADirectoryError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    payload_dict = job.model_dump() if hasattr(job, "model_dump") else job.dict()
    return FolderWipeStatusResponse.model_validate(payload_dict)


@router.get("/wipe/folder/status/{job_id}", response_model=FolderWipeStatusResponse)
def get_folder_wipe_status(job_id: str, request: Request) -> FolderWipeStatusResponse:
    file_wiper = request.app.state.file_wiper
    job = file_wiper.get_folder_wipe_status(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Folder wipe job not found: {job_id}")
    payload_dict = job.model_dump() if hasattr(job, "model_dump") else job.dict()
    return FolderWipeStatusResponse.model_validate(payload_dict)
