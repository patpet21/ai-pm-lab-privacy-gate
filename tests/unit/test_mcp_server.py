import asyncio

from mcp import Client

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import Finding
from ai_pm_lab_privacy_gate.infrastructure.mcp.server import create_mcp_server
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository


def _save_document(repository: LibraryRepository):
    source = "Tenant Jane Smith, email jane@example.com"
    findings = (
        Finding("person", "PERSON", "Jane Smith", 7, 17, 1.0, 1, source),
        Finding("email", "EMAIL_ADDRESS", "jane@example.com", 25, 41, 1.0, 1, source),
    )
    service = PrivacyGateService()
    return repository.save(
        title="Protected tenant note",
        source_kind="text",
        source_name="Pasted text",
        profile_key="property_management",
        result=service.protect(service.document_from_text(source), findings),
        labels=("lease",),
    )


def test_mcp_exposes_only_explicitly_shared_protected_text(tmp_path) -> None:
    repository = LibraryRepository(tmp_path)
    saved = _save_document(repository)
    server = create_mcp_server(repository)

    async def exercise_server() -> None:
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {tool.name for tool in tools.tools}
            assert {
                "privacy_gate_status",
                "list_protected_documents",
                "search_protected_documents",
                "get_protected_document",
            } <= names

            hidden = await client.call_tool("list_protected_documents")
            assert hidden.structured_content["count"] == 0

            repository.set_mcp_shared(saved.document_id, True)
            visible = await client.call_tool("list_protected_documents")
            assert visible.structured_content["count"] == 1

            result = await client.call_tool(
                "get_protected_document",
                {"document_id": saved.document_id},
            )
            protected_text = result.structured_content["protected_text"]
            assert "[[PG_PERSON_001]]" in protected_text
            assert "[[PG_EMAIL_ADDRESS_001]]" in protected_text
            assert "Jane Smith" not in protected_text
            assert "jane@example.com" not in protected_text

            repository.set_mcp_shared(saved.document_id, False)
            blocked = await client.call_tool(
                "get_protected_document",
                {"document_id": saved.document_id},
            )
            assert blocked.is_error is True

    asyncio.run(exercise_server())


def test_mcp_search_never_reads_restore_mapping(tmp_path) -> None:
    repository = LibraryRepository(tmp_path)
    saved = _save_document(repository)
    repository.set_mcp_shared(saved.document_id, True)

    async def exercise_server() -> None:
        async with Client(create_mcp_server(repository)) as client:
            result = await client.call_tool(
                "search_protected_documents",
                {"query": "Tenant"},
            )
            serialized = str(result.structured_content)
            assert "Jane Smith" not in serialized
            assert "jane@example.com" not in serialized

    asyncio.run(exercise_server())
