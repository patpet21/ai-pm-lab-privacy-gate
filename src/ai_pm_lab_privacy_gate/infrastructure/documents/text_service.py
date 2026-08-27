from __future__ import annotations

from pathlib import Path

from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, PageContent, ProtectionResult


class TextDocumentService:
    """Read and write UTF text files through the same local protection pipeline."""

    SUPPORTED_SUFFIXES = {".txt"}

    def extract(self, path: str | Path) -> AnalysisDocument:
        source = self._validated_source(path)
        raw = source.read_bytes()
        text = self._decode(raw)
        return AnalysisDocument(
            source_kind="txt",
            source_path=source,
            pages=(PageContent(page_number=1, text=text, location="Text file"),),
        )

    def write_protected(
        self,
        source_document: AnalysisDocument,
        result: ProtectionResult,
        path: str | Path,
    ) -> Path:
        if source_document.source_kind not in {"txt", "text"}:
            raise ValueError("A text source document is required.")
        destination = Path(path)
        if destination.suffix.lower() != ".txt":
            destination = destination.with_suffix(".txt")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(result.combined_text, encoding="utf-8")
        return destination

    @classmethod
    def _validated_source(cls, path: str | Path) -> Path:
        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(source)
        if source.suffix.lower() not in cls.SUPPORTED_SUFFIXES:
            raise ValueError("Supported text format is .txt.")
        return source

    @staticmethod
    def _decode(raw: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "utf-16"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")
