from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from ai_pm_lab_privacy_gate.domain.ocr import Polygon
from ai_pm_lab_privacy_gate.infrastructure.ocr.base import (
    OcrLineObservation,
    OcrWordObservation,
)


_MAX_PREPROCESSED_DIMENSION = 3200
_MAX_UPSCALE = 2.0


def _polygon(value: Any) -> Polygon:
    if value is None:
        return ()
    items = list(value)
    if len(items) == 4 and all(isinstance(item, (int, float, np.number)) for item in items):
        left, top, right, bottom = (float(item) for item in items)
        return ((left, top), (right, top), (right, bottom), (left, bottom))
    return tuple((float(point[0]), float(point[1])) for point in items)


def _scale_polygon(polygon: Polygon, factor: float) -> Polygon:
    if not polygon or factor == 1.0:
        return polygon
    return tuple((point[0] * factor, point[1] * factor) for point in polygon)


def _prepare_for_ocr(image: Image.Image) -> tuple[Image.Image, float]:
    """Normalize a document photo/screenshot before local OCR.

    Photos of screens and camera captures often contain moire, weak contrast and
    text which is only a few pixels high. RapidOCR performs substantially better
    when that text is enlarged and contrast-normalized first. The returned scale
    factor is used to map every OCR polygon back into the original image space so
    visual redaction still lands on the source pixels.
    """
    rgb = image.convert("RGB")
    width, height = rgb.size
    largest = max(width, height)
    if largest <= 0:
        return rgb, 1.0

    scale = min(_MAX_UPSCALE, _MAX_PREPROCESSED_DIMENSION / float(largest))
    scale = max(1.0, scale)
    if scale > 1.05:
        rgb = rgb.resize(
            (max(1, round(width * scale)), max(1, round(height * scale))),
            Image.Resampling.LANCZOS,
        )
    else:
        scale = 1.0

    gray = ImageOps.grayscale(rgb)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.25)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1.0, percent=170, threshold=2))
    return gray.convert("RGB"), scale


def _bounds(polygon: Polygon) -> tuple[float, float, float, float] | None:
    if not polygon:
        return None
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _word_entries(raw: Any, coordinate_scale: float = 1.0) -> tuple[OcrWordObservation, ...]:
    """Normalize RapidOCR word_results across flat and older nested shapes."""
    if raw is None:
        return ()
    try:
        items = list(raw)
    except TypeError:
        return ()

    candidates: list[Any] = []
    for item in items:
        if isinstance(item, (list, tuple)) and len(item) == 3 and isinstance(item[0], str):
            candidates.append(item)
            continue
        if isinstance(item, (list, tuple)):
            for nested in item:
                if (
                    isinstance(nested, (list, tuple))
                    and len(nested) == 3
                    and isinstance(nested[0], str)
                ):
                    candidates.append(nested)

    words: list[OcrWordObservation] = []
    for word_text, word_score, word_box in candidates:
        cleaned = str(word_text).strip()
        polygon = _scale_polygon(_polygon(word_box), coordinate_scale)
        if not cleaned or not polygon:
            continue
        try:
            confidence = float(word_score)
        except (TypeError, ValueError):
            confidence = 0.0
        words.append(
            OcrWordObservation(
                text=cleaned,
                confidence=confidence,
                polygon=polygon,
            )
        )
    return tuple(words)


def _line_for_word(word: OcrWordObservation, line_polygons: tuple[Polygon, ...]) -> int | None:
    word_bounds = _bounds(word.polygon)
    if word_bounds is None:
        return None
    wx1, wy1, wx2, wy2 = word_bounds
    cx = (wx1 + wx2) / 2.0
    cy = (wy1 + wy2) / 2.0

    best_index: int | None = None
    best_score = float("inf")
    for index, polygon in enumerate(line_polygons):
        line_bounds = _bounds(polygon)
        if line_bounds is None:
            continue
        lx1, ly1, lx2, ly2 = line_bounds
        margin_y = max(3.0, (ly2 - ly1) * 0.35)
        margin_x = max(3.0, (lx2 - lx1) * 0.03)
        if lx1 - margin_x <= cx <= lx2 + margin_x and ly1 - margin_y <= cy <= ly2 + margin_y:
            line_cy = (ly1 + ly2) / 2.0
            score = abs(cy - line_cy)
            if score < best_score:
                best_score = score
                best_index = index
    return best_index


class RapidOcrEngine:
    """Lazy, local RapidOCR + ONNX Runtime adapter."""

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
        prepared, input_scale = _prepare_for_ocr(image)
        coordinate_scale = 1.0 / input_scale
        result = engine(
            np.asarray(prepared),
            return_word_box=True,
            return_single_char_box=False,
        )
        boxes = getattr(result, "boxes", None)
        texts = getattr(result, "txts", None)
        scores = getattr(result, "scores", None)
        if boxes is None or texts is None or scores is None:
            return ()

        raw_lines: list[tuple[str, float, Polygon]] = []
        for box, text, score in zip(boxes, texts, scores):
            cleaned = str(text).strip()
            polygon = _scale_polygon(_polygon(box), coordinate_scale)
            if not cleaned or not polygon:
                continue
            raw_lines.append((cleaned, float(score), polygon))

        # RapidOCR 3.x exposes word_results as one flat sequence for the whole
        # page. Older/alternate results may be nested. Normalize first, then map
        # each word back to the OCR line by its pixel centre.
        page_words = _word_entries(
            getattr(result, "word_results", None),
            coordinate_scale=coordinate_scale,
        )
        line_polygons = tuple(item[2] for item in raw_lines)
        words_by_line: list[list[OcrWordObservation]] = [[] for _ in raw_lines]
        for word in page_words:
            line_index = _line_for_word(word, line_polygons)
            if line_index is not None:
                words_by_line[line_index].append(word)

        lines: list[OcrLineObservation] = []
        for index, (text, score, polygon) in enumerate(raw_lines):
            words = sorted(
                words_by_line[index],
                key=lambda word: (
                    min((point[1] for point in word.polygon), default=0.0),
                    min((point[0] for point in word.polygon), default=0.0),
                ),
            )
            lines.append(
                OcrLineObservation(
                    text=text,
                    confidence=score,
                    polygon=polygon,
                    words=tuple(words),
                )
            )
        return tuple(lines)
