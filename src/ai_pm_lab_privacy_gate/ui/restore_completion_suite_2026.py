from __future__ import annotations

"""Final Restore product-completion layer for the stable 2026 experience.

This module deliberately builds on the proven RestorePage/DocumentRestoreService
flow. It adds four local-first capabilities without replacing the restore engine:

* debounced best-match suggestions derived only from local placeholder tokens;
* a real validation summary for restored/unresolved/unknown placeholders;
* a clearer local text-edit session with dirty/reset/discard semantics;
* an optional resumable *local file* session whose source path is encrypted with
  the existing LocalProtector. No document text or restored values are persisted.

No Supabase/API write is introduced here.
"""

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import MethodType

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.documents.restore_service import TOKEN_PATTERN
from ai_pm_lab_privacy_gate.infrastructure.security.local_protector import LocalProtector
from ai_pm_lab_privacy_gate.ui import mockup_restore_edit_2026 as _restore_edit
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    AMBER,
    AMBER_SOFT,
    BLUE,
    BLUE_SOFT,
    BORDER,
    GREEN,
    GREEN_SOFT,
    INK,
    MUTED,
    TEXT,
)
from ai_pm_lab_privacy_gate.ui.organization_product_experience_2026 import (
    PrivacyGateProductDialog,
)


def _secondary_qss() -> str:
    return (
        "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
        "border-radius:8px;padding:6px 9px;font-size:7.7px;font-weight:850;}"
        "QPushButton:hover{background:#F8FAFC;border-color:#98A2B3;}"
        "QPushButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
    )


def _primary_qss() -> str:
    return (
        f"QPushButton{{background:{BLUE};color:#FFFFFF;border:1px solid {BLUE};"
        "border-radius:8px;padding:6px 10px;font-size:7.7px;font-weight:900;}"
        "QPushButton:hover{background:#1D4ED8;border-color:#1D4ED8;}"
        "QPushButton:pressed{background:#1E40AF;border-color:#1E40AF;}"
        "QPushButton:disabled{background:#D0D5DD;border-color:#D0D5DD;color:#FFFFFF;}"
    )


class LocalRestoreSessionStore:
    """Encrypted local pointer to the last file-based Restore session.

    Only the source path is encrypted and persisted, together with a local Library
    document id and timestamp. AI-result text, restored text, mappings, original
    values, account/workspace names and search queries are never written here.
    """

    def __init__(self, data_dir: Path) -> None:
        self.directory = Path(data_dir) / "LocalSessions"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "restore_session.json"
        self.protector = LocalProtector()

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            return

    def save(self, *, source_path: Path, document_id: str | None) -> None:
        try:
            protected = self.protector.protect(str(source_path))
            payload = {
                "version": 1,
                "protected_source_path": base64.b64encode(protected).decode("ascii"),
                "document_id": str(document_id or ""),
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(temporary, self.path)
        except Exception:
            return

    def load(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            protected = base64.b64decode(
                str(payload.get("protected_source_path") or ""), validate=True
            )
            source_path = Path(self.protector.unprotect(protected))
            if not source_path.exists() or not source_path.is_file():
                return None
            return {
                "source_path": source_path,
                "document_id": str(payload.get("document_id") or ""),
                "saved_at": str(payload.get("saved_at") or ""),
            }
        except Exception:
            return None


class RestoreValidationDialog(PrivacyGateProductDialog):
    def __init__(
        self,
        parent,
        *,
        restored_count: int,
        unresolved_tokens: tuple[str, ...],
        unknown_tokens: tuple[str, ...],
    ) -> None:
        complete = not unresolved_tokens and not unknown_tokens
        super().__init__(
            parent,
            title="Restore validation",
            subtitle=(
                "The local restore pass completed cleanly."
                if complete
                else "Review the placeholder tokens that still remain in the restored text."
            ),
            icon_name="protect" if complete else "info",
            width=650,
        )
        self.add_notice(
            f"{restored_count} placeholder occurrence{'s' if restored_count != 1 else ''} restored locally."
        )
        if unresolved_tokens:
            preview = "\n".join(unresolved_tokens[:18])
            self.add_notice(
                "Known restore keys still present after the restore/edit pass:\n" + preview
            )
        if unknown_tokens:
            preview = "\n".join(unknown_tokens[:18])
            self.add_notice(
                "Tokens not belonging to the selected original document:\n" + preview
            )
        if complete:
            self.add_notice(
                "No PrivacyGate placeholders remain in the restored text.", privacy=True
            )
        else:
            self.add_notice(
                "Original values and restore mappings remain local while you review these tokens.",
                privacy=True,
            )
        self.add_actions(
            primary_text="Done",
            primary_callback=self.accept,
            secondary_text="Close",
        )


class _EnhancedRestoreEditDialog(_restore_edit.RestoreEditDialog):
    """Adds explicit working-copy state without changing edit semantics."""

    def __init__(self, parent, *, text: str, source_suffix: str) -> None:
        self._restore_original_text = text
        super().__init__(parent, text=text, source_suffix=source_suffix)
        self.setWindowTitle("Edit restored text")

        self._restore_dirty_status = QLabel("LOCAL EDIT SESSION  ·  No unsaved changes")
        self._restore_dirty_status.setStyleSheet(
            f"background:{GREEN_SOFT};color:{GREEN};border:1px solid #BBF7D0;"
            "border-radius:8px;padding:6px 8px;font-size:7.7px;font-weight:900;"
        )
        try:
            self.body.insertWidget(1, self._restore_dirty_status)
        except Exception:
            self.body.addWidget(self._restore_dirty_status)

        toolbar = self.findChild(QFrame, "RestoreEditToolbar")
        if toolbar is not None and isinstance(toolbar.layout(), QHBoxLayout):
            reset = QPushButton("Reset to restored version")
            reset.setStyleSheet(_secondary_qss())
            reset.setMinimumHeight(34)
            reset.setIcon(icon("restore", color=BLUE, size=14))
            reset.setIconSize(QSize(14, 14))
            reset.clicked.connect(
                lambda _checked=False: self.editor.setPlainText(self._restore_original_text)
            )
            toolbar.layout().addWidget(reset)

        for button in self.findChildren(QPushButton):
            if button.text().strip() == "Cancel":
                button.setText("Discard changes")
                button.setToolTip("Close the editor without applying this working copy.")

        self.editor.textChanged.connect(self._sync_dirty_state)
        self._sync_dirty_state()

    def _sync_dirty_state(self) -> None:
        dirty = self.editor.toPlainText() != self._restore_original_text
        if dirty:
            self._restore_dirty_status.setText("UNSAVED LOCAL EDITS  ·  Apply edits locally to use this version")
            self._restore_dirty_status.setStyleSheet(
                f"background:{AMBER_SOFT};color:{AMBER};border:1px solid #FED7AA;"
                "border-radius:8px;padding:6px 8px;font-size:7.7px;font-weight:900;"
            )
        else:
            self._restore_dirty_status.setText("LOCAL EDIT SESSION  ·  No unsaved changes")
            self._restore_dirty_status.setStyleSheet(
                f"background:{GREEN_SOFT};color:{GREEN};border:1px solid #BBF7D0;"
                "border-radius:8px;padding:6px 8px;font-size:7.7px;font-weight:900;"
            )


def _install_enhanced_editor() -> None:
    if bool(getattr(_restore_edit, "_restore_completion_editor_2026", False)):
        return
    _restore_edit._restore_completion_editor_2026 = True
    # _open_editor resolves RestoreEditDialog from its module globals when invoked,
    # so replacing the class here upgrades the existing button without reconnecting
    # any Qt signal.
    _restore_edit.RestoreEditDialog = _EnhancedRestoreEditDialog


class RestoreCompletionController:
    def __init__(self, main_window) -> None:
        self.main_window = main_window
        self.page = getattr(main_window, "restore_page", None)
        if self.page is None:
            return
        self.finder_controller = getattr(
            main_window, "_restore_document_finder_controller", None
        )
        self.store = LocalRestoreSessionStore(Path(self.page.library.db_path).parent)
        self._mapping_token_cache: dict[str, set[str]] = {}
        self._best_document_id: str | None = None
        self._best_match_count = 0
        self._best_present_count = 0
        self._exact_candidate_count = 0
        self._last_restored_count = 0
        self._validation_active = False

        self._debounce = QTimer(self.page)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(140)
        self._debounce.timeout.connect(self._refresh_smart_state)

        self._build_smart_strip()
        self._wrap_runtime_hooks()
        self._connect_signals()
        self._refresh_smart_state()

    def _build_smart_strip(self) -> None:
        layout = self.page.result_section.layout()
        if not isinstance(layout, QVBoxLayout):
            return

        frame = QFrame(objectName="RestoreCompletionStrip")
        frame.setStyleSheet(
            f"QFrame#RestoreCompletionStrip{{background:#F8FAFC;border:1px solid {BORDER};border-radius:10px;}}"
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(9, 7, 9, 7)
        row.setSpacing(7)

        self.badge = QLabel("RESTORE ASSIST")
        self.badge.setStyleSheet(
            f"background:{BLUE_SOFT};color:{BLUE};border:1px solid #D6E4FF;"
            "border-radius:7px;padding:4px 7px;font-size:7px;font-weight:950;"
        )
        self.summary = QLabel("Upload an AI result to match it with a local original.")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(
            f"color:{TEXT};font-size:7.8px;font-weight:800;background:transparent;border:none;"
        )
        self.detail = QLabel()
        self.detail.setStyleSheet(
            f"color:{MUTED};font-size:7.2px;background:transparent;border:none;"
        )

        copy = QVBoxLayout()
        copy.setSpacing(1)
        copy.addWidget(self.summary)
        copy.addWidget(self.detail)

        self.review_button = QPushButton("Review matches")
        self.review_button.setStyleSheet(_secondary_qss())
        self.review_button.setMinimumHeight(30)
        self.review_button.setIcon(icon("search", color=BLUE, size=13))
        self.review_button.setIconSize(QSize(13, 13))
        self.review_button.clicked.connect(
            lambda _checked=False: self._open_finder()
        )

        self.primary_button = QPushButton("Use best match")
        self.primary_button.setStyleSheet(_primary_qss())
        self.primary_button.setMinimumHeight(30)
        self.primary_button.clicked.connect(
            lambda _checked=False: self._use_best_match()
        )

        self.validation_button = QPushButton("Review validation")
        self.validation_button.setStyleSheet(_secondary_qss())
        self.validation_button.setMinimumHeight(30)
        self.validation_button.clicked.connect(
            lambda _checked=False: self._open_validation()
        )
        self.validation_button.hide()

        self.resume_button = QPushButton("Resume")
        self.resume_button.setStyleSheet(_primary_qss())
        self.resume_button.setMinimumHeight(30)
        self.resume_button.clicked.connect(
            lambda _checked=False: self._resume_last_session()
        )
        self.resume_button.hide()

        self.forget_button = QPushButton("Forget")
        self.forget_button.setStyleSheet(_secondary_qss())
        self.forget_button.setMinimumHeight(30)
        self.forget_button.clicked.connect(
            lambda _checked=False: self._forget_last_session()
        )
        self.forget_button.hide()

        row.addWidget(self.badge)
        row.addLayout(copy, 1)
        row.addWidget(self.validation_button)
        row.addWidget(self.review_button)
        row.addWidget(self.primary_button)
        row.addWidget(self.resume_button)
        row.addWidget(self.forget_button)

        preview_index = layout.indexOf(self.page.preview_tabs)
        layout.insertWidget(max(1, preview_index), frame)
        self.page._restore_completion_strip = frame

    def _wrap_runtime_hooks(self) -> None:
        previous_restore_ready = self.page._restore_ready

        def restore_ready_with_validation(page_self, payload: object) -> None:
            try:
                self._last_restored_count = int(payload.get("restored_count", 0))
            except Exception:
                self._last_restored_count = 0
            previous_restore_ready(payload)
            self._validation_active = bool(self.page.output_text.toPlainText())
            self._save_current_session()
            self._refresh_smart_state()

        self.page._restore_ready = MethodType(restore_ready_with_validation, self.page)

        previous_file_loaded = self.page._file_loaded

        def file_loaded_with_session(page_self, payload: object) -> None:
            previous_file_loaded(payload)
            self._validation_active = False
            self._save_current_session()
            self._schedule_refresh()

        self.page._file_loaded = MethodType(file_loaded_with_session, self.page)

        previous_clear = self.page.clear

        def clear_with_session(page_self) -> None:
            previous_clear()
            self.store.clear()
            self._validation_active = False
            self._last_restored_count = 0
            self._schedule_refresh()

        self.page.clear = MethodType(clear_with_session, self.page)

    def _connect_signals(self) -> None:
        self.page.input_text.textChanged.connect(self._schedule_refresh)
        self.page.output_text.textChanged.connect(self._schedule_refresh)
        self.page.document_combo.currentIndexChanged.connect(
            lambda _index: self._selection_changed()
        )

    def _schedule_refresh(self, *_args) -> None:
        self._debounce.start()

    def _selection_changed(self) -> None:
        self._save_current_session()
        self._schedule_refresh()

    def _mapping_tokens(self, document_id: str) -> set[str]:
        cached = self._mapping_token_cache.get(document_id)
        if cached is not None:
            return cached
        try:
            values = {
                str(mapping.token)
                for mapping in self.page.library.get_mappings(document_id)
                if str(getattr(mapping, "token", "") or "")
            }
        except Exception:
            values = set()
        self._mapping_token_cache[document_id] = values
        return values

    def _rank_candidates(self) -> list[tuple[object, int, int]]:
        present = set(TOKEN_PATTERN.findall(self.page.input_text.toPlainText()))
        if not present:
            return []
        rows: list[tuple[object, int, int]] = []
        try:
            documents = [
                document
                for document in self.page.library.list_documents()
                if document.has_mapping and document.replacement_mode == "reversible"
            ]
        except Exception:
            return []
        for document in documents:
            tokens = self._mapping_tokens(str(document.document_id))
            matching = len(tokens.intersection(present))
            rows.append((document, matching, len(present)))
        rows.sort(
            key=lambda item: (
                0 if item[1] == item[2] and item[2] > 0 else 1,
                -item[1],
                -item[0].updated_at.timestamp(),
            )
        )
        return rows

    def _selected_match(self) -> tuple[int, int]:
        document_id = str(self.page.document_combo.currentData() or "")
        present = set(TOKEN_PATTERN.findall(self.page.input_text.toPlainText()))
        if not document_id or not present:
            return 0, len(present)
        return len(self._mapping_tokens(document_id).intersection(present)), len(present)

    def _refresh_smart_state(self) -> None:
        if not hasattr(self, "summary"):
            return
        if self._validation_active and self.page.output_text.toPlainText():
            self._show_validation_state()
            return

        text = self.page.input_text.toPlainText()
        present = set(TOKEN_PATTERN.findall(text))
        selected_id = str(self.page.document_combo.currentData() or "")
        self.validation_button.hide()
        self.resume_button.hide()
        self.forget_button.hide()

        if not text.strip():
            session = self.store.load()
            self._best_document_id = None
            self.review_button.hide()
            self.primary_button.hide()
            if session is not None:
                source_path = Path(session["source_path"])
                self.badge.setText("RECENT LOCAL SESSION")
                self.badge.setStyleSheet(
                    f"background:{BLUE_SOFT};color:{BLUE};border:1px solid #D6E4FF;"
                    "border-radius:7px;padding:4px 7px;font-size:7px;font-weight:950;"
                )
                self.summary.setText(f"Resume {source_path.name}")
                self.detail.setText(
                    "The file path is encrypted locally. PrivacyGate will reload the file from this PC; no content was saved to the cloud."
                )
                self.resume_button.show()
                self.forget_button.show()
            else:
                self.badge.setText("RESTORE ASSIST")
                self.summary.setText("Upload an AI result to match it with a local original.")
                self.detail.setText("Matching uses placeholder token names and local reversible mappings only.")
            return

        if not present:
            self._best_document_id = None
            self.badge.setText("NO PLACEHOLDERS")
            self.badge.setStyleSheet(
                f"background:{AMBER_SOFT};color:{AMBER};border:1px solid #FED7AA;"
                "border-radius:7px;padding:4px 7px;font-size:7px;font-weight:950;"
            )
            self.summary.setText("This AI result does not contain PrivacyGate placeholders.")
            self.detail.setText("You can still inspect the file, but there is nothing for Restore to replace yet.")
            self.review_button.hide()
            self.primary_button.hide()
            return

        ranked = self._rank_candidates()
        best = ranked[0] if ranked else None
        if best is None or best[1] <= 0:
            self._best_document_id = None
            self.badge.setText("NO STRONG MATCH")
            self.badge.setStyleSheet(
                f"background:{AMBER_SOFT};color:{AMBER};border:1px solid #FED7AA;"
                "border-radius:7px;padding:4px 7px;font-size:7px;font-weight:950;"
            )
            self.summary.setText("No strong local original match found.")
            self.detail.setText("Search by document name, source or account; you can still choose the original manually.")
            self.review_button.show()
            self.primary_button.hide()
            return

        document, matching, present_count = best
        exact_count = sum(
            1 for _document, count, total in ranked if count == total and total > 0
        )
        self._best_document_id = str(document.document_id)
        self._best_match_count = matching
        self._best_present_count = present_count
        self._exact_candidate_count = exact_count

        if selected_id:
            selected_matching, selected_present = self._selected_match()
            exact = selected_present > 0 and selected_matching == selected_present
            self.badge.setText("ORIGINAL MATCHED" if exact else "CHECK ORIGINAL")
            self.badge.setStyleSheet(
                f"background:{GREEN_SOFT if exact else AMBER_SOFT};"
                f"color:{GREEN if exact else AMBER};"
                f"border:1px solid {'#BBF7D0' if exact else '#FED7AA'};"
                "border-radius:7px;padding:4px 7px;font-size:7px;font-weight:950;"
            )
            self.summary.setText(
                f"Selected original matches {selected_matching}/{selected_present} placeholder keys."
            )
            self.detail.setText(
                "Ready to restore locally." if exact else "Review the selected original before restoring."
            )
            self.review_button.show()
            self.primary_button.hide()
            return

        exact = matching == present_count and present_count > 0
        self.badge.setText("BEST MATCH FOUND" if exact else "PARTIAL MATCH")
        self.badge.setStyleSheet(
            f"background:{GREEN_SOFT if exact else AMBER_SOFT};"
            f"color:{GREEN if exact else AMBER};"
            f"border:1px solid {'#BBF7D0' if exact else '#FED7AA'};"
            "border-radius:7px;padding:4px 7px;font-size:7px;font-weight:950;"
        )
        title = str(document.title or "Original protected document")
        self.summary.setText(
            f"{title} · {matching}/{present_count} placeholder keys match"
        )
        self.detail.setText(
            f"{exact_count} exact candidate{'s' if exact_count != 1 else ''} found. "
            "Use the best candidate or review all local matches."
            if exact_count > 1
            else "PrivacyGate ranked this candidate using local placeholder tokens only."
        )
        self.review_button.show()
        self.primary_button.show()
        self.primary_button.setText("Use best match")

    def _validation_values(self) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
        remaining = tuple(TOKEN_PATTERN.findall(self.page.output_text.toPlainText()))
        document_id = str(self.page.document_combo.currentData() or "")
        known = self._mapping_tokens(document_id) if document_id else set()
        unresolved = tuple(token for token in remaining if token in known)
        unknown = tuple(sorted(set(token for token in remaining if token not in known)))
        return self._last_restored_count, unresolved, unknown

    def _show_validation_state(self) -> None:
        restored_count, unresolved, unknown = self._validation_values()
        clean = not unresolved and not unknown
        self.badge.setText("RESTORE COMPLETE" if clean else "REVIEW")
        self.badge.setStyleSheet(
            f"background:{GREEN_SOFT if clean else AMBER_SOFT};"
            f"color:{GREEN if clean else AMBER};"
            f"border:1px solid {'#BBF7D0' if clean else '#FED7AA'};"
            "border-radius:7px;padding:4px 7px;font-size:7px;font-weight:950;"
        )
        self.summary.setText(
            f"{restored_count} restored · {len(unresolved)} unresolved · {len(unknown)} unknown token{'s' if len(unknown) != 1 else ''}"
        )
        self.detail.setText(
            "Safe copy is ready. No PrivacyGate placeholders remain in the restored text."
            if clean
            else "Review the remaining placeholders before using or sharing the restored result."
        )
        self.primary_button.hide()
        self.review_button.hide()
        self.resume_button.hide()
        self.forget_button.hide()
        self.validation_button.setText("Validation details")
        self.validation_button.show()

    def _open_validation(self) -> None:
        restored_count, unresolved, unknown = self._validation_values()
        RestoreValidationDialog(
            self.page,
            restored_count=restored_count,
            unresolved_tokens=unresolved,
            unknown_tokens=unknown,
        ).exec()

    def _open_finder(self) -> None:
        if self.finder_controller is None:
            return
        try:
            self.finder_controller.open_finder()
        finally:
            self._schedule_refresh()

    def _use_best_match(self) -> None:
        document_id = self._best_document_id
        if not document_id:
            return
        try:
            self.page.refresh(document_id)
            index = self.page.document_combo.findData(document_id)
            if index >= 0:
                self.page.document_combo.setCurrentIndex(index)
            if self.finder_controller is not None:
                self.finder_controller._update_selection_copy()
        except Exception:
            return
        self._save_current_session()
        self._schedule_refresh()

    def _save_current_session(self) -> None:
        source_path = getattr(self.page, "_source_path", None)
        if source_path is None:
            return
        source_path = Path(source_path)
        if not source_path.exists() or not source_path.is_file():
            return
        self.store.save(
            source_path=source_path,
            document_id=str(self.page.document_combo.currentData() or ""),
        )

    def _resume_last_session(self) -> None:
        session = self.store.load()
        if session is None:
            self._schedule_refresh()
            return
        document_id = str(session.get("document_id") or "")
        if document_id:
            try:
                self.page.refresh(document_id)
                index = self.page.document_combo.findData(document_id)
                if index >= 0:
                    self.page.document_combo.setCurrentIndex(index)
            except Exception:
                pass
        try:
            self.page._begin_load_file(Path(session["source_path"]))
        except Exception:
            return
        self._schedule_refresh()

    def _forget_last_session(self) -> None:
        self.store.clear()
        self._schedule_refresh()


def apply_restore_completion_suite_2026(main_window) -> None:
    if bool(getattr(main_window, "_restore_completion_suite_2026", False)):
        return
    main_window._restore_completion_suite_2026 = True

    _install_enhanced_editor()
    controller = RestoreCompletionController(main_window)
    main_window._restore_completion_controller = controller
