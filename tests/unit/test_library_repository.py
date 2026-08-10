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
    assert repository.list_mcp_documents()[0].document_id == saved.document_id
    assert repository.get_mcp_document(saved.document_id).document_id == saved.document_id
    assert repository.list_mcp_documents()[0].mcp_shared is True
    mappings = repository.get_mappings(saved.document_id)
    assert mappings[0].original_text == "jane@example.com"
    assert b"jane@example.com" not in (tmp_path / "library.db").read_bytes()


def test_library_metadata_trash_and_encrypted_backup_round_trip(tmp_path) -> None:
    service = PrivacyGateService()
    document = service.document_from_text("Tenant Jane Smith")
    finding = Finding(
        finding_id="person-1",
        entity_type="PERSON",
        text="Jane Smith",
        start=7,
        end=17,
        score=1.0,
        page_number=1,
        context="Tenant Jane Smith",
    )
    repository = LibraryRepository(tmp_path / "data")
    saved = repository.save(
        title="Original",
        source_kind="text",
        source_name="Pasted text",
        profile_key="property_management",
        result=service.protect(document, (finding,)),
        labels=("Tenant",),
    )
    repository.set_favorite(saved.document_id, True)
    repository.set_mcp_shared(saved.document_id, True)
    repository.update_metadata(saved.document_id, title="Updated", labels=("Lease", "NYC"))
    backup = repository.create_backup(tmp_path / "library.pgbackup")

    repository.move_to_trash(saved.document_id)
    assert repository.list_documents() == ()
    assert repository.list_documents(include_deleted=True)[0].deleted_at is not None
    repository.restore_from_trash(saved.document_id)
    repository.update_metadata(saved.document_id, title="Changed after backup")

    safety_backup = repository.restore_backup(backup)
    restored = repository.get(saved.document_id)
    assert restored.title == "Updated"
    assert restored.favorite is True
    assert restored.mcp_shared is True
    assert restored.labels == ("Lease", "NYC")
    assert repository.get_mappings(saved.document_id)[0].original_text == "Jane Smith"
    assert safety_backup.exists()
