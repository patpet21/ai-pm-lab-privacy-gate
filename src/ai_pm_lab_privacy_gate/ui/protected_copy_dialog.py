from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.mobile_link.manager import MobileLinkManager


class ProtectedCopyDialog(QDialog):
    """Grant one Library item and one explicit transfer mode to one trusted device."""

    def __init__(
        self,
        manager: MobileLinkManager,
        parent=None,
        *,
        preselected_client_id: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.manager = manager
        self._client_id = str(preselected_client_id or "").strip()
        self._trusted: list[dict[str, object]] = []
        self._mode = "protected_copy"

        self.setWindowTitle("Make Library item available")
        self.resize(780, 650)
        self.setMinimumSize(700, 580)
        self.setStyleSheet(self._stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(0)

        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title = QLabel("Make a Library item available")
        title.setObjectName("title")
        subtitle = QLabel(
            "Choose what this trusted device may download. Nothing is synchronized automatically and every authorization remains item-by-item."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        destination = QFrame()
        destination.setObjectName("destinationCard")
        destination_layout = QHBoxLayout(destination)
        destination_layout.setContentsMargins(14, 12, 14, 12)
        destination_layout.setSpacing(12)

        badge = QLabel("1")
        badge.setObjectName("stepBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        destination_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        destination_text = QVBoxLayout()
        destination_text.setSpacing(2)
        destination_label = QLabel("DESTINATION")
        destination_label.setObjectName("eyebrow")
        self.device_name = QLabel("No trusted device selected")
        self.device_name.setObjectName("deviceName")
        self.device_id = QLabel("Select a trusted device in Device Trust first.")
        self.device_id.setObjectName("muted")
        self.device_id.setWordWrap(True)
        destination_text.addWidget(destination_label)
        destination_text.addWidget(self.device_name)
        destination_text.addWidget(self.device_id)
        destination_layout.addLayout(destination_text, 1)

        self.change_device = QPushButton("Change device…")
        self.change_device.setObjectName("secondary")
        self.change_device.clicked.connect(self._change_device)
        destination_layout.addWidget(self.change_device, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(destination)

        mode_card = QFrame()
        mode_card.setObjectName("stepCard")
        mode_layout = QVBoxLayout(mode_card)
        mode_layout.setContentsMargins(14, 12, 14, 12)
        mode_layout.setSpacing(9)
        mode_header = QHBoxLayout()
        mode_badge = QLabel("2")
        mode_badge.setObjectName("stepBadge")
        mode_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_header.addWidget(mode_badge, 0, Qt.AlignmentFlag.AlignTop)
        mode_text = QVBoxLayout()
        mode_title = QLabel("Transfer type")
        mode_title.setObjectName("section")
        mode_hint = QLabel("Choose whether this mobile copy can Restore original values offline.")
        mode_hint.setObjectName("muted")
        mode_hint.setWordWrap(True)
        mode_text.addWidget(mode_title)
        mode_text.addWidget(mode_hint)
        mode_header.addLayout(mode_text, 1)
        mode_layout.addLayout(mode_header)

        self.protected_mode = QRadioButton("Protected copy  ·  protected text only, no Restore")
        self.full_mode = QRadioButton("Full offline session  ·  protected text + encrypted Restore mapping")
        self.protected_mode.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.protected_mode)
        group.addButton(self.full_mode)
        self._mode_group = group
        self.protected_mode.toggled.connect(self._transfer_mode_changed)
        self.full_mode.toggled.connect(self._transfer_mode_changed)
        mode_layout.addWidget(self.protected_mode)
        mode_layout.addWidget(self.full_mode)
        layout.addWidget(mode_card)

        documents_card = QFrame()
        documents_card.setObjectName("stepCard")
        documents_layout = QVBoxLayout(documents_card)
        documents_layout.setContentsMargins(14, 12, 14, 14)
        documents_layout.setSpacing(8)

        documents_header = QHBoxLayout()
        doc_badge = QLabel("3")
        doc_badge.setObjectName("stepBadge")
        doc_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        documents_header.addWidget(doc_badge, 0, Qt.AlignmentFlag.AlignTop)
        doc_text = QVBoxLayout()
        doc_text.setSpacing(2)
        self.doc_title = QLabel("Protected copy to add")
        self.doc_title.setObjectName("section")
        self.doc_hint = QLabel("Only eligible items not already authorized in this mode are shown.")
        self.doc_hint.setObjectName("muted")
        self.doc_hint.setWordWrap(True)
        doc_text.addWidget(self.doc_title)
        doc_text.addWidget(self.doc_hint)
        documents_header.addLayout(doc_text, 1)
        documents_layout.addLayout(documents_header)

        self.documents = QListWidget()
        self.documents.setWordWrap(True)
        self.documents.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.documents.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.documents.currentItemChanged.connect(self._selection_changed)
        documents_layout.addWidget(self.documents, 1)

        self.documents_empty = QLabel("Select a trusted device to see available items.")
        self.documents_empty.setObjectName("empty")
        self.documents_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.documents_empty.setWordWrap(True)
        documents_layout.addWidget(self.documents_empty)
        layout.addWidget(documents_card, 1)

        self.info = QLabel()
        self.info.setObjectName("info")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        self.grant_button = QPushButton("Make available")
        self.grant_button.setObjectName("primary")
        self.grant_button.setEnabled(False)
        self.grant_button.clicked.connect(self._grant)
        actions.addWidget(self.grant_button)
        layout.addLayout(actions)

        root.addWidget(card)
        self._load_trusted_devices()
        self._render_mode()

    @staticmethod
    def _stylesheet() -> str:
        return """
        QDialog { background: #f4f7fb; color: #142033; }
        QFrame#card { background: #ffffff; border: 1px solid #dfe6ee; border-radius: 18px; }
        QFrame#destinationCard { background: #eefaf9; border: 1px solid #b9e2df; border-radius: 13px; }
        QFrame#stepCard { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 13px; }
        QLabel#title { color: #111827; font-size: 21px; font-weight: 800; }
        QLabel#section { color: #152238; font-size: 14px; font-weight: 800; }
        QLabel#eyebrow { color: #087e84; font-size: 11px; font-weight: 800; }
        QLabel#deviceName { color: #102a33; font-size: 15px; font-weight: 800; }
        QLabel#muted { color: #667085; font-size: 12px; }
        QLabel#stepBadge { min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px; border-radius: 14px; background: #d9f2f1; color: #087e84; font-weight: 800; }
        QLabel#empty { color: #667085; background: #ffffff; border: 1px dashed #cbd5e1; border-radius: 10px; padding: 22px; }
        QLabel#info { color: #475467; background: #f8fafc; border: 1px solid #e4e7ec; border-radius: 10px; padding: 10px; }
        QRadioButton { color: #1d2939; font-size: 13px; padding: 5px; }
        QRadioButton::indicator { width: 17px; height: 17px; }
        QListWidget { background: #ffffff; border: 1px solid #dce3eb; border-radius: 10px; padding: 5px; outline: none; }
        QListWidget::item { color: #1d2939; padding: 10px 11px; margin: 2px; border-radius: 8px; }
        QListWidget::item:hover { background: #f1f7f8; }
        QListWidget::item:selected { color: #073b42; background: #d9f2f1; border: 1px solid #32a7a9; }
        QPushButton { min-height: 40px; border-radius: 10px; padding: 0 16px; font-weight: 700; color: #1f2937; background: #ffffff; border: 1px solid #d7dee7; }
        QPushButton:hover { background: #f8fafc; }
        QPushButton#primary { color: #ffffff; background: #118d95; border-color: #118d95; }
        QPushButton#primary:hover { background: #0c7d84; }
        QPushButton#secondary { color: #087e84; background: #ffffff; border-color: #9ed7d3; }
        QPushButton:disabled { color: #98a2b3; background: #edf1f5; border-color: #e0e5eb; }
        """

    def _load_trusted_devices(self) -> None:
        self._trusted = list(self.manager.pairing.list_clients())
        if not self._trusted:
            self._client_id = ""
            self._render_destination()
            self._load_documents()
            return
        known_ids = {str(item["client_id"]) for item in self._trusted}
        if self._client_id not in known_ids:
            self._client_id = str(self._trusted[0]["client_id"])
        self._render_destination()
        self._load_documents()

    def _selected_device_record(self) -> dict[str, object] | None:
        for record in self._trusted:
            if str(record["client_id"]) == self._client_id:
                return record
        return None

    def _render_destination(self) -> None:
        record = self._selected_device_record()
        if record is None:
            self.device_name.setText("No trusted device selected")
            self.device_id.setText("Return to Device Trust and approve a mobile device first.")
            self.change_device.setEnabled(False)
            return
        client_id = str(record["client_id"])
        self.device_name.setText(str(record["client_name"] or "Mobile device"))
        self.device_id.setText(f"Trusted device · …{client_id[-12:]}")
        self.change_device.setEnabled(len(self._trusted) > 1)

    def _change_device(self) -> None:
        if len(self._trusted) <= 1:
            return
        labels: list[str] = []
        ids: list[str] = []
        current_index = 0
        for index, record in enumerate(self._trusted):
            client_id = str(record["client_id"])
            name = str(record["client_name"] or "Mobile device")
            labels.append(f"{name}  ·  …{client_id[-10:]}")
            ids.append(client_id)
            if client_id == self._client_id:
                current_index = index
        selected, accepted = QInputDialog.getItem(
            self,
            "Change trusted device",
            "Trusted device:",
            labels,
            current_index,
            False,
        )
        if not accepted:
            return
        try:
            index = labels.index(selected)
        except ValueError:
            return
        self._client_id = ids[index]
        self._render_destination()
        self._load_documents()

    def _transfer_mode_changed(self, *_args) -> None:
        self._mode = "full_offline_session" if self.full_mode.isChecked() else "protected_copy"
        self._render_mode()
        self._load_documents()

    def _render_mode(self) -> None:
        if not hasattr(self, "info"):
            return
        if self._mode == "full_offline_session":
            self.doc_title.setText("Restorable item to add")
            self.doc_hint.setText("Only documents with a valid Restore mapping and no existing Full offline session grant are shown.")
            self.info.setText(
                "Full offline session: the Restore mapping crosses only the authenticated pinned-TLS local connection, then Mobile immediately stores it separately in its AES-256-GCM device Vault. Nothing downloads automatically."
            )
        else:
            self.doc_title.setText("Protected copy to add")
            self.doc_hint.setText("Only eligible items not already authorized as a Protected copy are shown.")
            self.info.setText(
                "Protected copy: only protected text and safe metadata are available. Restore mappings are not included, and the mobile user still chooses Save to Library."
            )

    def _load_documents(self) -> None:
        self.documents.clear()
        if not self._client_id:
            self.documents.setVisible(False)
            self.documents_empty.setVisible(True)
            self.documents_empty.setText("No trusted device is available.")
            self._selection_changed()
            return

        already_granted = {
            str(item["document_id"])
            for item in self.manager.library_grants.list_for_client(self._client_id)
            if item.get("mode") == self._mode
        }
        eligible = []
        for document in self.manager.protected_library.list_mcp_documents(limit=200):
            if document.document_id in already_granted:
                continue
            if self._mode == "full_offline_session":
                try:
                    source = self.manager.library.get(document.document_id)
                except KeyError:
                    continue
                if source.deleted_at is not None or not source.has_mapping:
                    continue
            eligible.append(document)

        for document in eligible:
            title = str(document.title)
            suffix = "Restorable offline" if self._mode == "full_offline_session" else "Protected only"
            item = QListWidgetItem(f"{title}\n{document.findings_count} protected finding(s) · {suffix}")
            item.setData(Qt.ItemDataRole.UserRole, document.document_id)
            item.setToolTip(title)
            self.documents.addItem(item)

        self.documents.setVisible(bool(eligible))
        self.documents_empty.setVisible(not eligible)
        if not eligible:
            self.documents_empty.setText(
                "No additional eligible items are available for this trusted device in the selected transfer mode."
            )
        self.documents.setCurrentRow(-1)
        self._selection_changed()

    def _selection_changed(self, *_args) -> None:
        self.grant_button.setEnabled(bool(self._client_id) and self.documents.currentItem() is not None)

    def _grant(self) -> None:
        document = self.documents.currentItem()
        if not self._client_id or document is None:
            return
        document_id = str(document.data(Qt.ItemDataRole.UserRole))
        try:
            if self._mode == "full_offline_session":
                grant = self.manager.grant_full_offline_session(
                    client_id=self._client_id,
                    document_id=document_id,
                )
            else:
                grant = self.manager.grant_protected_copy(
                    client_id=self._client_id,
                    document_id=document_id,
                )
        except (KeyError, ValueError) as error:
            QMessageBox.warning(self, "Library item unavailable", str(error))
            return
        except Exception:
            QMessageBox.warning(
                self,
                "Library item unavailable",
                "The selected transfer could not be authorized. No Library data was transferred.",
            )
            return

        if self._mode == "full_offline_session":
            message = (
                "This trusted device can now fetch a Full offline session. The protected text and Restore mapping are still not downloaded until the mobile user explicitly saves it."
            )
        else:
            message = (
                "This trusted device can now fetch the selected Protected copy. Nothing was downloaded automatically."
            )
        QMessageBox.information(
            self,
            "Library item available",
            f"{message}\n\nGrant: {grant['grant_id']}",
        )
        self.accept()
