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

    def __init__(self, manager: MobileLinkManager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Make protected copy available on mobile")
        self.resize(760, 620)
        self.setMinimumSize(680, 540)
        self.setStyleSheet(
            """
            QDialog { background: #f4f7fb; color: #142033; }
            QFrame#card {
                background: white;
                border: 1px solid #dfe6ee;
                border-radius: 14px;
            }
            QLabel#title { font-size: 19px; font-weight: 700; color: #111827; }
            QLabel#muted { color: #667085; font-size: 12px; }
            QLabel#section { font-size: 14px; font-weight: 700; color: #152238; }
            QListWidget {
                background: #fbfcfe;
                border: 1px solid #dce3eb;
                border-radius: 10px;
                padding: 5px;
                outline: none;
            }
            QListWidget::item { padding: 9px 10px; margin: 2px; border-radius: 8px; }
            QListWidget::item:selected {
                color: #073b42;
                background: #d9f2f1;
                border: 1px solid #32a7a9;
            }
            QPushButton {
                min-height: 38px;
                border-radius: 9px;
                padding: 0 14px;
                font-weight: 600;
                background: white;
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
        layout.setSpacing(10)

        title = QLabel("Protected copy")
        title.setObjectName("title")
        layout.addWidget(title)

        helper = QLabel(
            "Choose one protected Library item and one trusted mobile device. "
            "Only protected text and safe metadata are authorized. Originals and restore mappings are never transferred."
        )
        helper.setObjectName("muted")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        device_title = QLabel("1. Trusted device")
        device_title.setObjectName("section")
        layout.addWidget(device_title)

        self.devices = QListWidget()
        self.devices.setMaximumHeight(130)
        self.devices.currentItemChanged.connect(self._selection_changed)
        layout.addWidget(self.devices)

        document_title = QLabel("2. Protected Library item")
        document_title.setObjectName("section")
        layout.addWidget(document_title)

        self.documents = QListWidget()
        self.documents.currentItemChanged.connect(self._selection_changed)
        layout.addWidget(self.documents, 1)

        note = QLabel(
            "The mobile device will only see items explicitly granted to its current paired credential. "
            "Saving on Mobile is a separate explicit action; this does not enable automatic Library sync."
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
        self._load()

    def _load(self) -> None:
        self.devices.clear()
        for record in self.manager.pairing.list_clients():
            client_id = str(record["client_id"])
            item = QListWidgetItem(f"{record['client_name']}\n{client_id}")
            item.setData(Qt.ItemDataRole.UserRole, client_id)
            self.devices.addItem(item)

        self.documents.clear()
        for document in self.manager.protected_library.list_mcp_documents(limit=200):
            item = QListWidgetItem(
                f"{document.title}\n{document.document_id} · {document.findings_count} protected finding(s)"
            )
            item.setData(Qt.ItemDataRole.UserRole, document.document_id)
            self.documents.addItem(item)

        if self.devices.count() > 0:
            self.devices.setCurrentRow(0)
        if self.documents.count() > 0:
            self.documents.setCurrentRow(0)
        self._selection_changed()

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
            "The selected device can now fetch this protected copy. "
            "It still must choose Save to Library on Mobile.\n\n"
            f"Grant: {grant['grant_id']}",
        )
        self.accept()
