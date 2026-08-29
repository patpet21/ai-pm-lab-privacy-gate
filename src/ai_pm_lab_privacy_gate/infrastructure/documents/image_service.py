from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, PageContent, ProtectionResult
from ai_pm_lab_privacy_gate.domain.ocr import OcrPageLayout, OcrTextRegion, Polygon
from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService
from ai_pm_lab_privacy_gate.infrastructure.ocr.base import OcrEngine, OcrLineObservation
from ai_pm_lab_privacy_gate.infrastructure.ocr.rapidocr_engine import RapidOcrEngine


class ImageDocumentService:
    """Extract printed text + geometry and produce truly redacted raster copies."""

    SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg"}

    def __init__(self, ocr_engine: OcrEngine | None = None) -> None:
        self.ocr = ocr_engine or RapidOcrEngine()

    def extract(self, path: str | Path) -> AnalysisDocument:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        if source.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            raise ValueError("Image OCR supports PNG, JPG and JPEG files in this build.")

        with Image.open(source) as opened:
            # Normalize camera orientation before OCR so every returned coordinate
            # uses the same pixel space later used by the redaction writer.
            image = ImageOps.exif_transpose(opened).convert("RGB")
        lines = self.ocr.read(image)
        text, regions = self._layout_text(lines)
        if not text.strip():
            raise ValueError(
                "No readable printed text was found in this image. Try a clearer screenshot or photo, "
                "better lighting, less perspective distortion, or a higher-resolution copy. "
                "Handwriting is not supported in this image OCR version."
            )
        layout = OcrPageLayout(
            page_number=1,
            width=image.width,
            height=image.height,
            regions=regions,
        )
        return AnalysisDocument(
            source_kind="image",
            source_path=source,
            pages=(PageContent(page_number=1, text=text, location="image"),),
            ocr_pages=(layout,),
        )

    @staticmethod
    def _layout_text(
        lines: tuple[OcrLineObservation, ...],
    ) -> tuple[str, tuple[OcrTextRegion, ...]]:
        text_parts: list[str] = []
        regions: list[OcrTextRegion] = []
        cursor = 0
        for line_index, line in enumerate(lines):
            if line_index:
                text_parts.append("\n")
                cursor += 1
            line_text = line.text.strip()
            if not line_text:
                continue
            line_start = cursor
            text_parts.append(line_text)
            cursor += len(line_text)
            line_end = cursor
            if line.polygon:
                regions.append(
                    OcrTextRegion(
                        text=line_text,
                        start=line_start,
                        end=line_end,
                        confidence=line.confidence,
                        polygon=line.polygon,
                        level="line",
                        line_index=line_index,
                    )
                )

            search_cursor = 0
            for word in line.words:
                local_start = ImageDocumentService._find_fragment(
                    line_text, word.text, search_cursor
                )
                if local_start < 0:
                    continue
                local_end = local_start + len(word.text)
                search_cursor = local_end
                if word.polygon:
                    regions.append(
                        OcrTextRegion(
                            text=line_text[local_start:local_end],
                            start=line_start + local_start,
                            end=line_start + local_end,
                            confidence=word.confidence,
                            polygon=word.polygon,
                            level="word",
                            line_index=line_index,
                        )
                    )
        return "".join(text_parts), tuple(regions)

    @staticmethod
    def _find_fragment(text: str, fragment: str, start: int) -> int:
        value = fragment.strip()
        if not value:
            return -1
        exact = text.find(value, start)
        if exact >= 0:
            return exact
        return text.lower().find(value.lower(), start)

    def write_protected(
        self,
        source_document: AnalysisDocument,
        result: ProtectionResult,
        path: str | Path,
    ) -> Path:
        if source_document.source_path is None:
            raise ValueError("An image source path is required.")
        if not source_document.ocr_pages:
            raise ValueError("OCR layout is required to safely redact an image.")

        destination = Path(path)
        suffix = destination.suffix.lower()
        if suffix not in self.SUPPORTED_SUFFIXES:
            source_suffix = source_document.source_path.suffix.lower()
            if source_suffix not in self.SUPPORTED_SUFFIXES:
                source_suffix = ".png"
            destination = destination.with_suffix(source_suffix)
        destination.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(source_document.source_path) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
        layout = source_document.ocr_pages[0]
        if (layout.width, layout.height) != image.size:
            raise ValueError("Image dimensions changed after OCR; protection was stopped for safety.")

        span_by_finding = {span.finding_id: span for span in result.protected_spans}
        draw = ImageDraw.Draw(image)
        unresolved: list[str] = []
        for finding in result.applied_findings:
            span = span_by_finding.get(finding.finding_id)
            regions = layout.regions_for_range(finding.start, finding.end)
            if span is None or not regions:
                unresolved.append(finding.text)
                continue
            box = self._union_box(tuple(region.polygon for region in regions), image.size)
            if box is None:
                unresolved.append(finding.text)
                continue
            color = PdfDocumentService.ENTITY_COLORS.get(finding.entity_type, "#E7E9ED")
            draw.rectangle(box, fill=color, outline="#66788A", width=1)
            label = PdfDocumentService._compact_replacement(
                span.replacement_text, finding.entity_type
            )
            PdfDocumentService._draw_fitted_text(draw, box, label)

        if unresolved:
            raise ValueError(
                "Unable to safely map every selected OCR value back to image pixels: "
                + "; ".join(unresolved[:8])
            )

        output_suffix = destination.suffix.lower()
        image_format = "PNG" if output_suffix == ".png" else "JPEG"
        temporary = destination.with_name(
            f".{destination.stem}.building-{os.getpid()}{output_suffix}"
        )
        temporary.unlink(missing_ok=True)
        # Saving a freshly converted raster intentionally drops EXIF and other
        # source metadata that could itself leak location/device information.
        save_kwargs = {"format": image_format}
        if image_format == "JPEG":
            save_kwargs.update({"quality": 95, "subsampling": 0})
        else:
            save_kwargs.update({"optimize": True})
        image.save(temporary, **save_kwargs)
        os.replace(temporary, destination)
        return destination

    @staticmethod
    def _union_box(
        polygons: tuple[Polygon, ...], image_size: tuple[int, int]
    ) -> tuple[int, int, int, int] | None:
        points = [point for polygon in polygons for point in polygon]
        if not points:
            return None
        width, height = image_size
        left = max(0, int(min(point[0] for point in points)) - 3)
        top = max(0, int(min(point[1] for point in points)) - 3)
        right = min(width, int(max(point[0] for point in points)) + 3)
        bottom = min(height, int(max(point[1] for point in points)) + 3)
        if right <= left or bottom <= top:
            return None
        return left, top, right, bottom
