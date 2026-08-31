from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.storage.ai_library_repository import (
    AiConversationSummary,
    AiLibraryRepository,
)


_PROVIDER_LABELS = {
    "chatgpt": "ChatGPT",
    "claude": "Claude",
    "gemini": "Gemini",
}


class _ProviderConversationPage(QWidget):
    """Read-only conversation list and local restored view for one AI provider."""

    def __init__(self, repository: AiLibraryRepository, provider: str) -> None:
        super().__init__()
        self.repository = repository
        self.provider = provider
        self.provider_label = _PROVIDER_LABELS[provider]
        self._conversations: tuple[AiConversationSummary, ...] = ()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        intro_row = QHBoxLayout()
        intro = QLabel(
            f"Protected {self.provider_label} browser conversations saved by PrivacyGate. "
            "Real values remain encrypted at rest on this device.",
            objectName="Muted",
        )
        intro.setWordWrap(True)
        self.refresh_button = QPushButton("Refresh", objectName="Secondary")
        self.refresh_button.setMinimumHeight(34)
        self.refresh_button.clicked.connect(self.refresh)
        intro_row.addWidget(intro, 1)
        intro_row.addWidget(self.refresh_button)
        layout.addLayout(intro_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        list_card = QFrame(objectName="Card")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(12, 12, 12, 12)
        list_layout.addWidget(QLabel("Conversations", objectName="SectionTitle"))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Conversation", "Turns", "Saved prompts", "Updated"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        list_layout.addWidget(self.table)

        preview_card = QFrame(objectName="Card")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        self.preview_title = QLabel("Local conversation", objectName="SectionTitle")
        self.meta = QLabel(objectName="Muted")
        self.meta.setWordWrap(True)
        self.restore_values = QCheckBox("Show local restored values")
        self.restore_values.setToolTip(
            "Decrypt and display the real values only inside PrivacyGate on this device."
        )
        self.restore_values.toggled.connect(self._selection_changed)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.copy_button = QPushButton("Copy view", objectName="Secondary")
        self.copy_button.clicked.connect(self._copy_view)

        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.meta)
        preview_layout.addWidget(self.restore_values)
        preview_layout.addWidget(self.preview, 1)
        actions = QHBoxLayout()
        actions.addWidget(
            QLabel(
                "Encrypted locally  •  Local only  •  Not shared through MCP",
                objectName="Muted",
            ),
            1,
        )
        actions.addWidget(self.copy_button)
        preview_layout.addLayout(actions)

        splitter.addWidget(list_card)
        splitter.addWidget(preview_card)
        splitter.setSizes([520, 650])
        layout.addWidget(splitter, 1)
        self._set_preview_enabled(False)

    def refresh(self, *_args) -> None:
        selected_id = self._current_session_id()
        self._conversations = self.repository.list_conversations(provider=self.provider)
        self.table.setRowCount(len(self._conversations))

        selected_row = -1
        for row, conversation in enumerate(self._conversations):
            name = QTableWidgetItem(conversation.display_name)
            name.setData(Qt.ItemDataRole.UserRole, conversation.session_id)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem(str(conversation.turn)))
            self.table.setItem(row, 2, QTableWidgetItem(str(conversation.message_count)))
            self.table.setItem(
                row,
                3,
                QTableWidgetItem(
                    conversation.updated_at.astimezone().strftime("%Y-%m-%d %H:%M")
                ),
            )
            if conversation.session_id == selected_id:
                selected_row = row

        if self._conversations:
            self.table.selectRow(selected_row if selected_row >= 0 else 0)
        else:
            self.preview_title.setText("Local conversation")
            self.meta.setText(
                f"No protected {self.provider_label} conversations yet. "
                "New protected conversations will appear here automatically when browser support is active."
            )
            self.preview.clear()
            self.restore_values.setChecked(False)
            self._set_preview_enabled(False)

    def _current_session_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) else None

    def _current_summary(self) -> AiConversationSummary | None:
        session_id = self._current_session_id()
        if session_id is None:
            return None
        return next(
            (item for item in self._conversations if item.session_id == session_id),
            None,
        )

    def _selection_changed(self) -> None:
        summary = self._current_summary()
        if summary is None:
            self._set_preview_enabled(False)
            return

        messages = self.repository.list_messages(summary.session_id)
        mappings = ()
        if self.restore_values.isChecked():
            snapshot = self.repository.load_session(summary.session_id)
            mappings = snapshot.mappings if snapshot is not None else ()

        chunks: list[str] = []
        for message in messages:
            text = message.protected_text
            if mappings:
                for mapping in sorted(mappings, key=lambda item: len(item.token), reverse=True):
                    text = text.replace(mapping.token, mapping.original_text)
            role = "YOU" if message.role == "user" else "AI"
            timestamp = message.created_at.astimezone().strftime("%Y-%m-%d %H:%M")
            chunks.append(f"{role} · TURN {message.turn} · {timestamp}\n{text}")

        self.preview_title.setText("Local conversation")
        mode = "LOCAL RESTORED" if self.restore_values.isChecked() else "PROTECTED"
        self.meta.setText(
            f"{self.provider_label}  •  {summary.display_name}  •  "
            f"{summary.turn} protected turn(s)  •  {mode}  •  "
            f"Session {summary.session_id[:8].upper()}…"
        )
        self.preview.setPlainText(
            "\n\n────────────────────────────────────────\n\n".join(chunks)
            if chunks
            else "No saved protected prompts are available for this conversation yet."
        )
        self._set_preview_enabled(True)

    def _copy_view(self) -> None:
        if self.preview.isEnabled():
            QApplication.clipboard().setText(self.preview.toPlainText())

    def _set_preview_enabled(self, enabled: bool) -> None:
        self.restore_values.setEnabled(enabled)
        self.preview.setEnabled(enabled)
        self.copy_button.setEnabled(enabled)


class AiLibraryPanel(QWidget):
    """Personal Library view for browser-protected AI conversations."""

    def __init__(self, data_dir) -> None:
        super().__init__()
        self.repository = AiLibraryRepository(data_dir)
        self._provider_pages: dict[str, _ProviderConversationPage] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        notice = QFrame(objectName="Card")
        notice_layout = QHBoxLayout(notice)
        notice_layout.setContentsMargins(16, 11, 16, 11)
        title = QLabel("AI Conversations", objectName="SectionTitle")
        detail = QLabel(
            "Encrypted locally  •  Local only  •  Not shared through MCP",
            objectName="Muted",
        )
        detail.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        notice_layout.addWidget(title)
        notice_layout.addStretch(1)
        notice_layout.addWidget(detail)
        root.addWidget(notice)

        self.provider_tabs = QTabWidget()
        self.provider_tabs.tabBar().setMinimumHeight(38)
        self.provider_tabs.tabBar().setStyleSheet(
            "QTabBar::tab { min-width: 118px; padding: 8px 18px; font-weight: 700; }"
        )
        for provider, label in _PROVIDER_LABELS.items():
            page = _ProviderConversationPage(self.repository, provider)
            self._provider_pages[provider] = page
            self.provider_tabs.addTab(page, label)
        self.provider_tabs.currentChanged.connect(self._provider_changed)
        root.addWidget(self.provider_tabs, 1)

    def _provider_changed(self, index: int) -> None:
        page = self.provider_tabs.widget(index)
        if isinstance(page, _ProviderConversationPage):
            page.refresh()

    def refresh(self, *_args) -> None:
        page = self.provider_tabs.currentWidget()
        if isinstance(page, _ProviderConversationPage):
            page.refresh()
