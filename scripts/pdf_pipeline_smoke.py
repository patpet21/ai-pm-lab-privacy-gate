from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.profiles import get_profile


def main() -> int:
    temp_dir = Path("tmp/pdfs")
    temp_dir.mkdir(parents=True, exist_ok=True)
    source = temp_dir / "privacy_gate_source.pdf"
    protected = temp_dir / "privacy_gate_protected.pdf"
    c = canvas.Canvas(str(source), pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(72, 720, "Property Management Contact Sheet")
    c.drawString(72, 690, "Tenant: Jane Smith")
    c.drawString(72, 670, "Email: jane.smith@example.com")
    c.drawString(72, 650, "Phone: 212-555-5555")
    c.drawString(72, 630, "Social Security Number: 219-09-9999")
    c.save()

    service = PrivacyGateService()
    document = service.document_from_pdf(source)
    findings = service.analyze(document, get_profile("property_management"))
    result = service.protect(document, findings)
    service.save_protected_pdf(result, protected)

    output_text = "\n".join(page.extract_text() or "" for page in PdfReader(str(protected)).pages)
    forbidden = ["Jane Smith", "jane.smith@example.com", "212-555-5555", "219-09-9999"]
    leaked = [value for value in forbidden if value in output_text]
    if leaked:
        raise RuntimeError(f"Protected PDF still contains sample PII: {leaked}")
    if "[[PG_EMAIL_ADDRESS_" not in output_text or "[[PG_US_SSN_" not in output_text:
        raise RuntimeError("Protected PDF is missing expected placeholders")
    print(f"PDF_OK {protected.resolve()} {len(findings)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
