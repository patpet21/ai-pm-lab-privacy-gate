from __future__ import annotations

"""UI-independent save path for a completed generic Protect session."""

from dataclasses import dataclass
from typing import Iterable

from ai_pm_lab_privacy_gate.application.protect_session_service import ProtectSessionResult
from ai_pm_lab_privacy_gate.domain.models import LibraryDocument
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository


@dataclass(frozen=True, slots=True)
class ProtectedSessionSave:
    documents: tuple[LibraryDocument, ...]

    @property
    def primary(self) -> LibraryDocument | None:
        return self.documents[0] if self.documents else None


class ProtectCompletionService:
    """Persist protected session results through the existing local Library."""

    def __init__(self, library: LibraryRepository) -> None:
        self.library = library

    def save_session(
        self,
        result: ProtectSessionResult,
        *,
        title: str,
        profile_key: str,
        labels: Iterable[str] = (),
    ) -> ProtectedSessionSave:
        clean_title = str(title or "").strip() or result.analysis.package.label or "Protected document"
        clean_labels = tuple(str(label).strip() for label in labels if str(label).strip())
        multi_source = result.source_count > 1
        saved: list[LibraryDocument] = []

        for source_result in result.sources:
            source = source_result.analysis.source
            document = source_result.analysis.document
            item_title = (
                f"{clean_title} — {source.label}"
                if multi_source
                else clean_title
            )
            saved.append(
                self.library.save(
                    title=item_title,
                    source_kind=document.source_kind,
                    source_name=source.label,
                    profile_key=profile_key,
                    result=source_result.result,
                    labels=clean_labels,
                )
            )

        return ProtectedSessionSave(tuple(saved))
