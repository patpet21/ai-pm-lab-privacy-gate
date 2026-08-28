from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QFileInfo, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_personal_workspace_2026 import (
    BLUE,
    GREEN,
    INK,
    MUTED,
    RED,
    TEAL,
    _clear_layout,
    _format_when,
    _muted,
)


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
    ".png",
    ".jpg",
    ".jpeg",
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
    aliases = {
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
        "image": ".png",
    }
    return aliases.get(kind, ".txt")


def _native_document_icon(page, document, size: int = 36) -> QPixmap:
    """Use the OS-registered file icon first, then a PrivacyGate fallback.

    On Windows this normally resolves to the registered Word/Excel/PowerPoint/PDF
    artwork when those applications/file associations are installed. It avoids
    shipping imitation vendor artwork and stays cross-platform.
    """

    provider = getattr(page, "_personal_file_icon_provider", None)
    if provider is None:
        provider = QFileIconProvider()
        page._personal_file_icon_provider = provider
    suffix = _document_suffix(document)
    native = provider.icon(QFileInfo(f"privacygate-document{suffix}"))
    if not native.isNull():
        pixmap = native.pixmap(size, size)
        if not pixmap.isNull():
            return pixmap

    fallback_color = {
        ".pdf": RED,
        ".doc": BLUE,
        ".docx": BLUE,
        ".xls": GREEN,
        ".xlsx": GREEN,
        ".ppt": "#F97316",
        ".pptx": "#F97316",
    }.get(suffix, TEAL)
    return icon("document", color=fallback_color, size=size).pixmap(size, size)


def _open_library_document(page, document_id: str) -> None:
    library_page = getattr(page.main_window, "library_page", None)
    if library_page is None:
        return
    try:
        library_page.select_document(document_id)
    except Exception:
        pass
    page._open_page("library_page")


def _restore_document(page, document_id: str) -> None:
    opener = getattr(page.main_window, "_open_restore", None)
    if callable(opener):
        opener(document_id)
        return
    library_page = getattr(page.main_window, "library_page", None)
    if library_page is not None:
        try:
            library_page.select_document(document_id)
            library_page.restore_requested.emit(document_id)
        except Exception:
            pass


def _toggle_mcp(page, document_id: str) -> None:
    """Reuse Library's existing confirmation and MCP-sharing semantics."""

    library_page = getattr(page.main_window, "library_page", None)
    if library_page is None:
        return
    try:
        library_page.select_document(document_id)
        library_page._toggle_mcp_share()
    finally:
        page.refresh()


def _show_document_menu(page, button: QPushButton, document) -> None:
    menu = QMenu(page)
    menu.setObjectName("PersonalDocumentMenu")
    menu.setStyleSheet(
        "QMenu#PersonalDocumentMenu{background:#FFFFFF;color:#101828;border:1px solid #D0D5DD;"
        "border-radius:12px;padding:7px;min-width:205px;}"
        "QMenu#PersonalDocumentMenu::item{padding:9px 12px;border-radius:8px;font-size:9px;}"
        "QMenu#PersonalDocumentMenu::item:selected{background:#EEF4FF;color:#1D4ED8;}"
        "QMenu#PersonalDocumentMenu::item:disabled{color:#98A2B3;}"
        "QMenu#PersonalDocumentMenu::separator{height:1px;background:#EAECF0;margin:5px 4px;}"
    )

    open_action = menu.addAction("Open in Library")
    open_action.triggered.connect(
        lambda _checked=False, doc_id=document.document_id: _open_library_document(page, doc_id)
    )

    restore_action = menu.addAction("Restore protected document")
    restore_action.setEnabled(bool(getattr(document, "has_mapping", False)))
    restore_action.triggered.connect(
        lambda _checked=False, doc_id=document.document_id: _restore_document(page, doc_id)
    )

    menu.addSeparator()
    share_label = "Block MCP / AI access" if bool(getattr(document, "mcp_shared", False)) else "Allow MCP / AI access"
    share_action = menu.addAction(share_label)
    share_action.triggered.connect(
        lambda _checked=False, doc_id=document.document_id: _toggle_mcp(page, doc_id)
    )

    position = button.mapToGlobal(button.rect().bottomRight())
    menu.exec(position)


def _render_documents(self, documents) -> None:
    _clear_layout(self.documents_layout)
    if not documents:
        empty = _muted("No protected documents yet. Use Protect to create your first safe copy.", 9)
        empty.setMinimumHeight(170)
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.documents_layout.addWidget(empty)
        return

    for document in documents[:5]:
        row = QFrame()
        row.setMinimumHeight(56)
        row.setStyleSheet(
            "QFrame{background:transparent;border:none;border-bottom:1px solid #F2F4F7;}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(2, 8, 0, 8)
        layout.setSpacing(11)

        file_icon = QLabel()
        file_icon.setFixedSize(42, 42)
        file_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_icon.setPixmap(_native_document_icon(self, document, 34))
        file_icon.setStyleSheet("background:transparent;border:none;")
        file_icon.setToolTip(f"{_document_suffix(document).lstrip('.').upper()} document")
        layout.addWidget(file_icon)

        copy = QVBoxLayout()
        copy.setSpacing(3)
        title = QLabel()
        title.setToolTip(document.title)
        title.setStyleSheet(
            f"color:{INK};font-size:10px;font-weight:800;background:transparent;border:none;"
        )
        metrics = title.fontMetrics()
        title.setText(metrics.elidedText(document.title, Qt.TextElideMode.ElideMiddle, 405))
        meta = QLabel(f"{document.source_kind or 'Document'} · Protected")
        meta.setStyleSheet(
            f"color:{MUTED};font-size:8px;background:transparent;border:none;"
        )
        copy.addWidget(title)
        copy.addWidget(meta)
        layout.addLayout(copy, 1)

        when = QLabel(_format_when(document.updated_at))
        when.setStyleSheet(
            f"color:{MUTED};font-size:8px;background:transparent;border:none;"
        )
        layout.addWidget(when)

        more = QPushButton("•••")
        more.setObjectName("PersonalDocumentMore")
        more.setFixedSize(34, 30)
        more.setCursor(Qt.CursorShape.PointingHandCursor)
        more.setToolTip("Document actions")
        more.setStyleSheet(
            "QPushButton#PersonalDocumentMore{background:transparent;color:#667085;border:none;"
            "border-radius:8px;font-size:12px;font-weight:850;padding:0;}"
            "QPushButton#PersonalDocumentMore:hover{background:#F2F4F7;color:#101828;}"
        )
        more.clicked.connect(
            lambda _checked=False, target=more, doc=document: _show_document_menu(self, target, doc)
        )
        layout.addWidget(more)
        self.documents_layout.addWidget(row)
    self.documents_layout.addStretch(1)


def _open_connected_provider(page, provider: str, title: str) -> None:
    apps_page = getattr(page, "apps_page", None)
    browse = getattr(apps_page, "_browse", None) if apps_page is not None else None
    if callable(browse):
        try:
            browse(provider, title, True)
            return
        except Exception:
            pass
    page._open_page("apps_hub_page")


def _render_apps(self, connected: list[tuple[str, str]]) -> None:
    """Compact app dock: original artwork only, logo itself is clickable."""

    _clear_layout(self.apps_layout)
    self.apps_layout.setContentsMargins(6, 12, 6, 12)
    self.apps_layout.setSpacing(18)

    if not connected:
        empty = _muted("No apps are connected in this Personal workspace yet.", 9)
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.apps_layout.addWidget(empty, 1)
        return

    self.apps_layout.addStretch(1)
    for provider, title in connected[:7]:
        holder = QFrame()
        holder.setFixedSize(88, 88)
        holder.setStyleSheet("QFrame{background:transparent;border:none;}")
        box = QVBoxLayout(holder)
        box.setContentsMargins(5, 5, 5, 5)
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        button = QPushButton()
        button.setObjectName("PersonalConnectedAppDock")
        button.setFixedSize(74, 74)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(f"{title}\nOpen connected source")
        button.setAccessibleName(title)
        button.setIconSize(QSize(46, 46))
        button.setStyleSheet(
            "QPushButton#PersonalConnectedAppDock{background:#FFFFFF;border:1px solid #E5E7EB;"
            "border-radius:18px;padding:13px;}"
            "QPushButton#PersonalConnectedAppDock:hover{background:#F8FAFF;border:1px solid #9DB9FF;}"
            "QPushButton#PersonalConnectedAppDock:pressed{background:#EEF4FF;border-color:#6F95FF;}"
        )
        button.clicked.connect(
            lambda _checked=False, p=provider, t=title: _open_connected_provider(self, p, t)
        )
        box.addWidget(button)
        self.apps_layout.addWidget(holder, 0, Qt.AlignmentFlag.AlignVCenter)

        # Original provider artwork only; cached provider logos load instantly after
        # the first successful fetch. No generic PrivacyGate glyph is substituted.
        self.logo_loader.load(
            provider,
            lambda pixmap, target=button: target.setIcon(QIcon(pixmap)),
        )

    self.apps_layout.addStretch(1)


def apply_mockup_personal_workspace_final_2026(main_window) -> None:
    if bool(getattr(main_window, "_privacygate_mockup_personal_workspace_final_2026", False)):
        return
    main_window._privacygate_mockup_personal_workspace_final_2026 = True

    page = getattr(main_window, "personal_workspace_page", None)
    if page is None:
        return

    page._render_documents = MethodType(_render_documents, page)
    page._render_apps = MethodType(_render_apps, page)
    page.refresh()
