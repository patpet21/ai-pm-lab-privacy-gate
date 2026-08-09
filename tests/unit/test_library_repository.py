from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import Finding
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository


def test_library_round_trip_with_encrypted_mapping(tmp_path) -> None:
    text = "Email jane@example.com"
    service = PrivacyGateService()
    finding = Finding(
        finding_id="email-1",
        entity_type="EMAIL_ADDRESS",
        text="jane@example.com",
        start=6,
        end=22,
        score=1.0,
        page_number=1,
        context=text,
    )
    result = service.protect(service.document_from_text(text), (finding,))
    repository = LibraryRepository(tmp_path)

    saved = repository.save(
        title="Tenant email",
        source_kind="text",
        source_name="Pasted text",
        profile_key="property_management",
        result=result,
        labels=("Tenant",),
    )

    assert repository.get(saved.document_id).protected_text == "Email [[PG_EMAIL_ADDRESS_001]]"
    mappings = repository.get_mappings(saved.document_id)
    assert mappings[0].original_text == "jane@example.com"
    assert b"jane@example.com" not in (tmp_path / "library.db").read_bytes()
