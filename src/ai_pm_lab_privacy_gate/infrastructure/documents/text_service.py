from __future__ import annotations

from pathlib import Path

from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, PageContent, ProtectionResult


class TextDocumentService:
    """Read and write UTF text/CSV files through the same local protection pipeline."""

    SUPPORTED_SUFFIXES = {".txt", ".csv"}

    def extract(self, path: str | Path) -> AnalysisDocument:
        source = self._validated_source(path)
        raw = source.read_bytes()
        text = self._decode(raw)
        kind = source.suffix.lower().lstrip(".")
        location = "CSV file" if kind == "csv" else "Text file"
        return AnalysisDocument(
            source_kind=kind,
            source_path=source,
            pages=(PageContent(page_number=1, text=text, location=location),),
        )

    def write_protected(
        self,
        source_document: AnalysisDocument,
        result: ProtectionResult,
        path: str | Path,
    ) -> Path:
        if source_document.source_kind not in {"txt", "text", "csv"}:
            raise ValueError("A text or CSV source document is required.")
        suffix = ".csv" if source_document.source_kind == "csv" else ".txt"
        destination = Path(path)
        if destination.suffix.lower() != suffix:
            destination = destination.with_suffix(suffix)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source_document.source_kind == "csv":
            # The extracted CSV text already contains the source file's actual
            # line endings. Writing bytes avoids Windows text-mode newline
            # translation turning an existing CRLF into CRCRLF.
            destination.write_bytes(result.combined_text.encode("utf-8"))
        else:
            destination.write_text(result.combined_text, encoding="utf-8")
        return destination

    @classmethod
    def _validated_source(cls, path: str | Path) -> Path:
        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(source)
        if source.suffix.lower() not in cls.SUPPORTED_SUFFIXES:
            raise ValueError("Supported text formats are .txt and .csv.")
        return source

    @staticmethod
    def _decode(raw: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "utf-16"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")
