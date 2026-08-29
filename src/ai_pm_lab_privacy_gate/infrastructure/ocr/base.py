from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from PIL import Image

from ai_pm_lab_privacy_gate.domain.ocr import Polygon


@dataclass(frozen=True, slots=True)
class OcrWordObservation:
    text: str
    confidence: float
    polygon: Polygon


@dataclass(frozen=True, slots=True)
class OcrLineObservation:
    text: str
    confidence: float
    polygon: Polygon
    words: tuple[OcrWordObservation, ...] = field(default_factory=tuple)


class OcrEngine(Protocol):
    """Local OCR boundary used by the document pipeline and by deterministic tests."""

    def read(self, image: Image.Image) -> tuple[OcrLineObservation, ...]: ...
