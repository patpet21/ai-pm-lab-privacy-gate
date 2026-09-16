from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.mobile_link.manager import MobileLinkManager


class ProtectedCopyDialog(QDialog):
    """Grant one protected Library item to one explicitly trusted device."""

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

        self.setWindowTitle("Make protected copy available")
        self.resize(760, 560)
        self.setMinimumSize(680, 500)
        self.setStyleSheet(self._stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(0)

        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(3)
        title = QLabel("Send a protected copy")
        title.setObjectName("title")
        subtitle = QLabel(
            "Choose the protected Library item to make available. Only protected text and safe metadata can leave this Desktop."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)
        mode = QLabel("PROTECTED ONLY")
        mode.setObjectName("modeBadge")
        mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(mode, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

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
        destination_label = QLabel("Destination")
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

        documents_card = QFrame()
        documents_card.setObjectName("stepCard")
        documents_layout = QVBoxLayout(documents_card)
        documents_layout.setContentsMargins(14, 12, 14, 14)
        documents_layout.setSpacing(8)

        documents_header = QHBoxLayout()
        doc_badge = QLabel("2")
        doc_badge.setObjectName("stepBadge")
        doc_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        documents_header.addWidget(doc_badge, 0, Qt.AlignmentFlag.AlignTop)
        doc_text = QVBoxLayout()
        doc_text.setSpacing(2)
        doc_title = QLabel("Protected copy to add")
        doc_title.setObjectName("section")
        doc_hint = QLabel(
            "Only eligible items not already authorized for this trusted device are shown."
        )
        doc_hint.setObjectName("muted")
        doc_hint.setWordWrap(True)
        doc_text.addWidget(doc_title)
        doc_text.addWidget(doc_hint)
        documents_header.addLayout(doc_text, 1)
        documents_layout.addLayout(documents_header)

        self.documents = QListWidget()
        self.documents.setWordWrap(True)
        self.documents.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.documents.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.documents.currentItemChanged.connect(self._selection_changed)
        documents_layout.addWidget(self.documents, 1)

        self.documents_empty = QLabel("Select a trusted device to see available protected copies.")
        self.documents_empty.setObjectName("empty")
        self.documents_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.documents_empty.setWordWrap(True)
        documents_layout.addWidget(self.documents_empty)
        layout.addWidget(documents_card, 1)

        info = QLabel(
            "Nothing downloads automatically. After authorization, the mobile user still chooses Save to Library. Restore mappings are never included."
        )
        info.setObjectName("info")
        info.setWordWrap(True)
        layout.addWidget(info)

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

    @staticmethod
    def _stylesheet() -> str:
        return """
        QDialog { background: #f4f7fb; color: #142033; }
        QFrame#card {
            background: #ffffff; border: 1px solid #dfe6ee; border-radius: 18px;
        }
        QFrame#destinationCard {
            background: #eefaf9; border: 1px solid #b9e2df; border-radius: 13px;
        }
        QFrame#stepCard {
            background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 13px;
        }
        QLabel#title { color: #111827; font-size: 21px; font-weight: 800; }
        QLabel#section { color: #152238; font-size: 14px; font-weight: 800; }
        QLabel#eyebrow { color: #087e84; font-size: 11px; font-weight: 800; }
        QLabel#deviceName { color: #102a33; font-size: 15px; font-weight: 800; }
        QLabel#muted { color: #667085; font-size: 12px; }
        QLabel#modeBadge {
            color: #087e84; background: #e8f7f6; border: 1px solid #b9e2df;
            border-radius: 10px; padding: 6px 10px; font-size: 10px; font-weight: 800;
        }
        QLabel#stepBadge {
            min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
            border-radius: 14px; background: #d9f2f1; color: #087e84; font-weight: 800;
        }
        QLabel#empty {
            color: #667085; background: #ffffff; border: 1px dashed #cbd5e1;
            border-radius: 10px; padding: 22px;
        }
        QLabel#info {
            color: #475467; background: #f8fafc; border: 1px solid #e4e7ec;
            border-radius: 10px; padding: 10px;
        }
        QListWidget {
            background: #ffffff; border: 1px solid #dce3eb; border-radius: 10px;
            padding: 5px; outline: none;
        }
        QListWidget::item {
            color: #1d2939; padding: 10px 11px; margin: 2px; border-radius: 8px;
        }
        QListWidget::item:hover { background: #f1f7f8; }
        QListWidget::item:selected {
            color: #073b42; background: #d9f2f1; border: 1px solid #32a7a9;
        }
        QPushButton {
            min-height: 40px; border-radius: 10px; padding: 0 16px; font-weight: 700;
            color: #1f2937; background: #ffffff; border: 1px solid #d7dee7;
        }
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
            if item.get("mode") == "protected_copy"
        }
        eligible = [
            document
            for document in self.manager.protected_library.list_mcp_documents(limit=200)
            if document.document_id not in already_granted
        ]

        for document in eligible:
            title = str(document.title)
            item = QListWidgetItem(
                f"{title}\n{document.findings_count} protected finding(s)"
            )
            item.setData(Qt.ItemDataRole.UserRole, document.document_id)
            item.setToolTip(title)
            self.documents.addItem(item)

        self.documents.setVisible(bool(eligible))
        self.documents_empty.setVisible(not eligible)
        if not eligible:
            self.documents_empty.setText(
                "No additional protected copies are available for this trusted device. Already-authorized items are hidden."
            )
        self.documents.setCurrentRow(-1)
        self._selection_changed()

    def _selection_changed(self, *_args) -> None:
        self.grant_button.setEnabled(
            bool(self._client_id) and self.documents.currentItem() is not None
        )

    def _grant(self) -> None:
        document = self.documents.currentItem()
        if not self._client_id or document is None:
            return
        try:
            grant = self.manager.grant_protected_copy(
                client_id=self._client_id,
                document_id=str(document.data(Qt.ItemDataRole.UserRole)),
            )
        except (KeyError, ValueError) as error:
            QMessageBox.warning(self, "Protected copy unavailable", str(error))
            return
        except Exception:
            QMessageBox.warning(
                self,
                "Protected copy unavailable",
                "The protected copy could not be authorized. No Library data was transferred.",
            )
            return

        QMessageBox.information(
            self,
            "Protected copy available",
            "This trusted device can now fetch the selected protected copy. Nothing was downloaded automatically.\n\n"
            f"Grant: {grant['grant_id']}",
        )
        self.accept()
