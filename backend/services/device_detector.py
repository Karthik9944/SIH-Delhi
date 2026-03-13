from __future__ import annotations

import logging
import platform
from typing import Any

from sqlalchemy.orm import Session

from wipe_engine_service.device_detector import DeviceDetector as LegacyDeviceDetector
from wipe_engine_service.filesystem_scanner import FilesystemScanner

from ..models.wipe_job import DeviceLog
from ..utils.system_utils import utcnow


class DeviceDetectorService:
    def __init__(self) -> None:
        self.logger = logging.getLogger("cipherforge.backend.device_detector")
        self._detector = LegacyDeviceDetector()
        self._filesystem_scanner = FilesystemScanner()

    def list_devices(self, db: Session | None = None) -> list[dict[str, Any]]:
        detected = self._detector.list_devices()
        now = utcnow()
        devices: list[dict[str, Any]] = []

        for index, item in enumerate(detected, start=1):
            device_name = self._normalize_device_name(str(item.device))
            serial = str(getattr(item, "serial", "UNKNOWN") or "UNKNOWN").strip() or "UNKNOWN"
            size = str(getattr(item, "size", "0B") or "0B").strip() or "0B"
            device_type = str(getattr(item, "type", "UNKNOWN") or "UNKNOWN").strip() or "UNKNOWN"
            devices.append(
                {
                    "id": index,
                    "device": device_name,
                    "type": device_type,
                    "size": size,
                    "serial": serial,
                    "last_seen_at": now.isoformat(),
                }
            )
            if db is not None:
                db.add(
                    DeviceLog(
                        device=device_name,
                        device_type=device_type,
                        size=size,
                        serial_number=serial,
                        detected_at=now,
                    )
                )

        if db is not None:
            db.commit()

        return devices

    def resolve_device(self, requested_device: str) -> dict[str, Any]:
        normalized_request = self._normalize_device_name(requested_device).upper()
        for item in self._detector.list_devices():
            device_name = self._normalize_device_name(str(item.device))
            if device_name.upper() == normalized_request:
                return {
                    "device": device_name,
                    "type": str(getattr(item, "type", "UNKNOWN") or "UNKNOWN"),
                    "size": str(getattr(item, "size", "0B") or "0B"),
                    "serial": str(getattr(item, "serial", "UNKNOWN") or "UNKNOWN"),
                    "size_bytes": int(getattr(item, "size_bytes", 0) or 0),
                }
        raise ValueError(f"Device '{requested_device}' not found.")

    def list_drives(self) -> list[dict[str, Any]]:
        drives = self._filesystem_scanner.list_logical_drives()
        payload: list[dict[str, Any]] = []
        for item in drives:
            drive = str(item.drive or "").strip()
            if drive and not drive.endswith("\\"):
                drive = f"{drive}\\"
            payload.append(
                {
                    "drive": drive,
                    "type": str(item.type or "Unknown"),
                    "size": str(item.size or "0B"),
                    "label": item.label,
                }
            )
        return payload

    def _normalize_device_name(self, device_name: str) -> str:
        candidate = (device_name or "").strip()
        if not candidate:
            return candidate
        if platform.system().lower() == "linux" and not candidate.startswith("/dev/"):
            return f"/dev/{candidate}"
        return candidate
