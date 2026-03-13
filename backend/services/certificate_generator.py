from __future__ import annotations

import logging
from typing import Any

from wipe_engine_service.certificate_generator import CertificateGenerator as LegacyCertificateGenerator

from ..config import get_settings


class CertificateGeneratorService:
    def __init__(self) -> None:
        settings = get_settings()
        self.logger = logging.getLogger("cipherforge.backend.certificate_generator")
        self._generator = LegacyCertificateGenerator(output_dir=settings.certificates_dir)
        self._generator.verification_base_url = settings.public_base_url

    def generate(self, **kwargs) -> dict[str, Any]:
        metadata = self._generator.generate(**kwargs)
        return metadata.model_dump() if hasattr(metadata, "model_dump") else metadata.dict()

    def load(self, certificate_id: str) -> dict[str, Any] | None:
        metadata = self._generator.load(certificate_id)
        if metadata is None:
            return None
        return metadata.model_dump() if hasattr(metadata, "model_dump") else metadata.dict()
