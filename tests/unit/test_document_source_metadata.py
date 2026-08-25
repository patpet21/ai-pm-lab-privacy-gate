from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import Finding
from ai_pm_lab_privacy_gate.infrastructure.storage.document_source_metadata import (
    DocumentSourceMetadataRepository,
)
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository


def _save_document(repository: LibraryRepository):
    text = "Tenant Jane Smith"
    service = PrivacyGateService()
    finding = Finding(
        finding_id="person-1",
        entity_type="PERSON",
        text="Jane Smith",
        start=7,
        end=17,
        score=1.0,
        page_number=1,
        context=text,
    )
    return repository.save(
        title="Lease review",
        source_kind="docx",
        source_name="Google Drive • account@example.com • Lease.docx",
        profile_key="property_management",
        result=service.protect(service.document_from_text(text), (finding,)),
        labels=("Lease",),
    )


def test_source_metadata_round_trip_and_mcp_isolation(tmp_path) -> None:
    repository = LibraryRepository(tmp_path / "data")
    saved = _save_document(repository)
    metadata_repository = DocumentSourceMetadataRepository(repository.db_path)

    metadata_repository.upsert(
        document_id=saved.document_id,
        provider="google_drive",
        provider_label="Google Drive",
        account_id="account-123",
        account_label="account@example.com",
        item_id="file-456",
        item_title="Lease.docx",
        item_kind="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    metadata = metadata_repository.get(saved.document_id)
    assert metadata is not None
    assert metadata.provider == "google_drive"
    assert metadata.provider_label == "Google Drive"
    assert metadata.account_id == "account-123"
    assert metadata.account_label == "account@example.com"
    assert metadata.item_id == "file-456"
    assert metadata.item_title == "Lease.docx"

    indexed = metadata_repository.list_for_documents([saved.document_id])
    assert indexed[saved.document_id] == metadata

    # Provenance remains in the local Library database and does not alter the
    # physically isolated protected copy used by MCP.
    mcp_document = repository.get_mcp_document(saved.document_id)
    assert mcp_document.document_id == saved.document_id
    assert mcp_document.protected_text == saved.protected_text


def test_source_metadata_survives_backup_and_cascades_on_delete(tmp_path) -> None:
    repository = LibraryRepository(tmp_path / "data")
    saved = _save_document(repository)
    metadata_repository = DocumentSourceMetadataRepository(repository.db_path)

    metadata_repository.upsert(
        document_id=saved.document_id,
        provider="gmail",
        provider_label="Gmail",
        account_id="gmail-account-1",
        account_label="first@example.com",
        item_id="message-1",
        item_title="Lease question",
        item_kind="email",
    )
    backup = repository.create_backup(tmp_path / "library.pgbackup")

    metadata_repository.upsert(
        document_id=saved.document_id,
        provider="gmail",
        provider_label="Gmail",
        account_id="gmail-account-2",
        account_label="second@example.com",
        item_id="message-2",
        item_title="Changed after backup",
        item_kind="email",
    )

    repository.restore_backup(backup)
    metadata_repository = DocumentSourceMetadataRepository(repository.db_path)
    restored = metadata_repository.get(saved.document_id)
    assert restored is not None
    assert restored.account_id == "gmail-account-1"
    assert restored.account_label == "first@example.com"
    assert restored.item_id == "message-1"

    repository.delete_permanently(saved.document_id)
    assert metadata_repository.get(saved.document_id) is None
