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
_LOW_CONFIDENCE_LINE = 0.82
_MIN_RETRY_SCORE = 0.78


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


def _ordered_quad(polygon: Polygon) -> np.ndarray | None:
    """Return a stable TL, TR, BR, BL quadrilateral for perspective recovery."""
    if len(polygon) != 4:
        return None
    points = np.asarray(polygon, dtype=np.float64)
    sums = points[:, 0] + points[:, 1]
    differences = points[:, 0] - points[:, 1]
    ordered = np.asarray(
        (
            points[int(np.argmin(sums))],
            points[int(np.argmax(differences))],
            points[int(np.argmax(sums))],
            points[int(np.argmin(differences))],
        ),
        dtype=np.float64,
    )
    if len({(round(float(x), 4), round(float(y), 4)) for x, y in ordered}) != 4:
        return None
    return ordered


def _perspective_coefficients(
    output_points: np.ndarray,
    source_points: np.ndarray,
) -> tuple[float, ...] | None:
    """Solve Pillow's output-to-source perspective transform coefficients."""
    matrix: list[list[float]] = []
    values: list[float] = []
    for (x, y), (source_x, source_y) in zip(output_points, source_points):
        matrix.append([x, y, 1.0, 0.0, 0.0, 0.0, -source_x * x, -source_x * y])
        values.append(source_x)
        matrix.append([0.0, 0.0, 0.0, x, y, 1.0, -source_y * x, -source_y * y])
        values.append(source_y)
    try:
        solved = np.linalg.solve(
            np.asarray(matrix, dtype=np.float64),
            np.asarray(values, dtype=np.float64),
        )
    except np.linalg.LinAlgError:
        return None
    return tuple(float(value) for value in solved)


def _map_perspective_point(
    point: tuple[float, float], coefficients: tuple[float, ...]
) -> tuple[float, float]:
    x, y = point
    a, b, c, d, e, f, g, h = coefficients
    denominator = g * x + h * y + 1.0
    if abs(denominator) < 1e-9:
        return x, y
    return (
        (a * x + b * y + c) / denominator,
        (d * x + e * y + f) / denominator,
    )


def _retry_line_recognition(
    engine: Any,
    image: Image.Image,
    polygon: Polygon,
    original_text: str,
    original_score: float,
) -> tuple[str, float, tuple[OcrWordObservation, ...]] | None:
    """Rectify and re-read one weak line while retaining safe word geometry.

    Screen photos commonly contain horizontal moire. The detector can still find
    the correct quadrilateral but the first recognition crop is weak because the
    line is slightly skewed. Re-projecting that exact quadrilateral to a level
    strip gives the recognizer its intended input and avoids a costly second
    whole-page pass.
    """
    if original_score >= _LOW_CONFIDENCE_LINE:
        return None
    source_quad = _ordered_quad(polygon)
    if source_quad is None:
        return None

    top_width = np.linalg.norm(source_quad[1] - source_quad[0])
    bottom_width = np.linalg.norm(source_quad[2] - source_quad[3])
    left_height = np.linalg.norm(source_quad[3] - source_quad[0])
    right_height = np.linalg.norm(source_quad[2] - source_quad[1])
    width = max(8, int(round(max(top_width, bottom_width))))
    height = max(8, int(round(max(left_height, right_height))))
    output_quad = np.asarray(
        ((0.0, 0.0), (width - 1.0, 0.0), (width - 1.0, height - 1.0), (0.0, height - 1.0)),
        dtype=np.float64,
    )
    coefficients = _perspective_coefficients(output_quad, source_quad)
    if coefficients is None:
        return None

    rectified = image.convert("RGB").transform(
        (width, height),
        Image.Transform.PERSPECTIVE,
        coefficients,
        resample=Image.Resampling.BICUBIC,
        fillcolor="white",
    )
    retry = engine(
        np.asarray(rectified),
        use_det=False,
        use_cls=False,
        use_rec=True,
        return_word_box=True,
        return_single_char_box=False,
    )
    texts = getattr(retry, "txts", None)
    scores = getattr(retry, "scores", None)
    raw_word_results = getattr(retry, "word_results", None)
    if not texts or not scores or not raw_word_results:
        return None
    retry_text = str(texts[0]).strip()
    retry_score = float(scores[0])
    original_alnum = sum(character.isalnum() for character in original_text)
    retry_alnum = sum(character.isalnum() for character in retry_text)
    if (
        retry_score < _MIN_RETRY_SCORE
        or retry_score < original_score + 0.08
        or retry_alnum < original_alnum + 3
    ):
        return None

    word_info = raw_word_results[0]
    word_groups = getattr(word_info, "words", None)
    word_columns = getattr(word_info, "word_cols", None)
    line_length = float(getattr(word_info, "line_txt_len", 0.0) or 0.0)
    if not word_groups or not word_columns or line_length <= 0:
        return None

    words: list[OcrWordObservation] = []
    for characters, columns in zip(word_groups, word_columns):
        word_text = "".join(str(character) for character in characters).strip()
        if not word_text or not columns:
            continue
        left = max(0.0, (float(min(columns)) - 0.75) * width / line_length)
        right = min(float(width - 1), (float(max(columns)) + 0.75) * width / line_length)
        if right <= left:
            continue
        word_polygon = tuple(
            _map_perspective_point(point, coefficients)
            for point in (
                (left, 0.0),
                (right, 0.0),
                (right, float(height - 1)),
                (left, float(height - 1)),
            )
        )
        words.append(
            OcrWordObservation(
                text=word_text,
                confidence=retry_score,
                polygon=word_polygon,
            )
        )
    if not words:
        return None
    canonical = " ".join(word.text for word in words)
    return canonical, retry_score, tuple(words)


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


def _canonical_line_text(line_text: str, words: tuple[OcrWordObservation, ...]) -> str:
    """Prefer word-level recognition when geometry is available.

    RapidOCR can return a weak whole-line transcription while its word pass still
    recovers individual identifiers correctly. Rebuilding the line from those
    words keeps sensitive values in the text that Presidio analyzes and guarantees
    that the same tokens have exact pixel boxes for redaction.
    """
    word_text = " ".join(word.text.strip() for word in words if word.text.strip()).strip()
    return word_text or line_text.strip()


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
            # RapidOCR keeps call parameters on the engine instance.  The
            # low-confidence retry below temporarily uses recognition-only
            # mode; without explicitly restoring the full pipeline here, the
            # next image scan inherits ``use_det=False`` and returns no lines.
            use_det=True,
            use_cls=True,
            use_rec=True,
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

        # A cheap second recognition pass is reserved for weak detected lines.
        # It uses the original pixels and the already-known line quadrilateral,
        # so successful recovery also returns exact word polygons for redaction.
        for index, (text, score, polygon) in enumerate(raw_lines):
            recovered = _retry_line_recognition(
                engine,
                image,
                polygon,
                text,
                score,
            )
            if recovered is None:
                continue
            recovered_text, recovered_score, recovered_words = recovered
            raw_lines[index] = (recovered_text, recovered_score, polygon)
            words_by_line[index] = list(recovered_words)

        lines: list[OcrLineObservation] = []
        for index, (text, score, polygon) in enumerate(raw_lines):
            words = tuple(
                sorted(
                    words_by_line[index],
                    # Words have already been assigned to one detected text line.
                    # Sort horizontally only: a photographed line is rarely
                    # perfectly level, and using its small Y jitter as the primary
                    # key can reverse labels and values (for example putting an ID
                    # number before ``Carta d'identita``).  That destroys the
                    # context required by the identity-document recognizers even
                    # though OCR recovered every token correctly.
                    key=lambda word: min(
                        (point[0] for point in word.polygon), default=0.0
                    ),
                )
            )
            lines.append(
                OcrLineObservation(
                    text=_canonical_line_text(text, words),
                    confidence=score,
                    polygon=polygon,
                    words=words,
                )
            )
        return tuple(lines)
