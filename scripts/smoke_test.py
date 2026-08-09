from __future__ import annotations

import argparse
from pathlib import Path

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.profiles import get_profile


SAMPLE = (
    "Tenant Jane Smith lives at 1600 Pennsylvania Avenue NW, Washington, DC. "
    "Email jane.smith@example.com, phone 212-555-5555, SSN 219-09-9999."
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-output", type=Path)
    args = parser.parse_args()
    service = PrivacyGateService()
    document = service.document_from_text(SAMPLE)
    findings = service.analyze(document, get_profile("property_management"))
    result = service.protect(document, findings)
    if not findings or "jane.smith@example.com" in result.combined_text:
        raise RuntimeError("Privacy smoke test failed")
    if args.pdf_output:
        service.save_protected_pdf(result, args.pdf_output)
    print(f"PASS: {len(findings)} findings; protected preview contains no sample email")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
