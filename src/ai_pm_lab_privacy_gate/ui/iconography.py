from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QTabWidget, QWidget

INK = "#17384e"
TEAL = "#078c89"


def icon(name: str, *, color: str = INK, size: int = 20) -> QIcon:
    """PrivacyGate's single outline-icon language, drawn locally with Qt."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidthF(max(1.5, size / 11.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    s = size / 20.0

    def pt(x: float, y: float) -> QPointF:
        return QPointF(x * s, y * s)

    def rc(x: float, y: float, w: float, h: float) -> QRectF:
        return QRectF(x * s, y * s, w * s, h * s)

    def rounded(x: float, y: float, w: float, h: float, radius: float = 1.4) -> None:
        painter.drawRoundedRect(rc(x, y, w, h), radius * s, radius * s)

    if name == "protect":
        path = QPainterPath(pt(10, 2))
        path.lineTo(pt(17, 5)); path.lineTo(pt(16, 12))
        path.cubicTo(pt(15.3, 15), pt(12.6, 17.3), pt(10, 18.3))
        path.cubicTo(pt(7.4, 17.3), pt(4.7, 15), pt(4, 12))
        path.lineTo(pt(3, 5)); path.closeSubpath(); painter.drawPath(path)
        painter.drawLine(pt(7, 10), pt(9, 12)); painter.drawLine(pt(9, 12), pt(13.5, 7.5))
    elif name in {"restore", "history"}:
        painter.drawArc(rc(4, 4, 12, 12), 25 * 16, 300 * 16)
        painter.drawLine(pt(4.5, 4), pt(4.5, 8)); painter.drawLine(pt(4.5, 4), pt(8.5, 4))
        if name == "history":
            painter.drawLine(pt(10, 7), pt(10, 11)); painter.drawLine(pt(10, 11), pt(13, 11))
    elif name == "upload":
        painter.drawLine(pt(10, 13), pt(10, 4)); painter.drawLine(pt(6.5, 7.5), pt(10, 4)); painter.drawLine(pt(13.5, 7.5), pt(10, 4)); rounded(4, 12, 12, 5)
    elif name == "download":
        painter.drawLine(pt(10, 4), pt(10, 13)); painter.drawLine(pt(6.5, 9.5), pt(10, 13)); painter.drawLine(pt(13.5, 9.5), pt(10, 13)); rounded(4, 14, 12, 3, 1)
    elif name == "document":
        path = QPainterPath(pt(5, 2.5)); path.lineTo(pt(12, 2.5)); path.lineTo(pt(16, 6.5)); path.lineTo(pt(16, 17.5)); path.lineTo(pt(5, 17.5)); path.closeSubpath(); painter.drawPath(path)
        painter.drawLine(pt(12, 2.5), pt(12, 6.5)); painter.drawLine(pt(12, 6.5), pt(16, 6.5)); painter.drawLine(pt(7.5, 10), pt(13.5, 10)); painter.drawLine(pt(7.5, 13), pt(13.5, 13))
    elif name == "paste":
        rounded(5, 4, 10, 13); rounded(7, 2.5, 6, 3, 1); painter.drawLine(pt(7.5, 9), pt(12.5, 9)); painter.drawLine(pt(7.5, 12), pt(12.5, 12))
    elif name == "scan":
        for a, b in (((3,7),(3,3)),((3,3),(7,3)),((13,3),(17,3)),((17,3),(17,7)),((3,13),(3,17)),((3,17),(7,17)),((13,17),(17,17)),((17,17),(17,13))): painter.drawLine(pt(*a), pt(*b))
        painter.drawEllipse(rc(7, 7, 6, 6)); painter.drawLine(pt(11.5, 11.5), pt(14.2, 14.2))
    elif name == "clear":
        painter.drawEllipse(rc(3, 3, 14, 14)); painter.drawLine(pt(6, 6), pt(14, 14)); painter.drawLine(pt(14, 6), pt(6, 14))
    elif name == "copy":
        rounded(6, 5, 9, 11); rounded(3, 2, 9, 11)
    elif name == "compare":
        rounded(2.5, 4, 6.5, 12); rounded(11, 4, 6.5, 12); painter.drawLine(pt(9.5, 8), pt(10.5, 8)); painter.drawLine(pt(9.5, 12), pt(10.5, 12))
    elif name == "library":
        rounded(3, 5, 14, 11); painter.drawLine(pt(4, 7.5), pt(16, 7.5)); painter.drawLine(pt(7, 3.5), pt(12, 3.5))
    elif name == "settings":
        painter.drawEllipse(rc(7, 7, 6, 6))
        for a, b in (((10,2),(10,5)),((10,15),(10,18)),((2,10),(5,10)),((15,10),(18,10)),((4.3,4.3),(6.4,6.4)),((13.6,13.6),(15.7,15.7)),((13.6,6.4),(15.7,4.3)),((4.3,15.7),(6.4,13.6))): painter.drawLine(pt(*a), pt(*b))
    elif name == "template":
        rounded(3, 3, 14, 14); painter.drawLine(pt(3, 8), pt(17, 8)); painter.drawLine(pt(9, 8), pt(9, 17))
    elif name == "report":
        painter.drawLine(pt(4, 16), pt(16, 16)); painter.drawLine(pt(5, 16), pt(5, 10)); painter.drawLine(pt(9, 16), pt(9, 6)); painter.drawLine(pt(13, 16), pt(13, 3))
    elif name == "workflow":
        painter.drawEllipse(rc(2.5, 7.5, 5, 5)); painter.drawEllipse(rc(12.5, 2.5, 5, 5)); painter.drawEllipse(rc(12.5, 12.5, 5, 5)); painter.drawLine(pt(7.5, 10), pt(11, 5.5)); painter.drawLine(pt(7.5, 10), pt(11, 14.5))
    elif name == "cloud":
        path = QPainterPath(pt(6, 15)); path.cubicTo(pt(3, 15), pt(2.5, 11), pt(5, 10)); path.cubicTo(pt(5, 6), pt(10, 5), pt(12, 8)); path.cubicTo(pt(16, 7), pt(18, 10), pt(16.5, 13)); path.cubicTo(pt(16, 14.5), pt(14.5, 15), pt(13, 15)); painter.drawPath(path)
    elif name == "contact":
        rounded(3, 4, 14, 10, 1.8); painter.drawLine(pt(6, 14), pt(5, 17)); painter.drawLine(pt(6, 14), pt(9, 14)); painter.drawLine(pt(6, 8), pt(14, 8)); painter.drawLine(pt(6, 11), pt(11, 11))
    elif name == "save":
        rounded(3, 3, 14, 14); rounded(6, 3, 7, 5, .8); rounded(6, 11, 8, 6, 1)
    elif name == "external":
        rounded(3, 6, 11, 11); painter.drawLine(pt(10, 3), pt(17, 3)); painter.drawLine(pt(17, 3), pt(17, 10)); painter.drawLine(pt(17, 3), pt(9, 11))
    elif name == "expand":
        for a, b in (((4,8),(4,4)),((4,4),(8,4)),((12,4),(16,4)),((16,4),(16,8)),((4,12),(4,16)),((4,16),(8,16)),((12,16),(16,16)),((16,16),(16,12))): painter.drawLine(pt(*a), pt(*b))
    elif name == "power":
        painter.drawArc(rc(4, 4, 12, 12), 40 * 16, 280 * 16); painter.drawLine(pt(10, 2), pt(10, 9))
    elif name == "check":
        painter.drawEllipse(rc(3, 3, 14, 14)); painter.drawLine(pt(6.5, 10), pt(9, 12.5)); painter.drawLine(pt(9, 12.5), pt(14, 7.5))
    else:
        painter.drawEllipse(rc(4, 4, 12, 12))

    painter.end()
    return QIcon(pixmap)


def _icon_for_text(text: str) -> str | None:
    text = " ".join(text.lower().replace("&", " ").split())
    exact = {
        "protect": "protect", "restore": "restore", "history": "history", "templates": "template",
        "settings": "settings", "local library": "library", "library": "library", "reports": "report",
        "document": "document", "paste text": "paste", "compare": "compare", "protected text": "protect",
        "clear": "clear", "scan": "scan", "scan locally": "scan", "upload": "upload", "upload file": "upload",
        "upload document": "upload", "save": "save", "save to library": "save", "restore locally": "restore",
        "full document view": "expand", "full screen preview": "expand",
    }
    if text in exact:
        return exact[text]
    for needle, key in (
        ("upload", "upload"), ("download", "download"), ("save", "save"), ("copy", "copy"),
        ("protect", "protect"), ("scan", "scan"), ("restore", "restore"), ("library", "library"),
        ("clear", "clear"), ("delete", "clear"), ("setting", "settings"), ("history", "history"),
        ("report", "report"), ("template", "template"), ("workflow", "workflow"), ("automation", "workflow"),
        ("mcp", "workflow"), ("cloud", "cloud"), ("email", "contact"), ("contact", "contact"),
        ("chatgpt", "external"), ("website", "external"), ("store", "external"), ("open", "external"),
        ("full", "expand"), ("paste", "paste"), ("document", "document"), ("file", "document"),
        ("compare", "compare"), ("quit", "power"), ("check", "check"),
    ):
        if needle in text:
            return key
    return None


def apply_iconography(root: QWidget) -> None:
    """Apply professional, consistent icons to existing controls without changing behavior."""
    for button in root.findChildren(QAbstractButton):
        key = _icon_for_text(button.text())
        if key:
            button.setIcon(icon(key, size=18))
            button.setIconSize(QSize(18, 18))

    for tabs in root.findChildren(QTabWidget):
        for index in range(tabs.count()):
            key = _icon_for_text(tabs.tabText(index))
            if key:
                tabs.setTabIcon(index, icon(key, color=TEAL, size=17))

    navigation = {
        "Protect": "protect", "Library": "library", "Restore": "restore",
        "Local Automation / n8n": "workflow", "Cloud / MCP / Email": "cloud",
        "Settings": "settings", "Contact / Workflows": "contact",
        "History": "history", "Templates": "template", "Local Library": "library", "Reports": "report",
    }
    for button in root.findChildren(QAbstractButton):
        key = navigation.get(button.text())
        if key:
            button.setIcon(icon(key, color="#dceff4", size=20))
            button.setIconSize(QSize(20, 20))
