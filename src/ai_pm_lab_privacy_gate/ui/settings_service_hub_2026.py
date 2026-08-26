from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
WHITE = "#FFFFFF"
INDIGO = "#6757D8"
GREEN = "#23824B"
AMBER = "#B7791F"


class _ServiceCard(QFrame):
    clicked = Signal()

    def __init__(
        self,
        title: str,
        detail: str,
        icon_name: str,
        status: str,
        *,
        accent: str = TEAL,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Settings2026ServiceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(132)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(title)
        self.setToolTip(f"Open {title} settings")
        self._accent = accent
        self._apply_style(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 15, 16, 14)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        bubble = QLabel()
        bubble.setFixedSize(44, 44)
        bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble.setPixmap(icon(icon_name, color=accent, size=23).pixmap(23, 23))
        bubble.setStyleSheet(
            f"background:{'#EAF8F8' if accent == TEAL else '#F1EFFF'};"
            "border:none;border-radius:14px;"
        )
        bubble.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        top.addWidget(bubble)
        top.addStretch(1)

        badge = QLabel(status)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if status == "NEXT":
            badge.setStyleSheet(
                "background:#FFF6E8;color:#9A641D;border:1px solid #F0D9B3;border-radius:9px;"
                "padding:5px 8px;font-size:8px;font-weight:900;letter-spacing:.5px;"
            )
        elif status in {"ACTIVE", "READY"}:
            badge.setStyleSheet(
                "background:#EAF8F1;color:#23824B;border:1px solid #CBE9D8;border-radius:9px;"
                "padding:5px 8px;font-size:8px;font-weight:900;letter-spacing:.5px;"
            )
        else:
            badge.setStyleSheet(
                "background:#EEF4F7;color:#476475;border:1px solid #D8E3E9;border-radius:9px;"
                "padding:5px 8px;font-size:8px;font-weight:900;letter-spacing:.5px;"
            )
        top.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(top)

        title_label = QLabel(title)
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title_label.setStyleSheet(
            f"color:{NAVY};font-size:14px;font-weight:900;border:none;background:transparent;"
        )
        root.addWidget(title_label)

        detail_label = QLabel(detail)
        detail_label.setWordWrap(True)
        detail_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        detail_label.setStyleSheet(
            f"color:{MUTED};font-size:9px;border:none;background:transparent;"
        )
        root.addWidget(detail_label, 1)

        action = QLabel("Open controls   →")
        action.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        action.setStyleSheet(
            f"color:{accent};font-size:9px;font-weight:900;border:none;background:transparent;"
        )
        root.addWidget(action)

    def _apply_style(self, hover: bool) -> None:
        if hover:
            self.setStyleSheet(
                "QFrame#Settings2026ServiceCard{background:#FFFFFF;border:2px solid #8FC8CD;"
                "border-radius:18px;}"
            )
        else:
            self.setStyleSheet(
                "QFrame#Settings2026ServiceCard{background:#FFFFFF;border:1px solid #DDE7EC;"
                "border-radius:18px;}"
            )

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._apply_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._apply_style(False)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}:
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


def _find_card(settings: QWidget, heading: str) -> QFrame | None:
    for frame in settings.findChildren(QFrame):
        for label in frame.findChildren(QLabel):
            if label.text().strip() == heading:
                return frame
    return None


def _find_future_files(settings: QWidget) -> QFrame | None:
    for frame in settings.findChildren(QFrame):
        for label in frame.findChildren(QLabel):
            if label.text().strip() == "Local workspace & files":
                return frame
    return None


def _scroll_to(scroll: QScrollArea, target: QWidget | None) -> None:
    if target is None:
        return
    target.show()
    scroll.ensureWidgetVisible(target, 30, 90)
    QTimer.singleShot(80, lambda: scroll.ensureWidgetVisible(target, 30, 90))


def _service_card(
    spec: tuple[str, str, str, str, str],
    target: QWidget | None,
    scroll: QScrollArea,
) -> _ServiceCard:
    title, detail, icon_name, status, accent = spec
    card = _ServiceCard(title, detail, icon_name, status, accent=accent)
    card.setEnabled(target is not None)
    if target is None:
        card.setToolTip(f"{title} module is not available in this build")
    else:
        card.clicked.connect(lambda: _scroll_to(scroll, target))
    return card


def apply_settings_service_hub_2026(main_window) -> None:
    """Turn the small Settings module strip into a visible, clickable service hub.

    This is navigation/presentation only. Existing Account, Workspace, Device,
    service, file-roadmap and update widgets remain the functional source of truth.
    """
    settings = getattr(main_window, "settings_page", None)
    if settings is None or bool(getattr(settings, "_privacygate_service_hub_2026", False)):
        return

    scroll = settings.findChild(QScrollArea, "ExecutiveSettingsScroll")
    content = settings.findChild(QWidget, "ExecutiveSettingsContent")
    old_strip = settings.findChild(QFrame, "SettingsModuleStrip")
    if scroll is None or content is None or old_strip is None:
        return
    body = content.layout()
    if not isinstance(body, QVBoxLayout):
        return

    account = getattr(settings, "_privacygate_plan_account_panel", None)
    workspaces = getattr(settings, "_privacygate_workspace_settings_panel", None)
    device = _find_card(settings, "Desktop behavior")
    services = _find_card(settings, "Local MCP service")
    files = _find_future_files(settings)
    updates = _find_card(settings, "Updates & release channel")

    hub = QFrame(objectName="Settings2026Hub")
    hub.setStyleSheet(
        "QFrame#Settings2026Hub{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        "stop:0 #F9FBFC,stop:1 #F2F8F8);border:1px solid #DDE7EC;border-radius:20px;}"
    )
    hub_box = QVBoxLayout(hub)
    hub_box.setContentsMargins(18, 17, 18, 18)
    hub_box.setSpacing(13)

    head = QHBoxLayout()
    copy = QVBoxLayout()
    copy.setSpacing(2)
    eyebrow = QLabel("CONTROL MODULES")
    eyebrow.setStyleSheet(
        "color:#0B7F89;font-size:8px;font-weight:900;letter-spacing:1px;border:none;background:transparent;"
    )
    title = QLabel("Choose what you want to manage")
    title.setStyleSheet(
        "color:#062B4F;font-size:18px;font-weight:950;border:none;background:transparent;"
    )
    subtitle = QLabel(
        "Each area opens its own controls. Nothing is hidden behind a generic Settings page."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(
        "color:#61798A;font-size:10px;border:none;background:transparent;"
    )
    copy.addWidget(eyebrow)
    copy.addWidget(title)
    copy.addWidget(subtitle)
    head.addLayout(copy, 1)

    hint = QLabel("CLICK A MODULE")
    hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hint.setStyleSheet(
        "background:#E8F7F7;color:#0B7F89;border:1px solid #C7E8E8;border-radius:10px;"
        "padding:7px 10px;font-size:8px;font-weight:900;letter-spacing:.5px;"
    )
    head.addWidget(hint, 0, Qt.AlignmentFlag.AlignTop)
    hub_box.addLayout(head)

    grid = QGridLayout()
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(12)
    specs = (
        (("Account", "Profile, plan, entitlement and account-level controls.", "contact", "ACTIVE", TEAL), account),
        (("Workspaces", "Switch, join or create company workspaces and managed contexts.", "workflow", "ACTIVE", TEAL), workspaces),
        (("Device", "Desktop behavior and the local privacy boundary for this computer.", "settings", "LOCAL", NAVY), device),
        (("Services", "Local MCP runtime and service controls used by PrivacyGate.", "cloud", "LOCAL", TEAL), services),
        (("Files", "Local folders, storage and the upcoming safe file-operation control surface.", "library", "NEXT", INDIGO), files),
        (("Updates", "Release channel, update checks and product maintenance controls.", "download", "READY", GREEN), updates),
    )
    cards: dict[str, _ServiceCard] = {}
    for index, (spec, target) in enumerate(specs):
        card = _service_card(spec, target, scroll)
        grid.addWidget(card, index // 3, index % 3)
        cards[spec[0].lower()] = card
    for column in range(3):
        grid.setColumnStretch(column, 1)
    hub_box.addLayout(grid)

    old_index = body.indexOf(old_strip)
    if old_index < 0:
        return
    body.removeWidget(old_strip)
    old_strip.hide()
    body.insertWidget(old_index, hub)

    settings.settings_service_cards = cards
    settings.settings_service_hub_2026 = hub
    settings._privacygate_service_hub_2026 = True
