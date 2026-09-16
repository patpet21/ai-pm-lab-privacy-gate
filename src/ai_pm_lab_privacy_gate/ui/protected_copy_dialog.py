from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.mobile_link.manager import MobileLinkManager


class ProtectedCopyDialog(QDialog):
    """Grant exactly one protected Library item to exactly one paired device."""

    def __init__(
        self,
        manager: MobileLinkManager,
        parent=None,
        *,
        preselected_client_id: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.manager = manager
        self.preselected_client_id = str(preselected_client_id or "").strip()
        self.setWindowTitle("Make protected copy available on mobile")
        self.resize(800, 640)
        self.setMinimumSize(700, 560)
        self.setStyleSheet(
            """
            QDialog { background: #f4f7fb; color: #142033; }
            QFrame#card {
                background: white;
                border: 1px solid #dfe6ee;
                border-radius: 16px;
            }
            QFrame#stepCard {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
            QLabel#title { font-size: 20px; font-weight: 800; color: #111827; }
            QLabel#muted { color: #667085; font-size: 12px; }
            QLabel#section { font-size: 14px; font-weight: 800; color: #152238; }
            QLabel#empty {
                color: #667085;
                background: #fbfcfe;
                border: 1px dashed #cbd5e1;
                border-radius: 10px;
                padding: 18px;
            }
            QListWidget {
                background: #ffffff;
                border: 1px solid #dce3eb;
                border-radius: 10px;
                padding: 5px;
                outline: none;
            }
            QListWidget::item { padding: 10px 11px; margin: 2px; border-radius: 8px; }
            QListWidget::item:hover { background: #eef7f8; }
            QListWidget::item:selected {
                color: #073b42;
                background: #d9f2f1;
                border: 1px solid #32a7a9;
            }
            QPushButton {
                min-height: 40px;
                border-radius: 10px;
                padding: 0 16px;
                font-weight: 700;
                background: white;
                color: #1f2937;
                border: 1px solid #d7dee7;
            }
            QPushButton#primary {
                color: white;
                background: #118d95;
                border-color: #118d95;
            }
            QPushButton:disabled {
                color: #98a2b3;
                background: #edf1f5;
                border-color: #e0e5eb;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("Protected copy")
        title.setObjectName("title")
        layout.addWidget(title)

        helper = QLabel(
            "Choose one trusted device and one protected Library item. Only protected text and safe metadata are authorized. "
            "Original values and restore mappings never leave this Desktop."
        )
        helper.setObjectName("muted")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        device_card = QFrame()
        device_card.setObjectName("stepCard")
        device_layout = QVBoxLayout(device_card)
        device_layout.setContentsMargins(12, 10, 12, 12)
        device_layout.setSpacing(7)
        device_title = QLabel("1. Trusted device")
        device_title.setObjectName("section")
        device_layout.addWidget(device_title)
        device_hint = QLabel("The device selected in Device Trust stays selected here. You can change it if needed.")
        device_hint.setObjectName("muted")
        device_hint.setWordWrap(True)
        device_layout.addWidget(device_hint)
        self.devices = QListWidget()
        self.devices.setMaximumHeight(132)
        self.devices.currentItemChanged.connect(self._device_changed)
        device_layout.addWidget(self.devices)
        layout.addWidget(device_card)

        document_card = QFrame()
        document_card.setObjectName("stepCard")
        document_layout = QVBoxLayout(document_card)
        document_layout.setContentsMargins(12, 10, 12, 12)
        document_layout.setSpacing(7)
        document_title = QLabel("2. Protected copy to add")
        document_title.setObjectName("section")
        document_layout.addWidget(document_title)
        document_hint = QLabel(
            "Only protected copies that are eligible and not already authorized for the selected device are shown."
        )
        document_hint.setObjectName("muted")
        document_hint.setWordWrap(True)
        document_layout.addWidget(document_hint)
        self.documents = QListWidget()
        self.documents.currentItemChanged.connect(self._selection_changed)
        document_layout.addWidget(self.documents, 1)
        self.documents_empty = QLabel("Select a trusted device to see available protected copies.")
        self.documents_empty.setObjectName("empty")
        self.documents_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.documents_empty.setWordWrap(True)
        document_layout.addWidget(self.documents_empty)
        layout.addWidget(document_card, 1)

        note = QLabel(
            "Making a copy available does not download it automatically. The mobile user must still choose Save to Library."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

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
        self._load_devices()

    def _load_devices(self) -> None:
        self.devices.clear()
        selected_row = -1
        for index, record in enumerate(self.manager.pairing.list_clients()):
            client_id = str(record["client_id"])
            item = QListWidgetItem(f"{record['client_name']}\n{client_id}")
            item.setData(Qt.ItemDataRole.UserRole, client_id)
            self.devices.addItem(item)
            if client_id == self.preselected_client_id:
                selected_row = index

        if self.devices.count() > 0:
            self.devices.setCurrentRow(selected_row if selected_row >= 0 else 0)
        else:
            self._load_documents_for_device(None)
        self._selection_changed()

    def _device_changed(self, current, _previous=None) -> None:
        client_id = str(current.data(Qt.ItemDataRole.UserRole)) if current is not None else None
        self._load_documents_for_device(client_id)
        self._selection_changed()

    def _load_documents_for_device(self, client_id: str | None) -> None:
        self.documents.clear()
        if not client_id:
            self.documents.setVisible(False)
            self.documents_empty.setVisible(True)
            self.documents_empty.setText("Select a trusted device to see available protected copies.")
            return

        already_granted = {
            str(item["document_id"])
            for item in self.manager.library_grants.list_for_client(client_id)
            if item.get("mode") == "protected_copy"
        }
        eligible = [
            document
            for document in self.manager.protected_library.list_mcp_documents(limit=200)
            if document.document_id not in already_granted
        ]
        for document in eligible:
            item = QListWidgetItem(
                f"{document.title}\n{document.findings_count} protected finding(s) · {document.document_id[:12]}…"
            )
            item.setData(Qt.ItemDataRole.UserRole, document.document_id)
            self.documents.addItem(item)

        self.documents.setVisible(bool(eligible))
        self.documents_empty.setVisible(not eligible)
        if not eligible:
            self.documents_empty.setText(
                "No additional protected copies are available for this device. Items already authorized are hidden."
            )
        # The device selection is preserved, but document choice stays explicit.
        self.documents.setCurrentRow(-1)

    def _selection_changed(self, *_args) -> None:
        self.grant_button.setEnabled(
            self.devices.currentItem() is not None and self.documents.currentItem() is not None
        )

    def _grant(self) -> None:
        device = self.devices.currentItem()
        document = self.documents.currentItem()
        if device is None or document is None:
            return
        try:
            grant = self.manager.grant_protected_copy(
                client_id=str(device.data(Qt.ItemDataRole.UserRole)),
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
            "The selected device can now fetch this protected copy. It still must choose Save to Library on Mobile.\n\n"
            f"Grant: {grant['grant_id']}",
        )
        self.accept()
