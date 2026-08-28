from __future__ import annotations

from datetime import datetime
from types import MethodType

from PySide6.QtCore import QRectF, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.application.feature_suite import LocalActivityStore
from ai_pm_lab_privacy_gate.ui.apps_hub import APPS
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_redesign_shell_2026 import _NAV_STYLE, _page_index
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader


BLUE = "#2563EB"
BLUE_SOFT = "#EEF4FF"
INK = "#101828"
TEXT = "#344054"
MUTED = "#667085"
BORDER = "#E4E7EC"
CANVAS = "#F8FAFC"
WHITE = "#FFFFFF"
GREEN = "#16A34A"
GREEN_SOFT = "#ECFDF3"
ORANGE = "#F97316"
PURPLE = "#7C3AED"
TEAL = "#0891B2"
RED = "#DC2626"


NAV_ICON_COLORS: dict[str, tuple[str, str]] = {
    "Overview": ("document", BLUE),
    "Protect": ("protect", BLUE),
    "Restore": ("restore", ORANGE),
    "Library": ("library", "#2563EB"),
    "Apps": ("cloud", PURPLE),
    "MCP & AI Direct": ("workflow", TEAL),
    "Automation": ("workflow", PURPLE),
    "Activity": ("history", "#475467"),
    "Governance": ("protect", GREEN),
    "AI & Apps": ("workflow", PURPLE),
    "Policy Center": ("protect", ORANGE),
    "Team": ("contact", BLUE),
    "Members & roles": ("contact", BLUE),
    "Devices": ("document", TEAL),
    "Settings": ("settings", "#475467"),
}


def _card() -> QFrame:
    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame{{background:{WHITE};border:1px solid {BORDER};border-radius:14px;}}"
    )
    return frame


def _heading(text: str, size: int = 13) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color:{INK};font-size:{size}px;font-weight:900;background:transparent;border:none;"
    )
    return label


def _muted(text: str = "", size: int = 8) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(
        f"color:{MUTED};font-size:{size}px;background:transparent;border:none;"
    )
    return label


def _link_button(text: str, callback) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton{background:transparent;color:#2563EB;border:none;padding:4px 6px;"
        "font-size:8px;font-weight:850;}QPushButton:hover{color:#1D4ED8;text-decoration:underline;}"
    )
    button.clicked.connect(lambda _checked=False: callback())
    return button


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            _clear_layout(child)


def _format_when(value: object) -> str:
    if isinstance(value, datetime):
        moment = value
    else:
        raw = str(value or "")
        if not raw:
            return "—"
        try:
            moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw[:16]
    return moment.strftime("%b %d · %H:%M")


def _friendly_event(value: str) -> str:
    key = str(value or "").strip().lower()
    mapping = {
        "library_saved": "Protected document saved",
        "document_scanned": "Document scanned",
        "batch_protected": "Batch protection completed",
        "preflight_completed": "Privacy preflight completed",
        "ocr_completed": "Local OCR completed",
        "encrypted_backup_created": "Encrypted backup created",
        "file_renamed": "Library item renamed",
        "file_moved": "Library item moved",
        "file_safe_deleted": "Library item moved to trash",
    }
    return mapping.get(key, key.replace("_", " ").title() or "PrivacyGate activity")


class _StatusRing(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.value = 0
        self.caption = "Ready"
        self.setFixedSize(150, 150)

    def set_value(self, value: int, caption: str) -> None:
        self.value = max(0, min(100, int(value)))
        self.caption = caption
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(17, 17, 116, 116)
        base = QPen(QColor("#E5E7EB"), 12)
        base.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(base)
        painter.drawArc(rect, 0, 360 * 16)
        progress = QPen(QColor(GREEN), 12)
        progress.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(progress)
        painter.drawArc(rect, 90 * 16, -int(360 * 16 * self.value / 100))
        painter.setPen(QColor(INK))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(24 if self.value else 16)
        painter.setFont(font)
        center = f"{self.value}%" if self.value else "READY"
        painter.drawText(QRectF(18, 45, 114, 36), Qt.AlignmentFlag.AlignCenter, center)
        painter.setPen(QColor(GREEN))
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(18, 82, 114, 20), Qt.AlignmentFlag.AlignCenter, self.caption)
        painter.end()


class _AdaptiveDashboard(QWidget):
    def __init__(self, cards: list[QWidget], parent=None) -> None:
        super().__init__(parent)
        self.cards = cards
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        self.columns = 0
        self._reflow(force=True)

    def _reflow(self, *, force: bool = False) -> None:
        columns = 2 if self.width() >= 820 else 1
        if columns == self.columns and not force:
            return
        self.columns = columns
        for card in self.cards:
            self.grid.removeWidget(card)
        for index, card in enumerate(self.cards):
            self.grid.addWidget(card, index // columns, index % columns)
        for column in range(2):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._reflow()


class MockupPersonalWorkspace(QWidget):
    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.library = main_window.library
        self.activity = LocalActivityStore(self.library.data_dir)
        self.logo_loader = ProviderLogoLoader(self.library.data_dir, self)
        self.apps_page = getattr(main_window, "apps_hub_page", None)
        self.apps_service = getattr(self.apps_page, "service", None)
        self._build()
        self.refresh()
        main_window.protection_page.library_changed.connect(
            lambda _document_id: QTimer.singleShot(0, self.refresh)
        )

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea{{background:{CANVAS};border:none;}}"
            "QScrollBar:vertical{background:transparent;width:7px;margin:2px;}"
            "QScrollBar::handle:vertical{background:#D0D5DD;border-radius:3px;min-height:30px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )
        host = QWidget()
        host.setStyleSheet(f"background:{CANVAS};")
        body = QVBoxLayout(host)
        body.setContentsMargins(30, 26, 30, 28)
        body.setSpacing(18)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel("Personal Workspace")
        title.setStyleSheet(
            f"color:{INK};font-size:30px;font-weight:950;background:transparent;border:none;"
        )
        subtitle = QLabel("Your privacy, your data, your control.")
        subtitle.setStyleSheet(
            f"color:{MUTED};font-size:11px;background:transparent;border:none;"
        )
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        badge = QLabel("PERSONAL")
        badge.setStyleSheet(
            f"background:{BLUE_SOFT};color:{BLUE};border:1px solid #D6E4FF;border-radius:9px;"
            "padding:6px 9px;font-size:7px;font-weight:900;"
        )
        header.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        body.addLayout(header)

        self.recent_card = self._recent_documents_card()
        self.privacy_card = self._privacy_status_card()
        self.apps_card = self._connected_apps_card()
        self.activity_card = self._recent_activity_card()
        body.addWidget(
            _AdaptiveDashboard(
                [self.recent_card, self.privacy_card, self.apps_card, self.activity_card]
            )
        )

        note = QFrame()
        note.setStyleSheet(
            "QFrame{background:#F0F7FF;border:1px solid #CFE0FF;border-radius:13px;}"
        )
        row = QHBoxLayout(note)
        row.setContentsMargins(15, 12, 15, 12)
        shield = QLabel()
        shield.setPixmap(icon("protect", color=BLUE, size=20).pixmap(20, 20))
        row.addWidget(shield, 0, Qt.AlignmentFlag.AlignTop)
        copy = _muted(
            "Personal Workspace uses your local Library and local activity metadata. Organization policy is not applied while Personal is active.",
            8,
        )
        copy.setStyleSheet(
            "color:#344054;font-size:8px;font-weight:700;background:transparent;border:none;"
        )
        row.addWidget(copy, 1)
        body.addWidget(note)
        body.addStretch(1)

        scroll.setWidget(host)
        root.addWidget(scroll)

    def _open_page(self, attribute: str) -> None:
        page = getattr(self.main_window, attribute, None)
        pages = getattr(self.main_window, "pages", None)
        if page is None or pages is None:
            return
        index = pages.indexOf(page)
        if index >= 0:
            self.main_window._show_page(index)

    def _open_activity(self) -> None:
        controller = getattr(self.main_window, "_privacygate_redesign_sidebar_controller", None)
        callback = getattr(controller, "_open_activity", None) if controller is not None else None
        if callable(callback):
            callback()

    def _card_header(self, title: str, action: str, callback) -> tuple[QFrame, QVBoxLayout]:
        card = _card()
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 17, 18, 16)
        box.setSpacing(10)
        row = QHBoxLayout()
        row.addWidget(_heading(title, 13))
        row.addStretch(1)
        row.addWidget(_link_button(action, callback))
        box.addLayout(row)
        return card, box

    def _recent_documents_card(self) -> QFrame:
        card, box = self._card_header(
            "Recent documents", "View all", lambda: self._open_page("library_page")
        )
        self.documents_layout = QVBoxLayout()
        self.documents_layout.setSpacing(1)
        box.addLayout(self.documents_layout, 1)
        footer = QPushButton("Open Library")
        footer.setIcon(icon("library", color="#475467", size=16))
        footer.setIconSize(QSize(16, 16))
        footer.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.setStyleSheet(
            "QPushButton{background:transparent;color:#475467;border:none;border-top:1px solid #EAECF0;"
            "padding:10px 4px 3px;text-align:left;font-size:8px;font-weight:750;}"
            "QPushButton:hover{color:#2563EB;}"
        )
        footer.clicked.connect(lambda: self._open_page("library_page"))
        box.addWidget(footer)
        return card

    def _privacy_status_card(self) -> QFrame:
        card, box = self._card_header(
            "Privacy status", "Protect", lambda: self._open_page("protection_page")
        )
        content = QHBoxLayout()
        content.setSpacing(20)
        self.status_ring = _StatusRing()
        content.addWidget(self.status_ring, 0, Qt.AlignmentFlag.AlignTop)
        self.status_metrics = QVBoxLayout()
        self.status_metrics.setSpacing(0)
        content.addLayout(self.status_metrics, 1)
        box.addLayout(content, 1)

        self.status_banner = QFrame()
        self.status_banner.setStyleSheet(
            f"QFrame{{background:{GREEN_SOFT};border:none;border-radius:11px;}}"
        )
        banner_row = QHBoxLayout(self.status_banner)
        banner_row.setContentsMargins(12, 10, 12, 10)
        banner_icon = QLabel()
        banner_icon.setPixmap(icon("protect", color=GREEN, size=19).pixmap(19, 19))
        banner_row.addWidget(banner_icon)
        self.status_banner_text = QLabel()
        self.status_banner_text.setWordWrap(True)
        self.status_banner_text.setStyleSheet(
            f"color:{GREEN};font-size:8px;font-weight:850;background:transparent;border:none;"
        )
        banner_row.addWidget(self.status_banner_text, 1)
        box.addWidget(self.status_banner)
        return card

    def _connected_apps_card(self) -> QFrame:
        card, box = self._card_header(
            "Connected apps", "View all", lambda: self._open_page("apps_hub_page")
        )
        self.apps_layout = QHBoxLayout()
        self.apps_layout.setSpacing(13)
        box.addLayout(self.apps_layout, 1)
        footer = QPushButton("Manage connections")
        footer.setIcon(icon("workflow", color="#475467", size=16))
        footer.setIconSize(QSize(16, 16))
        footer.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.setStyleSheet(
            "QPushButton{background:transparent;color:#475467;border:none;border-top:1px solid #EAECF0;"
            "padding:10px 4px 3px;text-align:left;font-size:8px;font-weight:750;}"
            "QPushButton:hover{color:#2563EB;}"
        )
        footer.clicked.connect(lambda: self._open_page("apps_hub_page"))
        box.addWidget(footer)
        return card

    def _recent_activity_card(self) -> QFrame:
        card, box = self._card_header("Recent activity", "View all", self._open_activity)
        self.activity_layout = QVBoxLayout()
        self.activity_layout.setSpacing(1)
        box.addLayout(self.activity_layout, 1)
        footer = QPushButton("View all activity")
        footer.setIcon(icon("history", color="#475467", size=16))
        footer.setIconSize(QSize(16, 16))
        footer.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.setStyleSheet(
            "QPushButton{background:transparent;color:#475467;border:none;border-top:1px solid #EAECF0;"
            "padding:10px 4px 3px;text-align:left;font-size:8px;font-weight:750;}"
            "QPushButton:hover{color:#2563EB;}"
        )
        footer.clicked.connect(self._open_activity)
        box.addWidget(footer)
        return card

    @staticmethod
    def _document_tone(document) -> tuple[str, str]:
        text = f"{document.title} {document.source_kind} {document.source_name}".lower()
        if ".pdf" in text or "pdf" in text:
            return "PDF", RED
        if ".xlsx" in text or "excel" in text or "xlsx" in text:
            return "XLS", GREEN
        if ".ppt" in text or "powerpoint" in text:
            return "PPT", ORANGE
        if ".doc" in text or "word" in text or "docx" in text:
            return "DOC", BLUE
        return "FILE", TEAL

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
            row.setStyleSheet("QFrame{background:transparent;border:none;border-bottom:1px solid #F2F4F7;}")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(2, 9, 2, 9)
            layout.setSpacing(10)
            extension, tone = self._document_tone(document)
            file_icon = QLabel(extension)
            file_icon.setFixedSize(34, 38)
            file_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            file_icon.setStyleSheet(
                f"background:{tone};color:#FFFFFF;border:none;border-radius:7px;font-size:7px;font-weight:900;"
            )
            layout.addWidget(file_icon)
            copy = QVBoxLayout()
            copy.setSpacing(2)
            title = QLabel(document.title)
            title.setWordWrap(True)
            title.setStyleSheet(
                f"color:{INK};font-size:9px;font-weight:800;background:transparent;border:none;"
            )
            meta = QLabel(f"{document.source_kind or 'Document'} · Protected")
            meta.setStyleSheet(
                f"color:{MUTED};font-size:7.5px;background:transparent;border:none;"
            )
            copy.addWidget(title)
            copy.addWidget(meta)
            layout.addLayout(copy, 1)
            when = QLabel(_format_when(document.updated_at))
            when.setStyleSheet(
                f"color:{MUTED};font-size:7.5px;background:transparent;border:none;"
            )
            layout.addWidget(when)
            self.documents_layout.addWidget(row)
        self.documents_layout.addStretch(1)

    def _metric_row(self, icon_name: str, color: str, label: str, value: int) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 7, 0, 7)
        layout.setSpacing(9)
        marker = QLabel()
        marker.setPixmap(icon(icon_name, color=color, size=15).pixmap(15, 15))
        layout.addWidget(marker)
        name = QLabel(label)
        name.setStyleSheet(f"color:{TEXT};font-size:8px;background:transparent;border:none;")
        layout.addWidget(name, 1)
        number = QLabel(str(value))
        number.setStyleSheet(f"color:{INK};font-size:9px;font-weight:850;background:transparent;border:none;")
        layout.addWidget(number)
        return row

    def _render_privacy(self, documents, connected_count: int, activity_count: int) -> None:
        protected_count = len(documents)
        restorable = sum(1 for item in documents if item.has_mapping)
        mcp_shared = sum(1 for item in documents if item.mcp_shared)
        self.status_ring.set_value(100 if protected_count else 0, "PROTECTED" if protected_count else "READY")
        _clear_layout(self.status_metrics)
        self.status_metrics.addWidget(self._metric_row("document", BLUE, "Protected documents", protected_count))
        self.status_metrics.addWidget(self._metric_row("restore", ORANGE, "Restorable mappings", restorable))
        self.status_metrics.addWidget(self._metric_row("workflow", TEAL, "MCP-approved copies", mcp_shared))
        self.status_metrics.addWidget(self._metric_row("cloud", PURPLE, "Connected apps", connected_count))
        self.status_metrics.addWidget(self._metric_row("history", "#475467", "Recent activity", activity_count))
        self.status_metrics.addStretch(1)
        if protected_count:
            self.status_banner_text.setText("Your protected Library is ready for local use and approved workflows.")
        else:
            self.status_banner_text.setText("PrivacyGate is ready. Protect a document to start your local Library.")

    def _connected_apps(self) -> list[tuple[str, str]]:
        if self.apps_service is None:
            return []
        connected: list[tuple[str, str]] = []
        for key, title, _description, _icon_key, _category, supported, _path in APPS:
            if not supported:
                continue
            try:
                if self.apps_service.is_connected(key):
                    connected.append((key, title))
            except Exception:
                continue
        return connected

    def _render_apps(self, connected: list[tuple[str, str]]) -> None:
        _clear_layout(self.apps_layout)
        if not connected:
            empty = _muted("No apps are connected in this Personal workspace yet.", 9)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.apps_layout.addWidget(empty, 1)
            return

        for provider, title in connected[:6]:
            tile = QWidget()
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(0, 8, 0, 8)
            tile_layout.setSpacing(5)
            logo = QLabel()
            logo.setFixedSize(48, 48)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo.setPixmap(icon("cloud", color=BLUE, size=23).pixmap(23, 23))
            logo.setStyleSheet(
                "background:#FFFFFF;border:1px solid #E4E7EC;border-radius:11px;"
            )
            tile_layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)
            label = QLabel(title)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            label.setStyleSheet(
                f"color:{INK};font-size:7.5px;font-weight:750;background:transparent;border:none;"
            )
            tile_layout.addWidget(label)
            status = QLabel("● Connected")
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status.setStyleSheet(
                f"color:{GREEN};font-size:7px;font-weight:800;background:transparent;border:none;"
            )
            tile_layout.addWidget(status)
            self.apps_layout.addWidget(tile, 1)
            self.logo_loader.load(
                provider,
                lambda pixmap, target=logo: target.setPixmap(
                    pixmap.scaled(
                        30,
                        30,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                ),
            )
        self.apps_layout.addStretch(1)

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
            row.setStyleSheet("QFrame{background:transparent;border:none;border-bottom:1px solid #F2F4F7;}")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(2, 10, 2, 10)
            layout.setSpacing(10)
            marker = QLabel()
            marker.setPixmap(icon("history", color=tones[index % len(tones)], size=16).pixmap(16, 16))
            layout.addWidget(marker)
            label = QLabel(_friendly_event(str(event.get("event_type", ""))))
            label.setWordWrap(True)
            label.setStyleSheet(f"color:{TEXT};font-size:8px;background:transparent;border:none;")
            layout.addWidget(label, 1)
            when = QLabel(_format_when(event.get("created_at")))
            when.setStyleSheet(f"color:{MUTED};font-size:7.5px;background:transparent;border:none;")
            layout.addWidget(when)
            self.activity_layout.addWidget(row)
        self.activity_layout.addStretch(1)

    def refresh(self) -> None:
        try:
            documents = list(self.library.list_documents())
        except Exception:
            documents = []
        try:
            all_events = list(self.activity.recent(100))
            events = [
                item
                for item in all_events
                if str(item.get("workspace_key", "personal") or "personal") == "personal"
            ]
        except Exception:
            events = []
        connected = self._connected_apps()
        self._render_documents(documents)
        self._render_privacy(documents, len(connected), len(events))
        self._render_apps(connected)
        self._render_activity(events)


def _apply_sidebar_icon_colors(controller) -> None:
    for button in getattr(controller, "_buttons", []):
        raw = button.property("mockupFullText") or button.text()
        label = str(raw or "").replace("   ▾", "").replace("   ⌃", "").strip()
        spec = NAV_ICON_COLORS.get(label)
        if spec is None:
            continue
        icon_name, color = spec
        size = 15 if button.objectName() == "RedesignSubNavButton" else 18
        button.setIcon(icon(icon_name, color=color, size=size))
        button.setIconSize(QSize(size, size))


def _install_personal_navigation(main_window, page: MockupPersonalWorkspace) -> None:
    controller = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
    if controller is None:
        return
    original_rebuild = controller.rebuild

    def rebuild(self) -> None:
        original_rebuild()
        personal_index = _page_index(self.main_window, "personal_workspace_page")
        current = int(self.main_window.pages.currentIndex())
        team_index = _page_index(self.main_window, "team_page")

        if not self._is_organization() and personal_index >= 0:
            overview = QPushButton("Overview")
            overview.setObjectName("RedesignNavButton")
            overview.setCheckable(True)
            overview.setCursor(Qt.CursorShape.PointingHandCursor)
            overview.setIcon(icon("document", color=BLUE, size=18))
            overview.setIconSize(QSize(18, 18))
            overview.setStyleSheet(_NAV_STYLE)
            overview.clicked.connect(
                lambda _checked=False, index=personal_index: self.main_window._show_page(index)
            )
            self.nav_layout.insertWidget(0, overview)
            self._buttons.insert(0, overview)
            self._page_buttons[personal_index] = overview
            if current == team_index:
                QTimer.singleShot(0, lambda: self.main_window._show_page(personal_index))
        elif self._is_organization() and current == personal_index:
            QTimer.singleShot(0, lambda: self._open_org_tab(0))

        self._sync_checked_state()
        _apply_sidebar_icon_colors(self)

    controller.rebuild = MethodType(rebuild, controller)

    pages = getattr(main_window, "pages", None)
    if pages is not None:
        personal_index = pages.indexOf(page)
        pages.currentChanged.connect(
            lambda index: QTimer.singleShot(0, page.refresh) if index == personal_index else None
        )

    controller.rebuild()
    _apply_sidebar_icon_colors(controller)

    # Personal gets a real dashboard landing page. Organization keeps its existing
    # Organization Overview; operational pages remain unchanged when switching context.
    if not controller._is_organization():
        current = int(main_window.pages.currentIndex())
        protect_index = _page_index(main_window, "protection_page")
        if current == protect_index:
            QTimer.singleShot(0, lambda: main_window._show_page(main_window.pages.indexOf(page)))


def apply_mockup_personal_workspace_2026(main_window) -> None:
    if bool(getattr(main_window, "_privacygate_mockup_personal_workspace_2026", False)):
        return
    main_window._privacygate_mockup_personal_workspace_2026 = True

    if getattr(main_window, "personal_workspace_page", None) is None:
        page = MockupPersonalWorkspace(main_window)
        main_window.pages.addWidget(page)
        main_window.personal_workspace_page = page
    else:
        page = main_window.personal_workspace_page

    _install_personal_navigation(main_window, page)
