from __future__ import annotations

"""Gmail -> ProtectPackage bridge shared by manual Protect and Automation.

This module deliberately contains no Qt state, Gmail API calls, protection logic,
or persistence. Gmail browsing/materialization stays in the connector layer; this
adapter only turns already-local Gmail components into the same generic
``ProtectPackage`` contract used by the ProtectSession engine.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from ai_pm_lab_privacy_gate.domain.protect_package import ProtectPackage, ProtectSource


GMAIL_BODY_KEY = "gmail_body"
GMAIL_ATTACHMENT_PREFIX = "gmail_attachment_"


@dataclass(frozen=True, slots=True)
class GmailProtectAttachment:
    """One already-materialized Gmail attachment ready for local Protect."""

    path: str | Path
    label: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    @property
    def local_path(self) -> Path:
        return Path(self.path)



def build_gmail_protect_package(
    *,
    email_body: str = "",
    attachments: Iterable[GmailProtectAttachment] = (),
    source_metadata: Mapping[str, object] | None = None,
    package_label: str = "",
) -> ProtectPackage | None:
    """Build a generic ProtectPackage from local Gmail components.

    The email body remains an in-memory text source. Attachments must already be
    materialized by the Gmail connector into PrivacyGate's managed local
    workspace. No message body or attachment content is copied into package
    metadata, which keeps this object safe to use as the bridge toward the future
    Automation runner.
    """

    metadata = dict(source_metadata or {})
    provider = str(metadata.get("provider") or "gmail").strip().lower()
    if provider != "gmail":
        raise ValueError("Gmail Protect adapter requires gmail provenance.")

    sources: list[ProtectSource] = []
    body = str(email_body or "").strip()
    if body:
        body_metadata = dict(metadata)
        body_metadata.update(
            {
                "provider": "gmail",
                "origin": "gmail",
                "component_kind": "body",
                "source_kind": "text",
            }
        )
        sources.append(
            ProtectSource.text_source(
                key=GMAIL_BODY_KEY,
                label="Email body",
                text=body,
                metadata=body_metadata,
            )
        )

    for index, attachment in enumerate(tuple(attachments), start=1):
        path = attachment.local_path
        if not str(path).strip():
            continue
        attachment_metadata = dict(metadata)
        attachment_metadata.update(dict(attachment.metadata or {}))
        attachment_metadata.update(
            {
                "provider": "gmail",
                "origin": "gmail",
                "component_kind": "attachment",
                "source_kind": "file",
            }
        )
        label = str(attachment.label or "").strip() or path.name or f"Attachment {index}"
        sources.append(
            ProtectSource.file_source(
                key=f"{GMAIL_ATTACHMENT_PREFIX}{index}",
                label=label,
                path=path,
                metadata=attachment_metadata,
            )
        )

    if not sources:
        return None

    label = str(package_label or "").strip()
    if not label:
        label = str(metadata.get("item_title") or metadata.get("source_name") or "Gmail message").strip()
    package_metadata = {
        "adapter": "gmail_v1",
        "provider": "gmail",
        "package_mode": "gmail_message_package",
        "source_count": len(sources),
    }
    for key in ("account_id", "account_label", "item_id", "item_title"):
        value = metadata.get(key)
        if value not in (None, "", (), [], {}):
            package_metadata[key] = value

    return ProtectPackage(
        origin="gmail",
        label=label or "Gmail message",
        sources=tuple(sources),
        metadata=package_metadata,
    )



def build_gmail_protect_package_from_manifest(
    manifest: Iterable[Mapping[str, object]],
    *,
    source_metadata: Mapping[str, object] | None = None,
    package_label: str = "",
) -> ProtectPackage | None:
    """Compatibility bridge for the current Gmail component UI manifest.

    Keeping this conversion here means the existing manual Gmail UI and the
    Automation runtime can converge on the same package contract without either
    layer learning the other's internal state model.
    """

    body = ""
    attachments: list[GmailProtectAttachment] = []
    for component in tuple(manifest):
        kind = str(component.get("component_kind") or "").strip().lower()
        if kind == "body":
            body = str(component.get("text") or "")
            continue
        if kind != "attachment":
            continue
        path = str(component.get("path") or "").strip()
        if not path:
            continue
        attachments.append(
            GmailProtectAttachment(
                path=path,
                label=str(component.get("label") or "").strip(),
            )
        )

    return build_gmail_protect_package(
        email_body=body,
        attachments=attachments,
        source_metadata=source_metadata,
        package_label=package_label,
    )
