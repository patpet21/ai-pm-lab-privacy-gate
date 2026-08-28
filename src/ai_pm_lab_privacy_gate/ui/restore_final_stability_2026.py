from __future__ import annotations

"""Final stability bridge for Restore 2026.

Two real-world cases are handled here without weakening the existing restore
engine:

1. Older layout-preserving PrivacyGate PDFs are intentionally image-based. They
   contain visible compact labels (PERSON_001, ADDRESS_001, ...) but no selectable
   ``[[PG_...]]`` token layer. When the user explicitly selects the matching local
   Library record, Restore can safely rebuild the restored *text* from the Library's
   protected_text + encrypted mappings and generate a local reflow PDF. This avoids
   OCR and does not pretend to preserve visual edits made to an image-only PDF.

2. QPdfDocument can keep the previous restored PDF locked on Windows. Every new
   restore therefore receives a unique local run directory after the old PDF
   document is closed, so os.replace never targets a file still owned by Qt.

No document content, path, mapping or restored value is sent to Supabase/API.
"""

import os
import re
import shutil
from pathlib import Path

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
from xml.sax.saxutils import escape

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from ai_pm_lab_privacy_gate.domain.models import ReplacementMapping
from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService
from ai_pm_lab_privacy_gate.infrastructure.documents.restore_service import (
    RestoreReport,
    TOKEN_PATTERN,
)
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker
from ai_pm_lab_privacy_gate.ui import restore_safe_visual_polish_2026 as _safe_visual


_PAGE_MARKER = re.compile(r"(?:^|\n\n)--- Page (\d+) ---\n")


def _document_type(document) -> str:
    text = " ".join(
        str(value or "")
        for value in (
            getattr(document, "title", ""),
            getattr(document, "source_name", ""),
            getattr(document, "source_kind", ""),
        )
    ).lower()
    for suffix, label in (
        (".pdf", "PDF"),
        (".docx", "DOC"),
        (".doc", "DOC"),
        (".xlsx", "XLS"),
        (".xls", "XLS"),
        (".pptx", "PPT"),
        (".ppt", "PPT"),
        (".csv", "CSV"),
        (".txt", "TXT"),
    ):
        if suffix in text:
            return label
    kind = str(getattr(document, "source_kind", "") or "").lower()
    return {
        "pdf": "PDF",
        "docx": "DOC",
        "word": "DOC",
        "xlsx": "XLS",
        "excel": "XLS",
        "pptx": "PPT",
        "powerpoint": "PPT",
        "csv": "CSV",
    }.get(kind, "TXT")


def _colored_file_icon(_provider, document, size: int = 22) -> QIcon:
    """High-contrast file-type badge; provider logos remain official artwork."""
    label = _document_type(document)
    background = {
        "PDF": "#DC2626",
        "DOC": "#2563EB",
        "XLS": "#15803D",
        "PPT": "#EA580C",
        "CSV": "#0F766E",
        "TXT": "#475467",
    }.get(label, "#475467")
    side = max(22, int(size))
    pixmap = QPixmap(side, side)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(background))
    painter.drawRoundedRect(1, 1, side - 2, side - 2, 5, 5)
    painter.setPen(QColor("#FFFFFF"))
    font = QFont()
    font.setBold(True)
    font.setPixelSize(max(7, int(side * 0.31)))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, label[:3])
    painter.end()
    return QIcon(pixmap)


def _install_file_type_badges() -> None:
    # restore_safe_visual_polish resolves this module global whenever Finder rows
    # are rendered, so the swap is presentation-only and does not touch callbacks.
    _safe_visual._native_file_icon = _colored_file_icon


def _split_protected_pages(text: str) -> tuple[tuple[int, str], ...]:
    matches = list(_PAGE_MARKER.finditer(text))
    if not matches:
        return ((1, text),)
    pages: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        page_number = int(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        pages.append((page_number, text[start:end].strip("\n")))
    return tuple(pages)


def _write_restored_reflow_pdf(text: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    font_name = PdfDocumentService._register_windows_font()
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "PrivacyGateRestoredBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9.5,
        leading=13,
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    heading = ParagraphStyle(
        "PrivacyGateRestoredHeading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=12,
        leading=15,
        textColor="#16324F",
        spaceAfter=10,
    )
    doc = SimpleDocTemplate(
        str(destination),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.65 * inch,
        title="Restored copy - AI PM LAB Privacy Gate",
        author="AI PM LAB Privacy Gate",
    )
    story = []
    pages = _split_protected_pages(text)
    for page_index, (page_number, page_text) in enumerate(pages):
        story.append(Paragraph(f"Restored copy - source page {page_number}", heading))
        for chunk in page_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            cleaned = chunk.strip()
            if cleaned:
                story.append(Paragraph(escape(cleaned), body))
            else:
                story.append(Spacer(1, 5))
        if page_index < len(pages) - 1:
            story.append(PageBreak())
    doc.build(story, onFirstPage=PdfDocumentService._footer, onLaterPages=PdfDocumentService._footer)
    return destination


class RestoreFinalStabilityController:
    def __init__(self, main_window) -> None:
        self.main_window = main_window
        self.page = getattr(main_window, "restore_page", None)
        if self.page is None:
            return
        self.completion = getattr(main_window, "_restore_completion_controller", None)
        self._standard_restore = self.page._restore
        self._base_preview_root = Path(self.page._preview_root)
        self._base_preview_root.mkdir(parents=True, exist_ok=True)
        self._run_number = 0
        self._previous_run_dir: Path | None = None
        self._legacy_restore_active = False

        self._rebind_restore_button()
        self._wrap_file_loaded()
        self._connect_state_hooks()
        QTimer.singleShot(0, self._late_bind_finder)
        QTimer.singleShot(0, self._apply_state)

    def _late_bind_finder(self) -> None:
        if self.completion is not None:
            self.completion.finder_controller = getattr(
                self.main_window, "_restore_document_finder_controller", None
            )

    def _rebind_restore_button(self) -> None:
        # RestorePage connected the original bound callback during construction.
        # Replace only this button's click routing with a compatibility dispatcher;
        # all actual standard restores still call the proven original callback.
        try:
            self.page.restore_button.clicked.disconnect()
        except RuntimeError:
            pass
        self.page.restore_button.clicked.connect(
            lambda _checked=False: self._dispatch_restore()
        )

    def _wrap_file_loaded(self) -> None:
        previous = self.page._file_loaded

        def loaded(payload: object) -> None:
            previous(payload)
            self._legacy_restore_active = False
            self.page.result_metric.setText("Waiting for restore")
            QTimer.singleShot(0, self._apply_state)

        self.page._file_loaded = loaded

    def _connect_state_hooks(self) -> None:
        self.page.input_text.textChanged.connect(
            lambda: QTimer.singleShot(0, self._apply_state)
        )
        self.page.document_combo.currentIndexChanged.connect(
            lambda _index: QTimer.singleShot(0, self._apply_state)
        )
        if self.completion is not None:
            self.completion._debounce.timeout.connect(
                lambda: QTimer.singleShot(0, self._apply_state)
            )

    def _selected_library_payload(self):
        document_id = str(self.page.document_combo.currentData() or "")
        if not document_id:
            return None
        try:
            document = self.page.library.get(document_id)
            mappings = self.page.library.get_mappings(document_id)
        except Exception:
            return None
        return document_id, document, mappings

    def _legacy_raster_payload(self):
        source = getattr(self.page, "_source_path", None)
        if source is None or Path(source).suffix.lower() != ".pdf":
            return None
        # A layout-preserving PrivacyGate PDF created by older builds is a single
        # safe raster layer. pdfplumber therefore extracts no token text at all.
        if self.page.input_text.toPlainText().strip():
            return None
        selected = self._selected_library_payload()
        if selected is None:
            return None
        document_id, document, mappings = selected
        protected_text = str(getattr(document, "protected_text", "") or "")
        if not mappings or not TOKEN_PATTERN.search(protected_text):
            return None
        if str(getattr(document, "replacement_mode", "")) != "reversible":
            return None
        return document_id, document, mappings, protected_text

    def _apply_state(self) -> None:
        payload = self._legacy_raster_payload()
        if payload is None:
            return
        busy = getattr(self.page, "_active_worker", None) is not None
        self.page.restore_button.setEnabled(not busy)
        self.page.restore_status.setText(
            "Legacy image-based PrivacyGate PDF detected. The selected local Library mapping can restore it as a safe reflow PDF."
        )
        if self.completion is not None and hasattr(self.completion, "badge"):
            self.completion.badge.setText("LEGACY LAYOUT PDF")
            self.completion.badge.setStyleSheet(
                "background:#FFF7ED;color:#B45309;border:1px solid #FED7AA;"
                "border-radius:7px;padding:4px 7px;font-size:7px;font-weight:950;"
            )
            document = payload[1]
            self.completion.summary.setText(
                f"{document.title} · local reversible mapping available"
            )
            self.completion.detail.setText(
                "This older safe PDF has no selectable token layer. PrivacyGate will use the selected Library protected text and generate a local reflow PDF; no OCR or cloud processing is used."
            )
            self.completion.primary_button.hide()
            self.completion.validation_button.hide()
            self.completion.review_button.show()

    def _prepare_unique_run(self) -> Path:
        try:
            self.page.output_pdf_document.close()
        except Exception:
            pass
        previous = self._previous_run_dir
        if previous is not None and previous.exists():
            try:
                shutil.rmtree(previous)
            except OSError:
                # Windows may release the old QPdfDocument handle a moment later.
                pass
        self._run_number += 1
        run_dir = self._base_preview_root / (
            f"restore-run-{os.getpid()}-{self._run_number:04d}"
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        self._previous_run_dir = run_dir
        self.page._preview_root = run_dir
        return run_dir

    def _dispatch_restore(self) -> None:
        legacy = self._legacy_raster_payload()
        if legacy is not None:
            self._restore_legacy_raster(legacy)
            return
        self._legacy_restore_active = False
        self._prepare_unique_run()
        self._standard_restore()

    def _restore_legacy_raster(self, payload) -> None:
        if getattr(self.page, "_active_worker", None) is not None:
            return
        _document_id, document, mappings, protected_text = payload
        run_dir = self._prepare_unique_run()
        output_path = run_dir / f"restored-reflow-{os.getpid()}-{self._run_number:04d}.pdf"
        self._legacy_restore_active = True
        self.page._set_busy(True, "Restoring legacy layout-safe PDF locally…")

        def task():
            known = {str(item.token) for item in mappings}
            present = set(TOKEN_PATTERN.findall(protected_text))
            unknown = sorted(present.difference(known))
            restored_text = self.page.service.restore_text(protected_text, mappings)
            restored_count = sum(protected_text.count(item.token) for item in mappings)
            _write_restored_reflow_pdf(restored_text, output_path)
            report = RestoreReport(
                output_path=output_path,
                restored_occurrences=restored_count,
                restored_tokens=tuple(sorted(present.intersection(known))),
                unknown_tokens=tuple(unknown),
            )
            return {
                "restored_text": restored_text,
                "restored_count": restored_count,
                "unknown": unknown,
                "report": report,
                "restored_path": output_path,
            }

        worker = FunctionWorker(task)
        self.page._active_worker = worker
        worker.signals.result.connect(self._legacy_ready)
        worker.signals.error.connect(self.page._restore_failed)
        worker.signals.finished.connect(self.page._operation_finished)
        self.page.thread_pool.start(worker)

    def _legacy_ready(self, payload: object) -> None:
        self.page._restore_ready(payload)
        self.page.preview_note.setText(
            "Legacy image-based PrivacyGate PDF on the left · locally restored reflow PDF on the right. The selected Library mapping supplied the restore tokens."
        )
        self.page.result_metric.setText(
            f"{int(payload.get('restored_count', 0))} placeholder occurrences restored locally · reflow PDF"
        )
        if self.completion is not None:
            self.completion._validation_active = bool(
                self.page.output_text.toPlainText()
            )
            self.completion._last_restored_count = int(
                payload.get("restored_count", 0)
            )
            self.completion._refresh_smart_state()


def apply_restore_final_stability_2026(main_window) -> None:
    if bool(getattr(main_window, "_restore_final_stability_2026", False)):
        return
    main_window._restore_final_stability_2026 = True
    _install_file_type_badges()
    controller = RestoreFinalStabilityController(main_window)
    main_window._restore_final_stability_controller = controller
