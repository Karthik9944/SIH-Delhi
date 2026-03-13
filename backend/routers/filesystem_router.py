from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from wipe_engine_service.folder_browser_api import FolderBrowser

router = APIRouter(tags=["filesystem"])
folder_browser = FolderBrowser()


class DriveResponse(BaseModel):
    drive: str
    type: str
    size: str
    label: str | None = None


class FileMetadataResponse(BaseModel):
    name: str
    size: str
    size_bytes: int = Field(ge=0)


class FilesystemBrowseResponse(BaseModel):
    path: str
    folders: list[str]
    files: list[FileMetadataResponse]


@router.get("/drives", response_model=list[DriveResponse])
def list_drives(request: Request) -> list[DriveResponse]:
    detector = request.app.state.device_detector
    return [DriveResponse.model_validate(item) for item in detector.list_drives()]


@router.get("/filesystem", response_model=FilesystemBrowseResponse)
def browse_filesystem(path: str = Query(..., min_length=1)) -> FilesystemBrowseResponse:
    try:
        response = folder_browser.browse(path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to browse filesystem: {exc}",
        ) from exc
    return FilesystemBrowseResponse.model_validate(response.model_dump())
