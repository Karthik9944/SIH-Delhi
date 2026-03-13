from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import WebSocket
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from wipe_engine_service.models import WipeMethod
from wipe_engine_service.wipe_executor import WipeExecutor

from ..config import AppSettings
from ..models.certificate import Certificate
from ..models.wipe_job import WipeJob, WipeJobStatus
from ..utils.system_utils import utcnow


@dataclass
class MethodDefinition:
    label: str
    engine_method: WipeMethod


class ProgressConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self.logger = logging.getLogger("cipherforge.backend.progress_ws")

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        with self._lock:
            self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        with self._lock:
            self._connections.discard(websocket)

    def publish(self, payload: dict[str, Any]) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(payload), self._loop)

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        message = json.dumps(payload, default=str)
        dead: list[WebSocket] = []
        with self._lock:
            connections = list(self._connections)
        for websocket in connections:
            try:
                await websocket.send_text(message)
            except Exception:
                dead.append(websocket)
        if dead:
            with self._lock:
                for websocket in dead:
                    self._connections.discard(websocket)


class WipeManager:
    METHOD_MAP = {
        "nist": MethodDefinition(label="NIST Clear", engine_method=WipeMethod.NIST),
        "nist clear": MethodDefinition(label="NIST Clear", engine_method=WipeMethod.NIST),
        "dod": MethodDefinition(label="DoD 5220.22-M", engine_method=WipeMethod.DOD),
        "dod 5220.22-m": MethodDefinition(label="DoD 5220.22-M", engine_method=WipeMethod.DOD),
        "gutmann": MethodDefinition(label="Gutmann", engine_method=WipeMethod.GUTMANN),
        "gutmann method": MethodDefinition(label="Gutmann", engine_method=WipeMethod.GUTMANN),
    }

    def __init__(
        self,
        *,
        settings: AppSettings,
        session_factory: sessionmaker[Session],
        device_detector,
        certificate_generator,
        forensic_verifier,
        progress_manager: ProgressConnectionManager,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.device_detector = device_detector
        self.certificate_generator = certificate_generator
        self.forensic_verifier = forensic_verifier
        self.progress_manager = progress_manager
        self.executor = WipeExecutor(dry_run=settings.wipe_engine_dry_run)
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cipherforge-device-wipe")
        self.logger = logging.getLogger("cipherforge.backend.wipe_manager")

    def supported_methods(self) -> list[str]:
        return ["NIST Clear", "DoD 5220.22-M", "Gutmann"]

    def start_device_wipe(self, *, device: str, method: str) -> WipeJob:
        method_definition = self._resolve_method(method)
        device_info = self.device_detector.resolve_device(device)
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        with self.session_factory() as db:
            job = WipeJob(
                id=job_id,
                engine_job_id=job_id,
                device=device_info["device"],
                device_type=device_info["type"],
                device_serial_number=device_info["serial"],
                wipe_method=method_definition.label,
                status=WipeJobStatus.QUEUED,
                progress=0.0,
                last_message="Wipe job queued.",
            )
            db.add(job)
            db.commit()
            db.refresh(job)

        self.progress_manager.publish(self.serialize_job_payload(job))
        self.pool.submit(self._run_device_job, job_id, device_info, method_definition)
        self.logger.info("Queued wipe job %s for %s", job_id, device_info["device"])
        return job

    def list_jobs(self, db: Session) -> list[WipeJob]:
        return list(db.scalars(select(WipeJob).order_by(desc(WipeJob.created_at))))

    def get_job(self, db: Session, job_id: str) -> WipeJob | None:
        return db.get(WipeJob, job_id)

    def get_certificate_by_id(self, db: Session, certificate_id: str) -> Certificate | None:
        return db.get(Certificate, certificate_id)

    def get_certificate_by_job_id(self, db: Session, job_id: str) -> Certificate | None:
        statement = select(Certificate).where(Certificate.job_id == job_id)
        return db.scalar(statement)

    def serialize_job_payload(self, job: WipeJob) -> dict[str, Any]:
        certificate_id = None
        try:
            if getattr(job, "certificate", None) is not None:
                certificate_id = job.certificate.id
        except Exception:
            certificate_id = None
        return {
            "job_id": job.id,
            "engine_job_id": job.engine_job_id,
            "device": job.device,
            "wipe_method": job.wipe_method,
            "status": job.status.value if isinstance(job.status, WipeJobStatus) else str(job.status),
            "progress": round(float(job.progress or 0.0), 2),
            "start_time": job.start_time.isoformat() if job.start_time else None,
            "end_time": job.end_time.isoformat() if job.end_time else None,
            "certificate_id": certificate_id,
            "error": job.error_message,
            "last_message": job.last_message,
        }

    def serialize_certificate_summary(self, certificate: Certificate) -> dict[str, Any]:
        return {
            "id": certificate.id,
            "job_id": certificate.job_id,
            "method": certificate.wipe_method,
            "verification_status": certificate.verification_status,
            "recovered_files": certificate.recovered_files,
            "timestamp": certificate.timestamp.isoformat(),
        }

    def serialize_certificate_detail(self, certificate: Certificate) -> dict[str, Any]:
        return {
            **self.serialize_certificate_summary(certificate),
            "device": certificate.device,
            "device_serial_number": certificate.device_serial_number,
            "device_type": certificate.device_type,
            "overwrite_passes": certificate.overwrite_passes,
            "sha256_hash": certificate.sha256_hash,
            "verification_url": certificate.verification_url,
            "json_path": certificate.json_path,
            "pdf_path": certificate.pdf_path,
            "raw_payload": certificate.raw_payload,
        }

    def _run_device_job(
        self,
        job_id: str,
        device_info: dict[str, Any],
        method_definition: MethodDefinition,
    ) -> None:
        with self.session_factory() as db:
            job = db.get(WipeJob, job_id)
            if job is None:
                return
            job.status = WipeJobStatus.RUNNING
            job.start_time = job.start_time or utcnow()
            job.last_message = "Wipe started."
            db.commit()
            db.refresh(job)
            self.progress_manager.publish(self.serialize_job_payload(job))

        def on_progress(progress: float, message: str) -> None:
            with self.session_factory() as progress_db:
                progress_job = progress_db.get(WipeJob, job_id)
                if progress_job is None:
                    return
                progress_job.status = WipeJobStatus.RUNNING
                progress_job.progress = progress
                progress_job.last_message = message
                progress_db.commit()
                progress_db.refresh(progress_job)
                self.progress_manager.publish(self.serialize_job_payload(progress_job))

        try:
            result = self.executor.wipe(
                target=device_info["device"],
                method=method_definition.engine_method,
                size_hint=int(device_info.get("size_bytes", 0) or 0),
                progress_callback=on_progress,
            )
            forensic_result = self.forensic_verifier.verify(device_info["device"])
            recovered_files = int(forensic_result.get("recovered_files", 0))
            verification_status = str(forensic_result.get("verification", "FAILED"))
            certificate_id = str(uuid.uuid4())
            certificate_meta = self.certificate_generator.generate(
                certificate_id=certificate_id,
                job_id=job_id,
                device=device_info["device"],
                device_serial_number=device_info["serial"],
                device_type=device_info["type"],
                wipe_method=method_definition.engine_method,
                overwrite_passes=int(result["passes_completed"]),
                timestamp=result["end_time"],
                verification_status=verification_status,
                recovered_files=recovered_files,
                bytes_wiped=int(result["bytes_wiped"]),
                execution_seconds=float(result["execution_seconds"]),
            )

            with self.session_factory() as db:
                job = db.get(WipeJob, job_id)
                if job is None:
                    return
                certificate = Certificate(
                    id=str(certificate_meta["id"]),
                    job_id=job.id,
                    device=str(certificate_meta["device"]),
                    device_serial_number=str(certificate_meta["device_serial_number"]),
                    device_type=str(certificate_meta["device_type"]),
                    wipe_method=job.wipe_method,
                    overwrite_passes=int(certificate_meta["overwrite_passes"]),
                    timestamp=certificate_meta["timestamp"],
                    verification_status=str(certificate_meta["verification_status"]),
                    recovered_files=int(certificate_meta["recovered_files"]),
                    sha256_hash=str(certificate_meta["sha256_hash"]),
                    verification_url=str(certificate_meta["verification_url"]),
                    json_path=str(certificate_meta["json_path"]),
                    pdf_path=str(certificate_meta["pdf_path"]),
                    raw_payload=json.dumps(certificate_meta, default=str),
                )
                db.add(certificate)
                job.status = WipeJobStatus.COMPLETED
                job.progress = 100.0
                job.end_time = result["end_time"]
                job.bytes_wiped = int(result["bytes_wiped"])
                job.overwrite_passes = int(result["passes_completed"])
                job.execution_seconds = float(result["execution_seconds"])
                job.verification_status = verification_status
                job.recovered_files = recovered_files
                job.last_message = "Wipe completed successfully."
                db.commit()
                db.refresh(job)
                self.progress_manager.publish(self.serialize_job_payload(job))
        except Exception as exc:
            with self.session_factory() as db:
                job = db.get(WipeJob, job_id)
                if job is None:
                    return
                job.status = WipeJobStatus.FAILED
                job.end_time = utcnow()
                job.error_message = str(exc)
                job.last_message = "Wipe failed."
                db.commit()
                db.refresh(job)
                self.progress_manager.publish(self.serialize_job_payload(job))
            self.logger.exception("Wipe job %s failed", job_id)

    def certificate_file_path(self, certificate: Certificate, *, kind: str) -> Path:
        raw_path = certificate.pdf_path if kind == "pdf" else certificate.json_path
        candidate = Path(raw_path)
        if candidate.is_absolute():
            return candidate
        return Path(__file__).resolve().parents[2] / candidate

    def _resolve_method(self, method: str) -> MethodDefinition:
        key = (method or "").strip().lower()
        if key not in self.METHOD_MAP:
            raise ValueError("Unsupported method. Use: NIST Clear, DoD 5220.22-M, or Gutmann.")
        return self.METHOD_MAP[key]
