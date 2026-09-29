from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.public_links import (
    CHROME_EXTENSION_URL,
    EDGE_EXTENSION_URL,
    GMAIL_MARKETPLACE_URL,
    MICROSOFT_STORE_URL,
    PRIVACYGATE_WEBSITE_URL,
)
from ai_pm_lab_privacy_gate.ui.resources import resource_path


NAVY = "#062B4F"
PETROL = "#0B7180"
MUTED = "#526C7D"
BORDER = "#D7E2EA"
PAGE_BG = "#F7FAFC"


def _button_style(enabled: bool = True) -> str:
    if not enabled:
        return (
            "QPushButton{background:#F3F6F8;color:#98A6B0;border:1px solid #DFE7EC;"
            "border-radius:9px;padding:9px 14px;font-weight:750;}"
        )
    return (
        "QPushButton{background:#0B7180;color:#FFFFFF;border:1px solid #0B7180;"
        "border-radius:9px;padding:9px 14px;font-weight:800;}"
        "QPushButton:hover{background:#095F6B;border-color:#095F6B;}"
    )


class IntegrationLinksPage(QWidget):
    """Public add-ons, extensions and official PrivacyGate distribution links."""

    def __init__(self, main_window) -> None:
        super().__init__()
        self.main_window = main_window
        self.setStyleSheet(f"background:{PAGE_BG};")
        self._build_ui()

    def _open(self, url: str) -> None:
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _card(
        self,
        host: QVBoxLayout,
        *,
        title: str,
        description: str,
        status: str,
        button_text: str,
        url: str,
        note: str = "",
        image_name: str = "",
    ) -> None:
        card = QFrame(objectName="PrivacyGateDistributionCard")
        card.setStyleSheet(
            "QFrame#PrivacyGateDistributionCard{background:#FFFFFF;"
            f"border:1px solid {BORDER};border-radius:14px;}}"
        )
        body = QVBoxLayout(card)
        body.setContentsMargins(20, 18, 20, 18)
        body.setSpacing(9)

        top = QHBoxLayout()
        mark = QLabel()
        mark.setFixedSize(68, 68)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)

        image_path = (
            resource_path("resources", "integrations", image_name)
            if image_name
            else None
        )
        if image_path is not None and image_path.exists():
            pixmap = QPixmap(str(image_path))
            mark.setPixmap(
                pixmap.scaled(
                    62,
                    62,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            mark.setStyleSheet("background:#FFFFFF;border:none;")
        else:
            mark.setPixmap(icon("external", color=PETROL, size=24).pixmap(24, 24))
            mark.setStyleSheet(
                "background:#EAF7F7;border:1px solid #CDE8E8;border-radius:10px;"
            )
        top.addWidget(mark)

        names = QVBoxLayout()
        name = QLabel(title)
        name.setStyleSheet(f"color:{NAVY};font-size:15px;font-weight:900;")
        detail = QLabel(description)
        detail.setWordWrap(True)
        detail.setStyleSheet(f"color:{MUTED};font-size:10px;")
        names.addWidget(name)
        names.addWidget(detail)
        top.addLayout(names, 1)

        live = bool(url)
        badge = QLabel(status)
        badge.setStyleSheet(
            (
                "background:#E6F4EA;color:#137333;border:1px solid #CEEAD6;"
                if live
                else "background:#FFF6DF;color:#8B641C;border:1px solid #E8CE8A;"
            )
            + "border-radius:8px;padding:5px 8px;font-size:8px;font-weight:900;"
        )
        top.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
        body.addLayout(top)

        if note:
            note_label = QLabel(note)
            note_label.setWordWrap(True)
            note_label.setStyleSheet(f"color:{MUTED};font-size:9px;")
            body.addWidget(note_label)

        actions = QHBoxLayout()
        button = QPushButton(button_text)
        button.setIcon(icon("external", color="#FFFFFF" if live else "#98A6B0", size=16))
        button.setEnabled(live)
        button.setStyleSheet(_button_style(live))
        if live:
            button.clicked.connect(lambda _checked=False, target=url: self._open(target))
        actions.addWidget(button)
        actions.addStretch(1)
        body.addLayout(actions)

        host.addWidget(card)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(14)

        title = QLabel("Add-ons & Extensions")
        title.setStyleSheet(f"color:{NAVY};font-size:27px;font-weight:900;")
        root.addWidget(title)

        subtitle = QLabel(
            "Install PrivacyGate Desktop, the Gmail add-on and supported browser extensions. "
            "Official store links open in your default browser."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{MUTED};font-size:11px;")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        body = QWidget()
        body.setStyleSheet("background:transparent;")
        cards = QVBoxLayout(body)
        cards.setContentsMargins(0, 4, 6, 4)
        cards.setSpacing(12)

        self._card(
            cards,
            title="PrivacyGate Desktop",
            description="Official Windows distribution of the PrivacyGate Desktop application.",
            status="LIVE",
            button_text="Get from Microsoft Store",
            url=MICROSOFT_STORE_URL,
            image_name="get-microsoft-store.png",
        )
        self._card(
            cards,
            title="PrivacyGate for Gmail™",
            description="Google Workspace add-on for sending only the Gmail message you explicitly choose to PrivacyGate Desktop.",
            status="LIVE",
            button_text="Get Gmail add-on",
            url=GMAIL_MARKETPLACE_URL,
            note="Approved and published on Google Workspace Marketplace.",
            image_name="get-gmail-addon.png",
        )
        self._card(
            cards,
            title="PrivacyGate for Microsoft Edge",
            description="Browser Protection extension for pairing Edge with the local PrivacyGate Desktop bridge.",
            status="LIVE",
            button_text="Get Edge extension",
            url=EDGE_EXTENSION_URL,
            image_name="get-edge-extension.png",
        )
        self._card(
            cards,
            title="PrivacyGate for Chrome & Brave",
            description="Browser Protection extension distributed through the Chrome Web Store.",
            status="COMING NEXT",
            button_text="Open Chrome Web Store",
            url=CHROME_EXTENSION_URL,
            note="Brave uses Chrome Web Store extensions, so the same PrivacyGate listing will cover both browsers.",
        )
        self._card(
            cards,
            title="PrivacyGate website",
            description="Product information, documentation, legal information and Desktop download options.",
            status="LIVE",
            button_text="Open PrivacyGate website",
            url=PRIVACYGATE_WEBSITE_URL,
        )

        cards.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
