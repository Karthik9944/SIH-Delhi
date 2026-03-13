from __future__ import annotations

from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.certificate import Certificate

router = APIRouter(tags=["certificates"])


class CertificateSummaryResponse(BaseModel):
    id: str
    job_id: str
    method: str
    verification_status: str
    recovered_files: int
    timestamp: str


class CertificateDetailResponse(CertificateSummaryResponse):
    device: str
    device_serial_number: str
    device_type: str
    overwrite_passes: int
    sha256_hash: str
    verification_url: str
    json_path: str
    pdf_path: str
    raw_payload: str | None = None


class VerificationResponse(BaseModel):
    device: str
    wipe_method: str
    timestamp: str
    verification_status: str


@router.get("/certificates", response_model=list[CertificateSummaryResponse])
def list_certificates(
    request: Request,
    db: Session = Depends(get_db),
) -> list[CertificateSummaryResponse]:
    manager = request.app.state.wipe_manager
    certificates = list(db.scalars(select(Certificate).order_by(desc(Certificate.timestamp))))
    return [CertificateSummaryResponse.model_validate(manager.serialize_certificate_summary(cert)) for cert in certificates]


@router.get("/certificate/{certificate_id}", response_model=CertificateDetailResponse)
def get_certificate(
    certificate_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> CertificateDetailResponse:
    manager = request.app.state.wipe_manager
    certificate = manager.get_certificate_by_id(db, certificate_id) or manager.get_certificate_by_job_id(db, certificate_id)
    if certificate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Certificate not found: {certificate_id}")
    return CertificateDetailResponse.model_validate(manager.serialize_certificate_detail(certificate))


@router.get("/certificate/download/{job_id}")
def download_certificate_pdf(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> FileResponse:
    manager = request.app.state.wipe_manager
    certificate = manager.get_certificate_by_job_id(db, job_id) or manager.get_certificate_by_id(db, job_id)
    if certificate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Certificate not found for job: {job_id}")
    file_path = manager.certificate_file_path(certificate, kind="pdf")
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate PDF file not found.")
    return FileResponse(path=file_path, media_type="application/pdf", filename=file_path.name)


@router.get("/certificate/download-json/{job_id}")
def download_certificate_json(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> FileResponse:
    manager = request.app.state.wipe_manager
    certificate = manager.get_certificate_by_job_id(db, job_id) or manager.get_certificate_by_id(db, job_id)
    if certificate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Certificate not found for job: {job_id}")
    file_path = manager.certificate_file_path(certificate, kind="json")
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate JSON file not found.")
    return FileResponse(path=file_path, media_type="application/json", filename=file_path.name)


@router.get("/verify/{certificate_id}", response_model=VerificationResponse)
def verify_certificate(
    certificate_id: str,
    request: Request,
    view: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    manager = request.app.state.wipe_manager
    certificate = manager.get_certificate_by_id(db, certificate_id) or manager.get_certificate_by_job_id(db, certificate_id)
    if certificate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Certificate not found: {certificate_id}")

    payload = VerificationResponse(
        device=certificate.device,
        wipe_method=certificate.wipe_method,
        timestamp=certificate.timestamp.isoformat(),
        verification_status=certificate.verification_status,
    )

    accepts_html = "text/html" in request.headers.get("accept", "").lower()
    if view == "html" or (accepts_html and view != "json"):
        return HTMLResponse(_render_verification_page(certificate.id, payload))
    return payload



def _render_verification_page(certificate_id: str, payload: VerificationResponse) -> str:
    is_authentic = payload.verification_status.upper() == "PASSED"
    status_class = "ok" if is_authentic else "bad"
    authenticity_text = "Certificate is authentic" if is_authentic else "Certificate failed verification"
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>CipherForge Verification</title>
  <style>
    body {{
      margin: 0;
      font-family: 'Segoe UI', Tahoma, sans-serif;
      background: linear-gradient(135deg, #e6f4f7 0%, #f7fbfc 100%);
      color: #1c2f3f;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
    }}
    .card {{
      width: min(720px, 100%);
      background: #ffffff;
      border: 1px solid #dbe5ed;
      border-radius: 16px;
      box-shadow: 0 10px 30px rgba(15, 40, 64, 0.12);
      padding: 24px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 1.5rem; }}
    .meta {{ color: #607387; margin-bottom: 20px; font-size: 0.92rem; }}
    .grid {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }}
    .item {{
      border: 1px solid #e3eaf1;
      border-radius: 10px;
      padding: 12px;
      background: #fbfdff;
    }}
    .label {{ font-size: 0.82rem; color: #607387; }}
    .value {{ margin-top: 4px; font-size: 1rem; font-weight: 600; }}
    .ok {{ color: #0a7f37; }}
    .bad {{ color: #b42318; }}
    .banner {{
      margin: 0 0 18px;
      padding: 10px 12px;
      border-radius: 10px;
      font-weight: 600;
      border: 1px solid #e3eaf1;
      background: #f8fbff;
    }}
  </style>
</head>
<body>
  <section class=\"card\">
    <h1>Certificate Verification</h1>
    <p class=\"meta\">Certificate ID: {escape(certificate_id)}</p>
    <p class=\"banner {status_class}\">{escape(authenticity_text)}</p>
    <div class=\"grid\">
      <div class=\"item\">
        <div class=\"label\">Device</div>
        <div class=\"value\">{escape(payload.device)}</div>
      </div>
      <div class=\"item\">
        <div class=\"label\">Wipe Method</div>
        <div class=\"value\">{escape(payload.wipe_method)}</div>
      </div>
      <div class=\"item\">
        <div class=\"label\">Timestamp</div>
        <div class=\"value\">{escape(payload.timestamp)}</div>
      </div>
      <div class=\"item\">
        <div class=\"label\">Verification Status</div>
        <div class=\"value {status_class}\">{escape(payload.verification_status)}</div>
      </div>
    </div>
  </section>
</body>
</html>"""
