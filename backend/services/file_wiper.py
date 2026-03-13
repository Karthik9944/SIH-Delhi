from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

from wipe_engine_service.file_wipe_executor import FileWipeExecutor
from wipe_engine_service.folder_wipe_manager import FolderWipeManager
from wipe_engine_service.folder_wipe_service import FolderWipeService


class FileWiperService:
    def __init__(self) -> None:
        self.logger = logging.getLogger("cipherforge.backend.file_wiper")
        self._file_executor = FileWipeExecutor()
        self._folder_service = FolderWipeService(file_wipe_executor=self._file_executor)
        self._folder_manager = FolderWipeManager(folder_wipe_service=self._folder_service)

    def wipe_file(self, path: str, method: str) -> dict[str, Any]:
        result = self._file_executor.secure_delete(path, method, cleanup_free_space=False)
        normalized_status = "completed" if bool(result.get("verified")) else str(result.get("status", "failed"))
        return {
            **result,
            "status": normalized_status,
        }

    def wipe_folder(self, path: str, method: str | None = None) -> dict[str, Any]:
        return self._folder_service.wipe_folder(path, method)

    def start_folder_wipe(self, path: str, method: str | None = None):
        return self._folder_manager.start_wipe(SimpleNamespace(path=path, method=method))

    def get_folder_wipe_status(self, job_id: str):
        return self._folder_manager.get_status(job_id)
