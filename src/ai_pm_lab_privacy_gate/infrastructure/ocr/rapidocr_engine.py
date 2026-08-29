from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image

from ai_pm_lab_privacy_gate.domain.ocr import Polygon
from ai_pm_lab_privacy_gate.infrastructure.ocr.base import (
    OcrLineObservation,
    OcrWordObservation,
)


def _polygon(value: Any) -> Polygon:
    if value is None:
        return ()
    items = list(value)
    if len(items) == 4 and all(isinstance(item, (int, float, np.number)) for item in items):
        left, top, right, bottom = (float(item) for item in items)
        return ((left, top), (right, top), (right, bottom), (left, bottom))
    return tuple((float(point[0]), float(point[1])) for point in items)


class RapidOcrEngine:
    """Lazy, local RapidOCR + ONNX Runtime adapter.

    RapidOCR's PP-OCRv6 small model is multilingual (including English and
    Italian). The heavy OCR runtime is imported and initialized only when an
    image is actually scanned, so normal PrivacyGate startup remains unchanged.
    """

    def __init__(self) -> None:
        self._engine: Any | None = None

    def _get_engine(self):
        if self._engine is None:
            try:
                from rapidocr import RapidOCR
            except ImportError as exc:
                raise RuntimeError(
                    "Image OCR is not installed. Install PrivacyGate OCR dependencies "
                    "(rapidocr and onnxruntime) and try again."
                ) from exc
            self._engine = RapidOCR()
        return self._engine

    def read(self, image: Image.Image) -> tuple[OcrLineObservation, ...]:
        engine = self._get_engine()
        result = engine(
            np.asarray(image.convert("RGB")),
            return_word_box=True,
            return_single_char_box=False,
        )
        boxes = getattr(result, "boxes", None)
        texts = getattr(result, "txts", None)
        scores = getattr(result, "scores", None)
        word_results = getattr(result, "word_results", None)
        if boxes is None or texts is None or scores is None:
            return ()

        lines: list[OcrLineObservation] = []
        for index, (box, text, score) in enumerate(zip(boxes, texts, scores)):
            cleaned = str(text).strip()
            if not cleaned:
                continue
            raw_words = ()
            if word_results is not None and index < len(word_results):
                raw_words = word_results[index] or ()
            words: list[OcrWordObservation] = []
            for item in raw_words:
                if not isinstance(item, (list, tuple)) or len(item) != 3:
                    continue
                word_text, word_score, word_box = item
                word_cleaned = str(word_text).strip()
                polygon = _polygon(word_box)
                if not word_cleaned or not polygon:
                    continue
                words.append(
                    OcrWordObservation(
                        text=word_cleaned,
                        confidence=float(word_score),
                        polygon=polygon,
                    )
                )
            lines.append(
                OcrLineObservation(
                    text=cleaned,
                    confidence=float(score),
                    polygon=_polygon(box),
                    words=tuple(words),
                )
            )
        return tuple(lines)
