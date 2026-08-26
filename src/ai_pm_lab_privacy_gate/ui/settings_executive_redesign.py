from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.resources import resource_path

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
TEAL_BRIGHT = "#12A5A0"
MUTED = "#61798A"
BORDER = "#DDE7EC"
SOFT = "#F5F8FA"
WHITE = "#FFFFFF"
INDIGO = "#6757D8"
GREEN = "#23824B"


def _shadow(widget: QWidget, *, blur: int = 24, alpha: int = 24, y: int = 5) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    effect.setColor(QColor(6, 43, 79, alpha))
    widget.setGraphicsEffect(effect)


def _section_title(title: str, subtitle: str, icon_name: str) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(11)

    bubble = QLabel()
    bubble.setFixedSize(38, 38)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon(icon_name, color=TEAL, size=21).pixmap(21, 21))
    bubble.setStyleSheet(
        "background:#E9F7F7;border:1px solid #CFEAEA;border-radius:12px;"
    )
    layout.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignTop)

    copy = QVBoxLayout()
    copy.setSpacing(1)
    heading = QLabel(title)
    heading.setStyleSheet(
        f"color:{NAVY};font-size:16px;font-weight:900;border:none;background:transparent;"
    )
    note = QLabel(subtitle)
    note.setWordWrap(True)
    note.setStyleSheet(
        f"color:{MUTED};font-size:10px;border:none;background:transparent;"
    )
    copy.addWidget(heading)
    copy.addWidget(note)
    layout.addLayout(copy, 1)
    return row


def _pill(text: str, *, tone: str = "teal") -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    palettes = {
        "teal": ("#E7F7F7", TEAL, "#C9E9E9"),
        "navy": ("#EDF2F6", NAVY, "#D8E2E8"),
        "indigo": ("#F0EEFF", INDIGO, "#DCD7FF"),
        "green": ("#EAF8F1", GREEN, "#CDE8D9"),
    }
    bg, fg, border = palettes.get(tone, palettes["teal"])
    label.setStyleSheet(
        f"background:{bg};color:{fg};border:1px solid {border};border-radius:10px;"
        "padding:6px 10px;font-size:8px;font-weight:900;letter-spacing:.4px;"
    )
    return label


def _module_card(title: str, detail: str, icon_name: str, *, accent: str = TEAL) -> QFrame:
    card = QFrame()
    card.setObjectName("ExecutiveModuleCard")
    card.setStyleSheet(
        "QFrame#ExecutiveModuleCard{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:17px;}"
    )
    box = QVBoxLayout(card)
    box.setContentsMargins(18, 17, 18, 17)
    box.setSpacing(9)

    head = QHBoxLayout()
    bubble = QLabel()
    bubble.setFixedSize(42, 42)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon(icon_name, color=accent, size=23).pixmap(23, 23))
    bubble.setStyleSheet(
        f"background:{'#EEF7F8' if accent == TEAL else '#F0EEFF'};"
        "border:none;border-radius:13px;"
    )
    head.addWidget(bubble)
    head.addStretch(1)
    box.addLayout(head)

    name = QLabel(title)
    name.setStyleSheet(
        f"color:{NAVY};font-size:14px;font-weight:900;border:none;background:transparent;"
    )
    note = QLabel(detail)
    note.setWordWrap(True)
    note.setStyleSheet(
        f"color:{MUTED};font-size:9px;border:none;background:transparent;"
    )
    box.addWidget(name)
    box.addWidget(note)
    return card


def _find_settings_card(settings: QWidget, heading: str) -> QFrame | None:
    for frame in settings.findChildren(QFrame):
        if frame.objectName() != "SettingsPremiumCard":
            continue
        for label in frame.findChildren(QLabel):
            if label.text().strip() == heading:
                return frame
    return None


def _find_button(root: QWidget, text: str) -> QPushButton | None:
    for button in root.findChildren(QPushButton):
        if button.text().strip() == text:
            return button
    return None


def _clear_layout(layout, keep: set[QWidget]) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            if widget not in keep:
                widget.deleteLater()
        elif child is not None:
            _clear_layout(child, keep)


def _restyle_existing_cards(settings: QWidget) -> None:
    for frame in settings.findChildren(QFrame):
        if frame.objectName() == "SettingsPremiumCard":
            frame.setStyleSheet(
                "QFrame#SettingsPremiumCard{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:17px;}"
            )
            frame.setMinimumHeight(max(150, frame.minimumHeight()))

    account = getattr(settings, "_privacygate_plan_account_panel", None)
    if isinstance(account, QFrame):
        account.setStyleSheet(
            "QFrame#CurrentAccountPanel{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:18px;}"
        )
        update = _find_button(account, "Update plan")
        if update is not None:
            update.setIcon(icon("external", color=WHITE, size=16))
            update.setIconSize(QSize(16, 16))
            update.setMinimumHeight(40)
            update.setStyleSheet(
                "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:11px;"
                "padding:9px 15px;font-size:10px;font-weight:850;}"
                "QPushButton:hover{background:#096D76;}"
            )

    workspace = getattr(settings, "_privacygate_workspace_settings_panel", None)
    if isinstance(workspace, QFrame):
        workspace.setStyleSheet(
            "QFrame#WorkspaceSettingsPanel{background:#FFFFFF;border:1px solid #D9E6EA;border-radius:19px;}"
        )
        current = workspace.findChild(QFrame, "WorkspaceCurrentCard")
        if current is not None:
            current.setStyleSheet(
                "QFrame#WorkspaceCurrentCard{background:#F5FAFB;border:1px solid #D9EBED;border-radius:14px;}"
            )
        add = workspace.findChild(QFrame, "WorkspaceAddCard")
        if add is not None:
            add.setStyleSheet(
                "QFrame#WorkspaceAddCard{background:#FBFAFF;border:1px solid #E3DFFF;border-radius:14px;}"
            )
        for button in workspace.findChildren(QPushButton):
            text = button.text().lower()
            if "use selected" in text:
                button.setIcon(icon("check", color=WHITE, size=16))
            elif "refresh" in text:
                button.setIcon(icon("restore", color=NAVY, size=16))
            elif "join" in text:
                button.setIcon(icon("external", color=WHITE, size=16))
            elif "create" in text:
                button.setIcon(icon("workflow", color=NAVY, size=16))
            button.setIconSize(QSize(16, 16))
            button.setMinimumHeight(max(40, button.minimumHeight()))


def _build_files_future_card() -> QFrame:
    card = _module_card(
        "Local workspace & files",
        "A dedicated home for local folder access, storage controls and safe file operations. The interface is reserved now so these capabilities can be added without cluttering the rest of Settings.",
        "library",
        accent=INDIGO,
    )
    box = card.layout()
    if isinstance(box, QVBoxLayout):
        head = QHBoxLayout()
        head.addWidget(_pill("NEXT MODULE", tone="indigo"))
        head.addStretch(1)
        box.insertLayout(1, head)
        detail = QLabel(
            "Planned surface  •  folder permissions  •  create / move / rename  •  safe delete  •  storage  •  open terminal in folder"
        )
        detail.setWordWrap(True)
        detail.setStyleSheet(
            "background:#F6F4FF;color:#5E55A5;border:1px solid #E6E1FF;border-radius:10px;"
            "padding:9px;font-size:8px;font-weight:700;"
        )
        box.addWidget(detail)
    return card


def apply_settings_executive_redesign(main_window) -> None:
    """Recompose Settings as a scalable executive control center.

    Existing controls are reparented, not recreated, so their signals and storage
    behavior remain intact. The layout deliberately leaves a first-class home for
    upcoming local file/folder management without implementing those operations yet.
    """
    settings = getattr(main_window, "settings_page", None)
    if settings is None or bool(getattr(settings, "_privacygate_executive_settings", False)):
        return

    root = settings.layout()
    if not isinstance(root, QVBoxLayout):
        return

    account = getattr(settings, "_privacygate_plan_account_panel", None)
    workspace = getattr(settings, "_privacygate_workspace_settings_panel", None)
    desktop = _find_settings_card(settings, "Desktop behavior")
    privacy = _find_settings_card(settings, "Local-first privacy boundary")
    mcp = _find_settings_card(settings, "Local MCP service")
    updates = _find_settings_card(settings, "Updates & release channel")
    save = _find_button(settings, "Save settings")

    preserved = {
        widget
        for widget in (account, workspace, desktop, privacy, mcp, updates, save)
        if isinstance(widget, QWidget)
    }
    if not preserved:
        return

    # Detach functional surfaces before replacing only the page composition.
    for widget in preserved:
        widget.setParent(settings)
    _clear_layout(root, preserved)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    scroll = QScrollArea(settings)
    scroll.setObjectName("ExecutiveSettingsScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    content = QWidget()
    content.setObjectName("ExecutiveSettingsContent")
    body = QVBoxLayout(content)
    body.setContentsMargins(30, 25, 30, 28)
    body.setSpacing(22)
    scroll.setWidget(content)
    root.addWidget(scroll)

    # Executive header with PrivacyGate branding.
    hero = QFrame(objectName="ExecutiveSettingsHero")
    hero.setStyleSheet(
        "QFrame#ExecutiveSettingsHero{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        "stop:0 #062B4F,stop:.62 #084C68,stop:1 #0B7F89);border:none;border-radius:21px;}"
    )
    hero_box = QHBoxLayout(hero)
    hero_box.setContentsMargins(22, 20, 22, 20)
    hero_box.setSpacing(15)

    brand = QLabel()
    brand.setFixedSize(54, 54)
    brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
    logo_path = resource_path("resources", "branding", "privacy-gate-icon.png")
    if logo_path.exists():
        pixmap = QPixmap(str(logo_path))
        brand.setPixmap(
            pixmap.scaled(
                42,
                42,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    else:
        brand.setPixmap(icon("settings", color=WHITE, size=28).pixmap(28, 28))
    brand.setStyleSheet("background:rgba(255,255,255,28);border:1px solid rgba(255,255,255,45);border-radius:15px;")
    hero_box.addWidget(brand, alignment=Qt.AlignmentFlag.AlignTop)

    copy = QVBoxLayout()
    copy.setSpacing(3)
    eyebrow = QLabel("PRIVACYGATE CONTROL CENTER")
    eyebrow.setStyleSheet(
        "color:#9FE5E2;font-size:8px;font-weight:900;letter-spacing:1.2px;border:none;background:transparent;"
    )
    title = QLabel("Settings")
    title.setStyleSheet("color:#FFFFFF;font-size:29px;font-weight:950;border:none;background:transparent;")
    subtitle = QLabel(
        "Account, workspaces, device behavior and local services — organized for the controls PrivacyGate is adding next."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet("color:#D9EEF1;font-size:11px;border:none;background:transparent;")
    copy.addWidget(eyebrow)
    copy.addWidget(title)
    copy.addWidget(subtitle)
    hero_box.addLayout(copy, 1)

    status = QVBoxLayout()
    status.setSpacing(7)
    status.addWidget(_pill("LOCAL DEVICE", tone="navy"))
    status.addWidget(_pill("PRIVACY FIRST", tone="teal"))
    hero_box.addLayout(status)
    _shadow(hero, blur=30, alpha=35, y=7)
    body.addWidget(hero)

    module_strip = QFrame(objectName="SettingsModuleStrip")
    module_strip.setStyleSheet(
        "QFrame#SettingsModuleStrip{background:#FFFFFF;border:1px solid #E0E8ED;border-radius:15px;}"
    )
    strip = QHBoxLayout(module_strip)
    strip.setContentsMargins(12, 9, 12, 9)
    strip.setSpacing(8)
    for label, icon_name in (
        ("Account", "contact"),
        ("Workspaces", "workflow"),
        ("Device", "settings"),
        ("Services", "cloud"),
        ("Files", "library"),
        ("Updates", "download"),
    ):
        item = QFrame()
        row = QHBoxLayout(item)
        row.setContentsMargins(8, 5, 8, 5)
        row.setSpacing(6)
        ico = QLabel()
        ico.setPixmap(icon(icon_name, color=TEAL, size=15).pixmap(15, 15))
        text = QLabel(label)
        text.setStyleSheet(f"color:{INK};font-size:9px;font-weight:800;border:none;")
        row.addWidget(ico)
        row.addWidget(text)
        strip.addWidget(item)
    strip.addStretch(1)
    body.addWidget(module_strip)

    # Identity & access.
    body.addWidget(
        _section_title(
            "Identity & access",
            "Your plan and the workspace context that determines where PrivacyGate is operating.",
            "contact",
        )
    )
    if isinstance(account, QWidget):
        body.addWidget(account)
    if isinstance(workspace, QWidget):
        body.addWidget(workspace)

    # Device & privacy.
    body.addWidget(
        _section_title(
            "Device & privacy",
            "Control desktop behavior while keeping PrivacyGate's local privacy boundary explicit.",
            "protect",
        )
    )
    device_row = QHBoxLayout()
    device_row.setSpacing(16)
    if isinstance(desktop, QWidget):
        device_row.addWidget(desktop, 1)
    if isinstance(privacy, QWidget):
        device_row.addWidget(privacy, 1)
    body.addLayout(device_row)

    # Local services + future file/folder controls.
    body.addWidget(
        _section_title(
            "Local services & files",
            "Runtime controls today, with a reserved module for the upcoming safe local workspace and folder-management layer.",
            "workflow",
        )
    )
    services_row = QHBoxLayout()
    services_row.setSpacing(16)
    if isinstance(mcp, QWidget):
        services_row.addWidget(mcp, 1)
    services_row.addWidget(_build_files_future_card(), 1)
    body.addLayout(services_row)

    # Product lifecycle.
    body.addWidget(
        _section_title(
            "Product & maintenance",
            "Release controls stay separate from privacy, workspace and local automation settings.",
            "download",
        )
    )
    if isinstance(updates, QWidget):
        body.addWidget(updates)

    # Save bar reuses the original functional button / signal.
    save_bar = QFrame(objectName="ExecutiveSaveBar")
    save_bar.setStyleSheet(
        "QFrame#ExecutiveSaveBar{background:#062B4F;border:none;border-radius:16px;}"
    )
    save_row = QHBoxLayout(save_bar)
    save_row.setContentsMargins(16, 12, 14, 12)
    save_row.setSpacing(12)
    save_icon = QLabel()
    save_icon.setPixmap(icon("save", color="#9FE5E2", size=19).pixmap(19, 19))
    save_row.addWidget(save_icon)
    save_copy = QLabel("Desktop and local-service changes are stored on this device.")
    save_copy.setStyleSheet("color:#DDEEF1;font-size:9px;font-weight:700;border:none;background:transparent;")
    save_row.addWidget(save_copy, 1)
    if isinstance(save, QPushButton):
        save.setIcon(icon("save", color=WHITE, size=17))
        save.setIconSize(QSize(17, 17))
        save.setMinimumHeight(42)
        save.setStyleSheet(
            "QPushButton{background:#12A5A0;color:#FFFFFF;border:none;border-radius:11px;"
            "padding:10px 18px;font-size:10px;font-weight:900;}"
            "QPushButton:hover{background:#19B7B0;}QPushButton:pressed{background:#0E8C88;}"
        )
        save_row.addWidget(save)
    body.addWidget(save_bar)

    content.setStyleSheet(
        "QWidget#ExecutiveSettingsContent{background:#F4F7F9;}"
        "QWidget#ExecutiveSettingsContent QLabel{background:transparent;}"
        "QScrollArea#ExecutiveSettingsScroll{background:#F4F7F9;border:none;}"
    )

    _restyle_existing_cards(settings)
    settings._privacygate_executive_settings = True
