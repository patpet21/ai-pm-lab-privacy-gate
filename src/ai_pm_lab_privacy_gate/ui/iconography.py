from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QTabWidget, QWidget


INK = "#17384e"
TEAL = "#078c89"


def _icon(name: str, color: str = INK, size: int = 20) -> QIcon:
    """Draw a compact, consistent outline icon without external assets.

    The shapes intentionally use one visual language: rounded line caps,
    1.8px-equivalent strokes and no fills except small status accents.
    """
    scale = max(1, size)
    pixmap = QPixmap(scale, scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color)
    pen.setWidthF(max(1.5, scale / 11.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    s = scale / 20.0
    def pt(x: float, y: float) -> QPointF:
        return QPointF(x * s, y * s)
    def rect(x: float, y: float, w: float, h: float) -> QRectF:
        return QRectF(x * s, y * s, w * s, h * s)

    if name in {"shield", "protect"}:
        path = QPainterPath(pt(10, 2))
        path.lineTo(pt(17, 5))
        path.lineTo(pt(16, 12))
        path.cubicTo(pt(15.4, 15), pt(12.6, 17.5), pt(10, 18.5))
        path.cubicTo(pt(7.4, 17.5), pt(4.6, 15), pt(4, 12))
        path.lineTo(pt(3, 5))
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(pt(7, 10), pt(9, 12))
        p.drawLine(pt(9, 12), pt(13.5, 7.5))
    elif name == "restore":
        p.drawArc(rect(4, 4, 12, 12), 35 * 16, 285 * 16)
        p.drawLine(pt(4.5, 4), pt(4.5, 8))
        p.drawLine(pt(4.5, 4), pt(8.5, 4))
        p.drawLine(pt(10, 7), pt(10, 11))
        p.drawLine(pt(10, 11), pt(13, 12.5))
    elif name == "upload":
        p.drawLine(pt(10, 13), pt(10, 4))
        p.drawLine(pt(6.5, 7.5), pt(10, 4))
        p.drawLine(pt(13.5, 7.5), pt(10, 4))
        p.drawRoundedRect(rect(4, 12, 12, 5), 1.5 * s, 1.5 * s)
    elif name == "download":
        p.drawLine(pt(10, 4), pt(10, 13))
        p.drawLine(pt(6.5, 9.5), pt(10, 13))
        p.drawLine(pt(13.5, 9.5), pt(10, 13))
        p.drawRoundedRect(rect(4, 14, 12, 3), 1.2 * s, 1.2 * s)
    elif name in {"document", "file"}:
        path = QPainterPath(pt(5, 2.5))
        path.lineTo(pt(12, 2.5))
        path.lineTo(pt(16, 6.5))
        path.lineTo(pt(16, 17.5))
        path.lineTo(pt(5, 17.5))
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(pt(12, 2.5), pt(12, 6.5))
        p.drawLine(pt(12, 6.5), pt(16, 6.5))
        p.drawLine(pt(7.5, 10), pt(13.5, 10))
        p.drawLine(pt(7.5, 13), pt(13.5, 13))
    elif name == "paste":
        p.drawRoundedRect(rect(5, 4, 10, 13), 1.5 * s, 1.5 * s)
        p.drawRoundedRect(rect(7, 2.5, 6, 3), 1.2 * s, 1.2 * s)
        p.drawLine(pt(7.5, 9), pt(12.5, 9))
        p.drawLine(pt(7.5, 12), pt(12.5, 12))
    elif name == "scan":
        p.drawLine(pt(3, 7), pt(3, 3)); p.drawLine(pt(3, 3), pt(7, 3))
        p.drawLine(pt(13, 3), pt(17, 3)); p.drawLine(pt(17, 3), pt(17, 7))
        p.drawLine(pt(3, 13), pt(3, 17)); p.drawLine(pt(3, 17), pt(7, 17))
        p.drawLine(pt(13, 17), pt(17, 17)); p.drawLine(pt(17, 17), pt(17, 13))
        p.drawEllipse(rect(7, 7, 6, 6))
        p.drawLine(pt(11.5, 11.5), pt(14.2, 14.2))
    elif name == "clear":
        p.drawLine(pt(6, 6), pt(14, 14)); p.drawLine(pt(14, 6), pt(6, 14))
        p.drawEllipse(rect(3, 3, 14, 14))
    elif name == "copy":
        p.drawRoundedRect(rect(6, 5, 9, 11), 1.5 * s, 1.5 * s)
        p.drawRoundedRect(rect(3, 2, 9, 11), 1.5 * s, 1.5 * s)
    elif name == "compare":
        p.drawRoundedRect(rect(2.5, 4, 6.5, 12), 1.2 * s, 1.2 * s)
        p.drawRoundedRect(rect(11, 4, 6.5, 12), 1.2 * s, 1.2 * s)
        p.drawLine(pt(9.5, 8), pt(10.5, 8)); p.drawLine(pt(9.5, 12), pt(10.5, 12))
    elif name == "library":
        p.drawRoundedRect(rect(3, 5, 14, 11), 1.3 * s, 1.3 * s)
        p.drawLine(pt(4, 7.5), pt(16, 7.5))
        p.drawLine(pt(7, 3.5), pt(12, 3.5))
    elif name == "settings":
        p.drawEllipse(rect(7, 7, 6, 6))
        for x1, y1, x2, y2 in ((10,2,10,5),(10,15,10,18),(2,10,5,10),(15,10,18,10),(4.3,4.3,6.4,6.4),(13.6,13.6,15.7,15.7),(13.6,6.4,15.7,4.3),(4.3,15.7,6.4,13.6)):
            p.drawLine(pt(x1,y1), pt(x2,y2))
    elif name == "history":
        p.drawArc(rect(4, 4, 12, 12), 20 * 16, 315 * 16)
        p.drawLine(pt(4.5, 4), pt(4.5, 8)); p.drawLine(pt(4.5, 4), pt(8.5, 4))
        p.drawLine(pt(10, 7), pt(10, 11)); p.drawLine(pt(10, 11), pt(13, 11))
    elif name == "template":
        p.drawRoundedRect(rect(3, 3, 14, 14), 1.5 * s, 1.5 * s)
        p.drawLine(pt(3, 8), pt(17, 8)); p.drawLine(pt(9, 8), pt(9, 17))
    elif name == "report":
        p.drawLine(pt(4, 16), pt(16, 16)); p.drawLine(pt(5, 16), pt(5, 10))
        p.drawLine(pt(9, 16), pt(9, 6)); p.drawLine(pt(13, 16), pt(13, 3))
    elif name == "workflow":
        p.drawEllipse(rect(2.5, 7.5, 5, 5)); p.drawEllipse(rect(12.5, 2.5, 5, 5)); p.drawEllipse(rect(12.5, 12.5, 5, 5))
        p.drawLine(pt(7.5, 10), pt(11, 5.5)); p.drawLine(pt(7.5, 10), pt(11, 14.5))
    elif name == "cloud":
        path = QPainterPath(pt(6, 15))
        path.cubicTo(pt(3, 15), pt(2.5, 11), pt(5, 10))
        path.cubicTo(pt(5, 6), pt(10, 5), pt(12, 8))
        path.cubicTo(pt(16, 7), pt(18, 10), pt(16.5, 13))
        path.cubicTo(pt(16, 14.5), pt(14.5, 15), pt(13, 15))
        p.drawPath(path)
    elif name == "contact":
        p.drawRoundedRect(rect(3, 4, 14, 10), 1.8 * s, 1.8 * s)
        p.drawLine(pt(6, 14), pt(5, 17)); p.drawLine(pt(6, 14), pt(9, 14))
        p.drawLine(pt(6, 8), pt(14, 8)); p.drawLine(pt(6, 11), pt(11, 11))
    elif name == "save":
        p.drawRoundedRect(rect(3, 3, 14, 14), 1.3 * s, 1.3 * s)
        p.drawRoundedRect(rect(6, 3, 7, 5), 0.8 * s, 0.8 * s)
        p.drawRoundedRect(rect(6, 11, 8, 6), 1.0 * s, 1.0 * s)
    elif name == "external":
        p.drawRoundedRect(rect(3, 6, 11, 11), 1.4 * s, 1.4 * s)
        p.drawLine(pt(10, 3), pt(17, 3)); p.drawLine(pt(17, 3), pt(17, 10)); p.drawLine(pt(17, 3), pt(9, 11))
    elif name == "expand":
        p.drawLine(pt(4, 8), pt(4, 4)); p.drawLine(pt(4, 4), pt(8, 4))
        p.drawLine(pt(12, 4), pt(16, 4)); p.drawLine(pt(16, 4), pt(16, 8))
        p.drawLine(pt(4, 12), pt(4, 16)); p.drawLine(pt(4, 16), pt(8, 16))
        p.drawLine(pt(12, 16), pt(16, 16)); p.drawLine(pt(16, 16), pt(16, 12))
    elif name == "power":
        p.drawArc(rect(4, 4, 12, 12), 40 * 16, 280 * 16)
        p.drawLine(pt(10, 2), pt(10, 9))
    elif name == "check":
        p.drawEllipse(rect(3, 3, 14, 14)); p.drawLine(pt(6.5, 10), pt(9, 12.5)); p.drawLine(pt(9, 12.5), pt(14, 7.5))
    else:
        p.drawEllipse(rect(4, 4, 12, 12))

    p.end()
    return QIcon(pixmap)


def icon(name: str, *, color: str = INK, size: int = 20) -> QIcon:
    return _icon(name, color=color, size=size)


def _icon_for_text(text: str) -> str | None:
    t = " ".join(text.lower().replace("&", " ").split())
    if not t:
        return None
    exact = {
        "protect": "protect", "restore": "restore", "history": "history",
        "templates": "template", "settings": "settings", "local library": "library",
        "reports": "report", "document": "document", "paste text": "paste",
        "compare": "compare", "protected text": "protect", "clear": "clear",
        "scan": "scan", "scan locally": "scan", "upload": "upload",
        "upload file": "upload", "upload document": "upload", "download": "download",
        "save": "save", "save to library": "save", "restore locally": "restore",
        "full document view": "expand", "full screen preview": "expand",
    }
    if t in exact:
        return exact[t]
    rules = (
        ("upload", "upload"), ("download", "download"), ("save", "save"),
        ("copy", "copy"), ("protect", "protect"), ("scan", "scan"),
        ("restore", "restore"), ("library", "library"), ("clear", "clear"),
        ("delete", "clear"), ("remove", "clear"), ("setting", "settings"),
        ("history", "history"), ("report", "report"), ("template", "template"),
        ("workflow", "workflow"), ("automation", "workflow"), ("mcp", "workflow"),
        ("cloud", "cloud"), ("email", "contact"), ("contact", "contact"),
        ("chatgpt", "external"), ("website", "external"), ("store", "external"),
        ("open", "external"), ("full", "expand"), ("paste", "paste"),
        ("document", "document"), ("file", "document"), ("compare", "compare"),
        ("quit", "power"), ("check", "check"),
    )
    for needle, name in rules:
        if needle in t:
            return name
    return None


def apply_iconography(root: QWidget) -> None:
    """Apply one coherent icon system to buttons and tabs already in the UI."""
    for button in root.findChildren(QAbstractButton):
        key = _icon_for_text(button.text())
        if key is None:
            continue
        button.setIcon(icon(key, size=18))
        button.setIconSize(QSize(18, 18))

    for tabs in root.findChildren(QTabWidget):
        for index in range(tabs.count()):
            key = _icon_for_text(tabs.tabText(index))
            if key is not None:
                tabs.setTabIcon(index, icon(key, color=TEAL, size=17))

    # Navigation uses slightly larger white/teal-friendly line icons.
    nav_labels = {
        "Protect": "protect",
        "Library": "library",
        "Restore": "restore",
        "Local Automation / n8n": "workflow",
        "Cloud / MCP / Email": "cloud",
        "Settings": "settings",
        "Contact / Workflows": "contact",
        "History": "history",
        "Templates": "template",
        "Local Library": "library",
        "Reports": "report",
    }
    for button in root.findChildren(QAbstractButton):
        key = nav_labels.get(button.text())
        if key:
            button.setIcon(icon(key, color="#dceff4", size=20))
            button.setIconSize(QSize(20, 20))
