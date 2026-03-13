from __future__ import annotations

from wipe_engine_service.forensic_verifier import ForensicVerifier as LegacyForensicVerifier


class ForensicVerifierService:
    def __init__(self) -> None:
        self._verifier = LegacyForensicVerifier()

    def verify(self, device: str) -> dict[str, object]:
        return self._verifier.verify(device)
