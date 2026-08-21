from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, PageContent
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
from ai_pm_lab_privacy_gate.ui.protection_page import _manual_findings_for_text


def test_manual_item_survives_spacing_protection_and_library_save(tmp_path) -> None:
    document = AnalysisDocument(
        source_kind="pdf",
        pages=(
            PageContent(
                page_number=1,
                text="Profile: PROJECT\n   MANAGEMENT | New York",
            ),
        ),
    )

    findings = _manual_findings_for_text(document, "project management", "custom")

    assert len(findings) == 1
    assert findings[0].text == "PROJECT\n   MANAGEMENT"
    assert findings[0].entity_type == "CUSTOM"

    result = PrivacyGateService().protect(document, findings)
    assert "PROJECT" not in result.combined_text
    assert "[[PG_CUSTOM_001]]" in result.combined_text
    assert result.mappings[0].original_text == "PROJECT\n   MANAGEMENT"

    saved = LibraryRepository(tmp_path / "library").save(
        title="Manual item",
        source_kind="pdf",
        source_name="source.pdf",
        profile_key="property_management",
        result=result,
        labels=(),
    )
    assert saved.protected_text == result.combined_text
    assert saved.findings_count == 1
