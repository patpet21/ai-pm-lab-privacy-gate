from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics, QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_personal_workspace_2026 import (
    BLUE,
    GREEN,
    INK,
    MUTED,
    NAV_ICON_COLORS,
    ORANGE,
    PURPLE,
    TEAL,
    TEXT,
    _clear_layout,
    _format_when,
    _friendly_event,
    _muted,
)


def _hide_personal_technical_note(page) -> None:
    prefix = "Personal Workspace uses your local Library and local activity metadata."
    for label in page.findChildren(QLabel):
        if label.text().startswith(prefix):
            parent = label.parentWidget()
            while parent is not None and parent is not page and not isinstance(parent, QFrame):
                parent = parent.parentWidget()
            if isinstance(parent, QFrame):
                parent.hide()
                parent.setMaximumHeight(0)
            break


def _polish_static_typography(page) -> None:
    heading_names = {"Recent documents", "Privacy status", "Connected apps", "Recent activity"}
    for label in page.findChildren(QLabel):
        text = label.text().strip()
        if text == "Personal Workspace":
            label.setStyleSheet(
                "color:#101828;font-size:31px;font-weight:950;background:transparent;border:none;"
            )
        elif text == "Your privacy, your data, your control.":
            label.setStyleSheet(
                "color:#667085;font-size:11px;background:transparent;border:none;"
            )
        elif text in heading_names:
            label.setStyleSheet(
                "color:#101828;font-size:14px;font-weight:900;background:transparent;border:none;"
            )

    for button in page.findChildren(QPushButton):
        if button.text().strip() == "View all":
            button.setStyleSheet(
                "QPushButton{background:transparent;color:#2563EB;border:none;padding:4px 6px;"
                "font-size:9px;font-weight:850;}"
                "QPushButton:hover{color:#1D4ED8;text-decoration:underline;}"
            )
        elif button.text().strip() in {"Open Library", "Manage connections", "View all activity"}:
            button.setStyleSheet(
                "QPushButton{background:transparent;color:#475467;border:none;border-top:1px solid #EAECF0;"
                "padding:11px 4px 4px;text-align:left;font-size:9px;font-weight:750;}"
                "QPushButton:hover{color:#2563EB;}"
            )


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
    """Render connected apps as original provider logos only.

    The logo itself is the interaction surface. Hover gives the provider name and
    clicking opens that connected source when the existing Apps browser supports it.
    "View all" remains in the card header for the complete Apps catalog.
    """

    _clear_layout(self.apps_layout)
    self.apps_layout.setSpacing(14)

    if not connected:
        empty = _muted("No apps are connected in this Personal workspace yet.", 9)
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.apps_layout.addWidget(empty, 1)
        return

    self.apps_layout.addStretch(1)
    for provider, title in connected[:7]:
        button = QPushButton()
        button.setObjectName("PersonalConnectedAppLogo")
        button.setFixedSize(72, 72)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(f"{title}\nOpen connected source")
        button.setAccessibleName(title)
        button.setIconSize(QSize(42, 42))
        button.setStyleSheet(
            "QPushButton#PersonalConnectedAppLogo{background:#FFFFFF;border:1px solid #E4E7EC;"
            "border-radius:14px;padding:12px;}"
            "QPushButton#PersonalConnectedAppLogo:hover{background:#F8FAFF;border:1px solid #AFC7FF;}"
            "QPushButton#PersonalConnectedAppLogo:pressed{background:#EEF4FF;border-color:#7AA2FF;}"
        )
        button.clicked.connect(
            lambda _checked=False, p=provider, t=title: _open_connected_provider(self, p, t)
        )
        self.apps_layout.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.apps_layout.addStretch(1)

        # Deliberately no generic fallback glyph: this surface shows the provider's
        # original artwork only. Cached logos appear instantly on subsequent runs.
        self.logo_loader.load(
            provider,
            lambda pixmap, target=button: target.setIcon(QIcon(pixmap)),
        )


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
        row.setMinimumHeight(54)
        row.setStyleSheet(
            "QFrame{background:transparent;border:none;border-bottom:1px solid #F2F4F7;}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(2, 9, 2, 9)
        layout.setSpacing(11)

        extension, tone = self._document_tone(document)
        file_icon = QLabel(extension)
        file_icon.setFixedSize(36, 40)
        file_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_icon.setStyleSheet(
            f"background:{tone};color:#FFFFFF;border:none;border-radius:7px;font-size:7px;font-weight:900;"
        )
        layout.addWidget(file_icon)

        copy = QVBoxLayout()
        copy.setSpacing(3)
        title = QLabel()
        title.setToolTip(document.title)
        title.setStyleSheet(
            f"color:{INK};font-size:10px;font-weight:800;background:transparent;border:none;"
        )
        metrics = QFontMetrics(title.font())
        title.setText(metrics.elidedText(document.title, Qt.TextElideMode.ElideMiddle, 430))
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
        self.documents_layout.addWidget(row)
    self.documents_layout.addStretch(1)


def _metric_row(self, icon_name: str, color: str, label: str, value: int) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 9, 0, 9)
    layout.setSpacing(10)
    marker = QLabel()
    marker.setPixmap(icon(icon_name, color=color, size=17).pixmap(17, 17))
    layout.addWidget(marker)
    name = QLabel(label)
    name.setStyleSheet(
        f"color:{TEXT};font-size:9px;background:transparent;border:none;"
    )
    layout.addWidget(name, 1)
    number = QLabel(str(value))
    number.setStyleSheet(
        f"color:{INK};font-size:10px;font-weight:850;background:transparent;border:none;"
    )
    layout.addWidget(number)
    return row


def _render_activity(self, events) -> None:
    _clear_layout(self.activity_layout)
    if not events:
        empty = _muted("No Personal workspace activity has been recorded yet.", 9)
        empty.setMinimumHeight(170)
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activity_layout.addWidget(empty)
        return

    tones = (GREEN, BLUE, PURPLE, ORANGE, TEAL)
    for index, event in enumerate(events[:5]):
        row = QFrame()
        row.setMinimumHeight(50)
        row.setStyleSheet(
            "QFrame{background:transparent;border:none;border-bottom:1px solid #F2F4F7;}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(2, 11, 2, 11)
        layout.setSpacing(11)
        marker = QLabel()
        marker.setPixmap(icon("history", color=tones[index % len(tones)], size=18).pixmap(18, 18))
        layout.addWidget(marker)
        label = QLabel(_friendly_event(str(event.get("event_type", ""))))
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color:{TEXT};font-size:9px;background:transparent;border:none;"
        )
        layout.addWidget(label, 1)
        when = QLabel(_format_when(event.get("created_at")))
        when.setStyleSheet(
            f"color:{MUTED};font-size:8px;background:transparent;border:none;"
        )
        layout.addWidget(when)
        self.activity_layout.addWidget(row)
    self.activity_layout.addStretch(1)


def _polish_sidebar_icons(main_window) -> None:
    controller = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
    if controller is None:
        return
    for button in getattr(controller, "_buttons", []):
        raw = button.property("mockupFullText") or button.text()
        label = str(raw or "").replace("   ▾", "").replace("   ⌃", "").strip()
        spec = NAV_ICON_COLORS.get(label)
        if spec is None:
            continue
        icon_name, color = spec
        size = 16 if button.objectName() == "RedesignSubNavButton" else 19
        button.setIcon(icon(icon_name, color=color, size=size))
        button.setIconSize(QSize(size, size))


def apply_mockup_personal_workspace_polish_2026(main_window) -> None:
    if bool(getattr(main_window, "_privacygate_mockup_personal_workspace_polish_2026", False)):
        return
    main_window._privacygate_mockup_personal_workspace_polish_2026 = True

    page = getattr(main_window, "personal_workspace_page", None)
    if page is None:
        return

    page._render_apps = MethodType(_render_apps, page)
    page._render_documents = MethodType(_render_documents, page)
    page._metric_row = MethodType(_metric_row, page)
    page._render_activity = MethodType(_render_activity, page)

    _hide_personal_technical_note(page)
    _polish_static_typography(page)
    _polish_sidebar_icons(main_window)

    # Pack the privacy content toward the top instead of leaving a large visual gap
    # between the metrics and the green status banner when the adjacent document
    # card determines the row height.
    privacy_layout = page.privacy_card.layout()
    if isinstance(privacy_layout, QVBoxLayout):
        privacy_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    page.status_metrics.setSpacing(1)
    page.status_banner_text.setStyleSheet(
        "color:#16A34A;font-size:9px;font-weight:850;background:transparent;border:none;"
    )

    page.refresh()
