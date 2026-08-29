from __future__ import annotations

from dataclasses import dataclass, field


Point = tuple[float, float]
Polygon = tuple[Point, ...]


@dataclass(frozen=True, slots=True)
class OcrTextRegion:
    """One OCR text fragment anchored to the exact page-text offsets and pixels."""

    text: str
    start: int
    end: int
    confidence: float
    polygon: Polygon
    level: str = "word"
    line_index: int = 0

    def overlaps(self, start: int, end: int) -> bool:
        return start < self.end and self.start < end


@dataclass(frozen=True, slots=True)
class OcrPageLayout:
    """OCR geometry for one raster image page."""

    page_number: int
    width: int
    height: int
    regions: tuple[OcrTextRegion, ...] = field(default_factory=tuple)

    def regions_for_range(self, start: int, end: int) -> tuple[OcrTextRegion, ...]:
        words = tuple(
            region
            for region in self.regions
            if region.level == "word" and region.overlaps(start, end)
        )
        if words:
            return words
        return tuple(
            region
            for region in self.regions
            if region.level == "line" and region.overlaps(start, end)
        )
