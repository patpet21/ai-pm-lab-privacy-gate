# Local MCP guide

AI PM LAB Privacy Gate includes a local, read-only Model Context Protocol server. It is free to run and does not require an API key, database server, or AI subscription.

## What it can access

The server can read only active protected copies that the user explicitly marks **Share with MCP** in the Local Library. New and existing documents are private by default.

It cannot:

- read encrypted restore mappings;
- reveal original PII;
- restore protected placeholders;
- edit or delete library documents;
- start a cloud connection by itself.

## Connect a local desktop client

1. Open **Library** and select a protected document.
2. Click **Share with MCP** and confirm.
3. Open **Cloud / MCP / Email** and choose **MCP setup**.
4. Click **Copy configuration**.
5. Paste the JSON into a desktop client that supports local stdio MCP and reconnect that client if required.

The installed configuration points to:

```text
AI PM LAB Privacy Gate MCP\AI PM LAB Privacy Gate MCP.exe
```

Available tools:

- `privacy_gate_status`
- `list_protected_documents`
- `search_protected_documents`
- `get_protected_document`

The server also provides the resource template `privacy-gate://documents/{document_id}`.

## Local versus cloud clients

The packaged MCP server uses local stdio: the compatible desktop client launches it only when needed. A cloud-only AI service cannot directly launch a program on the customer's PC. Connecting that type of service later requires an opt-in authenticated remote bridge, which is intentionally outside this local-first build.

The MCP connection itself is free. Any subscription or usage fee charged by the chosen AI provider remains separate from Privacy Gate.
