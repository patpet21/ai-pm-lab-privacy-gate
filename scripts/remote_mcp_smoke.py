from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path

from mcp import Client
import requests
import truststore


# AVG and other endpoint-security products may issue their own locally trusted
# TLS certificates. Use the Windows trust store for this customer-machine smoke
# test; never disable certificate verification.
truststore.inject_into_ssl()

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import Finding
from ai_pm_lab_privacy_gate.infrastructure.mcp.identity import ConnectionIdentityStore
from ai_pm_lab_privacy_gate.infrastructure.mcp.remote import RemoteMcpManager
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository


def create_protected_fixture(data_dir: Path) -> str:
    source = "Tenant Jane Smith, email jane@example.com"
    findings = (
        Finding("person", "PERSON", "Jane Smith", 7, 17, 1.0, 1, source),
        Finding("email", "EMAIL_ADDRESS", "jane@example.com", 25, 41, 1.0, 1, source),
    )
    service = PrivacyGateService()
    repository = LibraryRepository(data_dir)
    saved = repository.save(
        title="Remote MCP protected test",
        source_kind="text",
        source_name="Synthetic smoke test",
        profile_key="property_management",
        result=service.protect(service.document_from_text(source), findings),
    )
    return saved.document_id


async def exercise(url: str, expected_document_id: str) -> None:
    async with Client(url, read_timeout_seconds=30) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        assert "get_protected_document" in names
        status = await client.call_tool("privacy_gate_status")
        assert status.structured_content["can_access_original_pii"] is False
        documents = await client.call_tool("list_protected_documents")
        ids = {item["document_id"] for item in documents.structured_content["documents"]}
        assert expected_document_id in ids
        document = await client.call_tool(
            "get_protected_document", {"document_id": expected_document_id}
        )
        protected = document.structured_content["protected_text"]
        assert "Jane Smith" not in protected
        assert "jane@example.com" not in protected
        assert "[[PG_PERSON_001]]" in protected


def probe_initialize(url: str) -> None:
    response = requests.post(
        url,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "privacy-gate-smoke", "version": "1"},
            },
        },
        headers={"Accept": "application/json, text/event-stream"},
        timeout=30,
    )
    print(f"HTTP probe {response.status_code}: {response.text[:500]}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="privacy-gate-remote-smoke-") as temporary:
        data_dir = Path(temporary)
        os.environ["PRIVACY_GATE_DATA_DIR"] = str(data_dir)
        document_id = create_protected_fixture(data_dir)
        manager = RemoteMcpManager(ConnectionIdentityStore(data_dir))
        try:
            manager.start()
            deadline = time.monotonic() + 65
            while time.monotonic() < deadline and manager.status.state == "starting":
                time.sleep(0.25)
            status = manager.status
            if status.state != "online":
                raise RuntimeError(status.error or f"Unexpected state: {status.state}")
            identity = manager.identity_store.load_or_create()
            local_url = f"http://127.0.0.1:{status.local_port}{identity.mcp_path}"
            print(f"Local HTTP MCP URL: {local_url}")
            probe_initialize(local_url)
            asyncio.run(exercise(local_url, document_id))
            print("Local HTTP MCP smoke test passed.")
            print(f"Remote MCP URL: {status.public_url}")
            probe_initialize(status.public_url)
            asyncio.run(exercise(status.public_url, document_id))
            print("Remote MCP HTTPS smoke test passed.")
        finally:
            manager.stop()


if __name__ == "__main__":
    main()
