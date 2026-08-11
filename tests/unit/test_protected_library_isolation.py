from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import Finding
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
from ai_pm_lab_privacy_gate.infrastructure.storage.protected_library import ProtectedLibraryRepository


def test_mcp_store_contains_only_protected_copy_and_safe_metadata(tmp_path) -> None:
    source = "Tenant Jane Smith, email jane@example.com"
    findings = (
        Finding("person", "PERSON", "Jane Smith", 7, 17, 1.0, 1, source),
        Finding("email", "EMAIL_ADDRESS", "jane@example.com", 25, 41, 1.0, 1, source),
    )
    service = PrivacyGateService()
    repository = LibraryRepository(tmp_path)
    saved = repository.save(
        title="Jane Smith private lease",
        source_kind="pdf",
        source_name="Jane_Smith_lease.pdf",
        profile_key="property_management",
        result=service.protect(service.document_from_text(source), findings),
        labels=("Jane Smith",),
    )

    protected_store = ProtectedLibraryRepository(tmp_path / "Protected")
    exposed = protected_store.get_mcp_document(saved.document_id)
    database_bytes = protected_store.db_path.read_bytes()

    assert exposed.title.startswith("Protected document ")
    assert exposed.labels == ()
    assert "Jane Smith" not in exposed.protected_text
    assert "jane@example.com" not in exposed.protected_text
    assert b"Jane Smith" not in database_bytes
    assert b"jane@example.com" not in database_bytes
    assert b"Jane_Smith_lease.pdf" not in database_bytes


def test_withdrawing_from_ai_removes_the_separate_protected_copy(tmp_path) -> None:
    service = PrivacyGateService()
    repository = LibraryRepository(tmp_path)
    saved = repository.save(
        title="Safe test",
        source_kind="text",
        source_name="Pasted text",
        profile_key="property_management",
        result=service.protect(service.document_from_text("No sensitive data"), ()),
    )
    assert repository.protected_library.get_mcp_document(saved.document_id)

    repository.set_mcp_shared(saved.document_id, False)

    try:
        repository.protected_library.get_mcp_document(saved.document_id)
    except KeyError:
        pass
    else:
        raise AssertionError("Withdrawn document remained in the MCP-only store")
