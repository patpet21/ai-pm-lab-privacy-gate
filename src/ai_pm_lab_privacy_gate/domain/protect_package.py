from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ProtectSource:
    """One independent source participating in a Protect session.

    A source is either in-memory text or a local file. Connector-specific UI
    state is deliberately not part of this model so Gmail, Drive, uploads and
    future sources can share the same contract.
    """

    key: str
    label: str
    source_type: str
    text: str = ""
    path: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("ProtectSource.key is required")
        if not self.label.strip():
            raise ValueError("ProtectSource.label is required")
        if self.source_type not in {"text", "file"}:
            raise ValueError("ProtectSource.source_type must be 'text' or 'file'")
        if self.source_type == "text" and not self.text.strip():
            raise ValueError("Text ProtectSource requires text")
        if self.source_type == "file" and not self.path.strip():
            raise ValueError("File ProtectSource requires a path")

    @classmethod
    def text_source(
        cls,
        *,
        key: str,
        label: str,
        text: str,
        metadata: Mapping[str, object] | None = None,
    ) -> "ProtectSource":
        return cls(
            key=key,
            label=label,
            source_type="text",
            text=text,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def file_source(
        cls,
        *,
        key: str,
        label: str,
        path: str | Path,
        metadata: Mapping[str, object] | None = None,
    ) -> "ProtectSource":
        return cls(
            key=key,
            label=label,
            source_type="file",
            path=str(path),
            metadata=dict(metadata or {}),
        )


@dataclass(frozen=True, slots=True)
class ProtectPackage:
    """Atomic handoff of one or more independent sources into Protect."""

    origin: str
    label: str
    sources: tuple[ProtectSource, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.origin.strip():
            raise ValueError("ProtectPackage.origin is required")
        if not self.sources:
            raise ValueError("ProtectPackage requires at least one source")
        keys = [source.key for source in self.sources]
        if len(keys) != len(set(keys)):
            raise ValueError("ProtectPackage source keys must be unique")

    @property
    def source_count(self) -> int:
        return len(self.sources)

    @property
    def file_count(self) -> int:
        return sum(source.source_type == "file" for source in self.sources)

    def source(self, key: str) -> ProtectSource | None:
        return next((source for source in self.sources if source.key == key), None)
