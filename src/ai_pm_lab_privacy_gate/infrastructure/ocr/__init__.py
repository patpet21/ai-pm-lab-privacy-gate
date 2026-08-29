"""Local OCR adapters for PrivacyGate raster documents."""

from ai_pm_lab_privacy_gate.infrastructure.ocr.base import (
    OcrEngine,
    OcrLineObservation,
    OcrWordObservation,
)
from ai_pm_lab_privacy_gate.infrastructure.ocr.rapidocr_engine import RapidOcrEngine

__all__ = ["OcrEngine", "OcrLineObservation", "OcrWordObservation", "RapidOcrEngine"]
