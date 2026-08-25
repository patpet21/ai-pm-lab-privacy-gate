from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.storage.document_source_metadata import (
    DocumentSourceMetadataRepository,
)
from ai_pm_lab_privacy_gate.ui.automatic_temp_cleanup import prepare_managed_save
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage
from ai_pm_lab_privacy_gate.ui.source_metadata import resolve_external_source


_INSTALLED = False
_NAVY = "#062B4F"
_INK = "#17384E"
_MUTED = "#61798A"
_TEAL = "#0B7180"


class LibrarySaveDialog(QDialog):
    """Branded, local-first replacement for the generic Qt title prompt."""

    def __init__(self, suggested_title: str, source_line: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save protected copy")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet("QDialog{background:#F7FAFC;}")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        header = QHBoxLayout()
        tile = QLabel()
        tile.setFixedSize(48, 48)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setPixmap(icon("library", color=_TEAL, size=28).pixmap(28, 28))
        tile.setStyleSheet(
            "background:#EAF6F6;border:1px solid #BFE0E2;border-radius:12px;"
        )

        titles = QVBoxLayout()
        title = QLabel("Save protected copy")
        title.setStyleSheet(f"color:{_NAVY};font-size:20px;font-weight:950;")
        subtitle = QLabel("Choose how this protected item will appear in your Local Library.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{_MUTED};font-size:10px;")
        titles.addWidget(title)
        titles.addWidget(subtitle)

        badge = QLabel("LOCAL ONLY")
        badge.setStyleSheet(
            "background:#EAF6F6;color:#0B7180;border:1px solid #BFE0E2;"
            "border-radius:9px;padding:5px 9px;font-size:8px;font-weight:900;"
        )
        header.addWidget(tile, alignment=Qt.AlignmentFlag.AlignTop)
        header.addLayout(titles, 1)
        header.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        source_card = QFrame(objectName="LibrarySaveSource")
        source_card.setStyleSheet(
            "QFrame#LibrarySaveSource{background:#FFFFFF;border:1px solid #D7E2EA;"
            "border-radius:10px;}"
        )
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(12, 10, 12, 10)
        source_layout.setSpacing(4)
        source_heading = QLabel("SOURCE")
        source_heading.setStyleSheet(f"color:{_TEAL};font-size:8px;font-weight:950;")
        source_value = QLabel(source_line or "Current protected content")
        source_value.setWordWrap(True)
        source_value.setStyleSheet(f"color:{_NAVY};font-size:10px;font-weight:850;")
        source_layout.addWidget(source_heading)
        source_layout.addWidget(source_value)
        root.addWidget(source_card)

        field_label = QLabel("Library name")
        field_label.setStyleSheet(f"color:{_INK};font-size:10px;font-weight:900;")
        root.addWidget(field_label)

        self.title_input = QLineEdit(suggested_title)
        self.title_input.setMinimumHeight(44)
        self.title_input.setMaxLength(160)
        self.title_input.setPlaceholderText("Enter a clear name for this protected copy")
        self.title_input.setStyleSheet(
            "QLineEdit{background:#FFFFFF;color:#17384E;border:1px solid #BFCFD9;"
            "border-radius:9px;padding:9px 12px;font-size:11px;font-weight:750;}"
            "QLineEdit:focus{border:2px solid #1595A3;padding:8px 11px;}"
        )
        self.title_input.selectAll()
        root.addWidget(self.title_input)

        note = QFrame(objectName="LibrarySaveNote")
        note.setStyleSheet(
            "QFrame#LibrarySaveNote{background:#F0F7F8;border:1px solid #D1E6E8;"
            "border-radius:9px;}"
        )
        note_layout = QHBoxLayout(note)
        note_layout.setContentsMargins(11, 9, 11, 9)
        shield = QLabel()
        shield.setPixmap(icon("protect", color=_TEAL, size=18).pixmap(18, 18))
        note_text = QLabel(
            "The protected copy and encrypted restore mapping remain on this PC. "
            "The original source is not duplicated into the PrivacyGate cloud."
        )
        note_text.setWordWrap(True)
        note_text.setStyleSheet(f"color:{_MUTED};font-size:9px;")
        note_layout.addWidget(shield, alignment=Qt.AlignmentFlag.AlignTop)
        note_layout.addWidget(note_text, 1)
        root.addWidget(note)

        actions = QHBoxLayout()
        actions.setSpacing(9)
        cancel = QPushButton("Cancel")
        cancel.setMinimumHeight(40)
        cancel.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C8D7E0;"
            "border-radius:9px;padding:8px 16px;font-weight:850;}"
            "QPushButton:hover{background:#F1F7F9;}"
        )
        self.save_button = QPushButton("Save protected copy")
        self.save_button.setMinimumHeight(40)
        self.save_button.setIcon(icon("save", color="#FFFFFF", size=18))
        self.save_button.setStyleSheet(
            "QPushButton{background:#0B8390;color:#FFFFFF;border:1px solid #0B8390;"
            "border-radius:9px;padding:8px 17px;font-weight:900;}"
            "QPushButton:hover{background:#096B76;}"
            "QPushButton:disabled{background:#B7CFD2;border-color:#B7CFD2;}"
        )
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(self.save_button)
        root.addLayout(actions)

        cancel.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.accept)
        self.title_input.textChanged.connect(
            lambda value: self.save_button.setEnabled(bool(value.strip()))
        )
        self.title_input.returnPressed.connect(
            lambda: self.accept() if self.title_input.text().strip() else None
        )
        self.save_button.setEnabled(bool(suggested_title.strip()))
        self.title_input.setFocus()

    @property
    def document_title(self) -> str:
        return self.title_input.text().strip()


def prompt_library_title(
    parent,
    *,
    suggested_title: str,
    source_line: str,
) -> tuple[str, bool]:
    dialog = LibrarySaveDialog(suggested_title, source_line, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return "", False
    title = dialog.document_title
    return title, bool(title)


def install_library_save_dialog() -> None:
    """Use the branded save dialog while preserving the existing save semantics."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    def save_to_library(self: ProtectionPage):
        if self.current_document is None or self.current_result is None:
            return None

        external = str(getattr(self, "_external_source_name", "") or "").strip()
        metadata: dict[str, str] = {}
        if external:
            source_name, metadata = resolve_external_source(
                self,
                external,
                dict(getattr(self, "_external_source_metadata", {}) or {}),
            )
            source_line = source_name
        else:
            source_name = (
                self.current_document.source_path.name
                if self.current_document.source_path
                else "Pasted text"
            )
            source_line = source_name

        title, ok = prompt_library_title(
            self,
            suggested_title=self._derive_title(),
            source_line=source_line,
        )
        if not ok:
            return None

        # Preserve the managed-temp bookkeeping used by Save + Copy, Download
        # and AI handoff without changing user-selected local files.
        prepare_managed_save(self)

        labels = tuple(
            part.strip() for part in self.labels_input.text().split(",") if part.strip()
        )
        document = self.library.save(
            title=title,
            source_kind=self.current_document.source_kind,
            source_name=source_name,
            profile_key=self.profile_combo.currentData(),
            result=self.current_result,
            labels=labels,
        )

        provider = str(metadata.get("provider", "") or "").strip()
        if provider:
            try:
                DocumentSourceMetadataRepository(self.library.db_path).upsert(
                    document_id=document.document_id,
                    provider=provider,
                    provider_label=str(metadata.get("provider_label", "") or provider),
                    account_id=str(metadata.get("account_id", "") or ""),
                    account_label=str(metadata.get("account_label", "") or ""),
                    item_id=str(metadata.get("item_id", "") or ""),
                    item_title=str(metadata.get("item_title", "") or ""),
                    item_kind=str(metadata.get("item_kind", "") or ""),
                )
            except Exception:
                # Provenance enrichment must never invalidate a successful
                # local protected-document save.
                pass

        if hasattr(self, "_managed_temp_saved_ok"):
            self._managed_temp_saved_ok = True
        self.library_changed.emit(document.document_id)
        return document

    ProtectionPage._save_to_library = save_to_library  # type: ignore[method-assign]
