from __future__ import annotations

"""Safe visual polish for the proven Restore/Finder flow.

This module deliberately does not reparent Restore controls, change RestorePage
signals, replace DocumentRestoreService, or add any remote persistence.  It only
adds artwork/readability to the existing Finder widgets, makes the real Upload
button visually primary, and clarifies the already-existing local text editor.
"""

from pathlib import Path
from types import MethodType

from PySide6.QtCore import QFileInfo, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFileIconProvider, QLabel

from ai_pm_lab_privacy_gate.infrastructure.storage.document_source_metadata import (
    DocumentSourceMetadataRepository,
)
from ai_pm_lab_privacy_gate.ui import restore_document_finder_2026 as _finder
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import BLUE, BLUE_SOFT, GREEN
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader


_SUFFIXES = (
    ".docx",
    ".doc",
    ".xlsx",
    ".xls",
    ".pptx",
    ".ppt",
    ".pdf",
    ".txt",
    ".csv",
)


def _document_suffix(document) -> str:
    haystack = " ".join(
        str(value or "")
        for value in (
            getattr(document, "title", ""),
            getattr(document, "source_name", ""),
            getattr(document, "source_kind", ""),
        )
    ).lower()
    for suffix in _SUFFIXES:
        if suffix in haystack:
            return suffix
    kind = str(getattr(document, "source_kind", "") or "").lower().strip(".")
    return {
        "word": ".docx",
        "docx": ".docx",
        "excel": ".xlsx",
        "xlsx": ".xlsx",
        "powerpoint": ".pptx",
        "pptx": ".pptx",
        "pdf": ".pdf",
        "text": ".txt",
        "txt": ".txt",
        "csv": ".csv",
    }.get(kind, ".txt")


def _type_label(document) -> str:
    suffix = _document_suffix(document).lstrip(".").upper()
    return {
        "DOCX": "WORD",
        "DOC": "WORD",
        "XLSX": "EXCEL",
        "XLS": "EXCEL",
        "PPTX": "POWERPOINT",
        "PPT": "POWERPOINT",
        "TXT": "TEXT",
    }.get(suffix, suffix)


def _native_file_icon(provider: QFileIconProvider, document, size: int = 22) -> QIcon:
    suffix = _document_suffix(document)
    native = provider.icon(QFileInfo(f"privacygate-restore-document{suffix}"))
    if not native.isNull():
        return native
    return icon("document", color=BLUE, size=size)


def _safe_set_item_icon(item, value: QIcon) -> None:
    try:
        item.setIcon(value)
    except (RuntimeError, AttributeError):
        # A filter refresh can replace a QTableWidgetItem while an async provider
        # logo request is in flight.  Artwork must never affect Finder behavior.
        return


def _install_finder_artwork() -> None:
    cls = _finder.OriginalDocumentFinderDialog
    if bool(getattr(cls, "_restore_safe_artwork_2026", False)):
        return
    cls._restore_safe_artwork_2026 = True

    original_init = cls.__init__
    original_apply_filters = cls._apply_filters
    original_rebuild_filters = cls._rebuild_filter_options
    original_selection_changed = cls._selection_changed

    def init_with_artwork(self, *args, **kwargs) -> None:
        # The base QDialog/QObject must exist before ProviderLogoLoader receives
        # this dialog as its Qt parent.
        original_init(self, *args, **kwargs)
        self._restore_safe_file_icons = QFileIconProvider()
        self._restore_safe_logo_loader = ProviderLogoLoader(
            Path(self.page.library.db_path).parent,
            self,
        )
        self.table.setIconSize(QSize(23, 23))
        self.detail.setMinimumHeight(76)
        self._rebuild_filter_options()
        self._apply_filters()

    def rebuild_filters_with_icons(self) -> None:
        original_rebuild_filters(self)
        loader = getattr(self, "_restore_safe_logo_loader", None)
        if loader is None:
            return
        for index in range(self.source_filter.count()):
            provider = str(self.source_filter.itemData(index) or "")
            if not provider:
                self.source_filter.setItemIcon(index, icon("search", color=BLUE, size=15))
                continue
            if provider in {"local", "paste"}:
                self.source_filter.setItemIcon(index, icon("document", color=BLUE, size=16))
                continue
            self.source_filter.setItemIcon(index, icon("cloud", color=BLUE, size=16))

            def apply_logo(pixmap, combo=self.source_filter, combo_index=index) -> None:
                try:
                    combo.setItemIcon(combo_index, QIcon(pixmap))
                except RuntimeError:
                    return

            loader.load(provider, apply_logo)

    def apply_filters_with_artwork(self, *args) -> None:
        original_apply_filters(self, *args)
        file_icons = getattr(self, "_restore_safe_file_icons", None)
        logo_loader = getattr(self, "_restore_safe_logo_loader", None)
        if file_icons is None:
            return

        for table_row, row in enumerate(getattr(self, "_visible_rows", ())):
            document_item = self.table.item(table_row, 0)
            source_item = self.table.item(table_row, 1)
            match_item = self.table.item(table_row, 4)

            if document_item is not None:
                document_item.setIcon(_native_file_icon(file_icons, row.document, 23))
                title = str(row.document.title or "Untitled protected document")
                document_item.setText(
                    f"{title}\n{_type_label(row.document)} · reversible restore mapping"
                )
                document_item.setToolTip(
                    f"{title}\nType: {_type_label(row.document)}\n"
                    f"{row.token_count} local restore key(s)"
                )

            if source_item is not None:
                if row.provider in {"local", "paste"}:
                    source_item.setIcon(icon("document", color=BLUE, size=17))
                else:
                    source_item.setIcon(icon("cloud", color=BLUE, size=17))
                    if logo_loader is not None:
                        logo_loader.load(
                            row.provider,
                            lambda pixmap, target=source_item: _safe_set_item_icon(
                                target, QIcon(pixmap)
                            ),
                        )

            if match_item is not None:
                if row.likely_match:
                    match_item.setText(
                        f"✓  Likely match\n{row.matching_tokens} / {row.present_tokens} keys"
                    )
                elif row.present_tokens and row.matching_tokens:
                    match_item.setText(
                        f"●  Partial match\n{row.matching_tokens} / {row.present_tokens} keys"
                    )
                elif row.present_tokens:
                    match_item.setText(
                        f"No token match\n0 / {row.present_tokens} keys"
                    )
                else:
                    match_item.setText(f"Manual selection\n{row.token_count} restore keys")

            self.table.setRowHeight(table_row, 50)

    def selection_changed_with_detail(self) -> None:
        original_selection_changed(self)
        row = self._selected_row()
        if row is None:
            return
        labels = ", ".join(str(value) for value in getattr(row.document, "labels", ())) or "No labels"
        account = row.account_label or "—"
        legacy = (
            "\nNote: saved before workspace tagging; it remains local and is not assigned to an organization."
            if row.legacy
            else ""
        )
        self.detail.setText(
            "SELECTED DOCUMENT\n"
            f"{row.document.title}\n"
            f"{_type_label(row.document)} · {row.provider_label} · Account: {account} · "
            f"{self._workspace_display(row)}\n"
            f"{self._match_display(row)} · {row.token_count} local restore keys · {labels}"
            f"{legacy}"
        )

    cls.__init__ = init_with_artwork
    cls._rebuild_filter_options = rebuild_filters_with_icons
    cls._apply_filters = apply_filters_with_artwork
    cls._selection_changed = selection_changed_with_detail


def _polish_selected_original(controller) -> None:
    page = controller.page
    if bool(getattr(controller, "_restore_safe_selection_2026", False)):
        return
    controller._restore_safe_selection_2026 = True
    controller._restore_safe_file_icons = QFileIconProvider()
    original = controller._update_selection_copy

    def update_selection_with_file_type(self) -> None:
        original()
        document_id = self.page.document_combo.currentData()
        if not document_id:
            self.selection.setIcon(icon("search", color=BLUE, size=17))
            self.selection.setIconSize(QSize(17, 17))
            return
        try:
            document = self.page.library.get(str(document_id))
            mappings = self.page.library.get_mappings(str(document_id))
            metadata = DocumentSourceMetadataRepository(
                self.page.library.db_path
            ).list_for_documents([str(document_id)]).get(str(document_id))
            source = (
                str(metadata.provider_label or metadata.provider)
                if metadata is not None
                else str(document.source_name or "Local file")
            )
            account = (
                f" · {metadata.account_label}"
                if metadata is not None and metadata.account_label
                else ""
            )
            title = str(document.title or "Original protected document")
            if len(title) > 62:
                title = title[:29] + "…" + title[-29:]
            self.selection.setIcon(
                _native_file_icon(self._restore_safe_file_icons, document, 19)
            )
            self.selection.setIconSize(QSize(19, 19))
            self.selection.setText(
                f"Original selected · {title}\n"
                f"{_type_label(document)} · {source}{account} · "
                f"{len(mappings)} restore key{'s' if len(mappings) != 1 else ''}"
            )
            self.selection.setToolTip(
                f"{document.title}\n{_type_label(document)} · {source}{account}\n"
                "Stored locally · reversible mapping available"
            )
            self.selection.setMinimumHeight(46)
            self.selection.setMaximumHeight(50)
        except Exception:
            return

    controller._update_selection_copy = MethodType(update_selection_with_file_type, controller)
    controller._update_selection_copy()


def _polish_upload_and_edit(main_window) -> None:
    page = getattr(main_window, "restore_page", None)
    if page is None:
        return

    # Visual-only change to the same proven Upload control.  No signal is
    # disconnected/reconnected and no transparent overlay is added.
    try:
        page.drop_zone.setMinimumSize(140, 38)
        page.drop_zone.setMaximumSize(170, 42)
        page.drop_zone.button.setText("Upload AI result")
        page.drop_zone.button.setMinimumHeight(38)
        page.drop_zone.button.setMaximumHeight(42)
        page.drop_zone.button.setMinimumWidth(138)
        page.drop_zone.button.setIcon(icon("upload", color="#FFFFFF", size=15))
        page.drop_zone.button.setIconSize(QSize(15, 15))
        page.drop_zone.button.setStyleSheet(
            f"QPushButton{{background:{BLUE};color:#FFFFFF;border:1px solid {BLUE};"
            "border-radius:9px;padding:8px 12px;font-size:8.5px;font-weight:900;}"
            "QPushButton:hover{background:#1D4ED8;border-color:#1D4ED8;}"
            "QPushButton:pressed{background:#1E40AF;border-color:#1E40AF;}"
            "QPushButton:disabled{background:#D0D5DD;border-color:#D0D5DD;color:#FFFFFF;}"
        )
        page.drop_zone.button.setToolTip(
            "Step 1 · Upload the AI-processed PDF, Word, Excel, PowerPoint or TXT file that still contains PrivacyGate placeholders."
        )
    except (RuntimeError, AttributeError):
        pass

    edit_button = getattr(page, "_restore_2026_edit_button", None)
    actions = getattr(page, "_restore_2026_final_actions", None)
    if edit_button is None or actions is None:
        return

    edit_button.setText("Edit restored text")
    edit_button.setToolTip(
        "Edit the restored text locally. Copy restored text and Download text use the edited version after Apply edits locally."
    )

    layout = actions.layout()
    if layout is None or getattr(page, "_restore_2026_edit_explainer", None) is not None:
        return
    explainer = QLabel(
        "Edit is local and text-focused · After Apply edits locally, Copy restored text and Download text include your changes. "
        "For PDF/Word/Excel/PowerPoint, the separate format-preserving document download remains the restored layout file."
    )
    explainer.setWordWrap(True)
    explainer.setStyleSheet(
        f"background:{BLUE_SOFT};color:#344054;border:1px solid #D6E4FF;"
        "border-radius:8px;padding:6px 8px;font-size:7.5px;font-weight:700;"
    )
    explainer.setToolTip(
        "PrivacyGate does not upload edited/restored content. The editor changes the local restored text layer, not a PDF/Office layout engine."
    )
    # Insert above the action-button row without moving any existing button.
    layout.insertWidget(1, explainer)
    page._restore_2026_edit_explainer = explainer


def apply_restore_safe_visual_polish_2026(main_window) -> None:
    if bool(getattr(main_window, "_restore_safe_visual_polish_2026", False)):
        return
    main_window._restore_safe_visual_polish_2026 = True

    _install_finder_artwork()

    controller = getattr(main_window, "_restore_document_finder_controller", None)
    if controller is not None:
        _polish_selected_original(controller)

    _polish_upload_and_edit(main_window)
