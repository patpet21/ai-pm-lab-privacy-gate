from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


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
AMBER = "#D97706"
AMBER_SOFT = "#FFF7ED"
RED = "#DC2626"
RED_SOFT = "#FEF2F2"
PURPLE = "#7C3AED"
PURPLE_SOFT = "#F5F3FF"
TEAL = "#0891B2"
TEAL_SOFT = "#ECFEFF"
NEUTRAL_SOFT = "#F2F4F7"


def card(object_name: str = "PrivacyGate2026Card") -> QFrame:
    frame = QFrame(objectName=object_name)
    frame.setStyleSheet(
        f"QFrame#{object_name}{{background:{WHITE};border:1px solid {BORDER};border-radius:15px;}}"
    )
    return frame


def heading(text: str, size: int = 13) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color:{INK};font-size:{size}px;font-weight:900;background:transparent;border:none;"
    )
    return label


def muted(text: str = "", size: float = 8.5) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(
        f"color:{MUTED};font-size:{size}px;background:transparent;border:none;"
    )
    return label


def link_button(text: str, callback: Callable[[], None]) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton{background:transparent;color:#2563EB;border:none;border-radius:7px;"
        "padding:5px 7px;font-size:9px;font-weight:850;}"
        "QPushButton:hover{background:#EEF4FF;color:#1D4ED8;}"
    )
    button.clicked.connect(lambda _checked=False: callback())
    return button


def action_button(
    text: str,
    callback: Callable[[], None],
    *,
    primary: bool = False,
) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        button.setStyleSheet(
            "QPushButton{background:#2563EB;color:#FFFFFF;border:1px solid #2563EB;border-radius:9px;"
            "padding:8px 12px;font-size:9px;font-weight:850;}"
            "QPushButton:hover{background:#1D4ED8;border-color:#1D4ED8;}"
            "QPushButton:disabled{background:#D0D5DD;border-color:#D0D5DD;color:#FFFFFF;}"
        )
    else:
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:9px;"
            "padding:8px 12px;font-size:9px;font-weight:800;}"
            "QPushButton:hover{background:#F8FAFC;border-color:#98A2B3;}"
            "QPushButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
        )
    button.clicked.connect(lambda _checked=False: callback())
    return button


def chip(text: str, tone: str = "neutral") -> QLabel:
    palette = {
        "blue": (BLUE_SOFT, BLUE, "#D6E4FF"),
        "green": (GREEN_SOFT, GREEN, "#BBF7D0"),
        "amber": (AMBER_SOFT, AMBER, "#FED7AA"),
        "red": (RED_SOFT, RED, "#FECACA"),
        "purple": (PURPLE_SOFT, PURPLE, "#DDD6FE"),
        "teal": (TEAL_SOFT, TEAL, "#A5F3FC"),
        "neutral": (NEUTRAL_SOFT, "#475467", BORDER),
    }
    background, foreground, border = palette.get(tone, palette["neutral"])
    label = QLabel(text)
    label.setStyleSheet(
        f"background:{background};color:{foreground};border:1px solid {border};border-radius:8px;"
        "padding:4px 8px;font-size:7.5px;font-weight:850;"
    )
    return label


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            clear_layout(child)


class StatusRing(QWidget):
    """Reusable status ring for Personal, Organization, Team and Governance views."""

    def __init__(self, *, color: str = GREEN, diameter: int = 104, parent=None) -> None:
        super().__init__(parent)
        self._value: int | None = 0
        self._center = "0%"
        self._caption = "READY"
        self._color = QColor(color)
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)

    def set_status(
        self,
        value: int | None,
        *,
        center: str | None = None,
        caption: str = "",
        color: str | None = None,
    ) -> None:
        self._value = None if value is None else max(0, min(100, int(value)))
        self._center = center if center is not None else ("—" if value is None else f"{self._value}%")
        self._caption = caption
        if color:
            self._color = QColor(color)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        margin = max(9, int(self._diameter * 0.09))
        rect = QRectF(margin, margin, self._diameter - 2 * margin, self._diameter - 2 * margin)
        width = max(7, int(self._diameter * 0.075))
        base = QPen(QColor("#EAECF0"), width)
        base.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(base)
        painter.drawArc(rect, 0, 360 * 16)
        if self._value is not None:
            progress = QPen(self._color, width)
            progress.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(progress)
            painter.drawArc(rect, 90 * 16, -int(360 * 16 * self._value / 100))

        painter.setPen(QColor(INK))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(11, int(self._diameter * 0.16)))
        painter.setFont(font)
        painter.drawText(
            QRectF(8, self._diameter * 0.34, self._diameter - 16, self._diameter * 0.24),
            Qt.AlignmentFlag.AlignCenter,
            self._center,
        )
        if self._caption:
            painter.setPen(self._color)
            font.setPointSize(max(6, int(self._diameter * 0.065)))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                QRectF(6, self._diameter * 0.57, self._diameter - 12, self._diameter * 0.16),
                Qt.AlignmentFlag.AlignCenter,
                self._caption,
            )
        painter.end()


class AdaptiveGrid(QWidget):
    """Small responsive grid used by dashboard surfaces.

    Cards are kept as real widgets and simply reflowed as the content area narrows,
    so future pages can reuse the same desktop behavior without duplicating resize logic.
    """

    def __init__(
        self,
        widgets: Sequence[QWidget],
        *,
        max_columns: int = 5,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.widgets = list(widgets)
        self.max_columns = max(1, int(max_columns))
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        self._columns = 0
        self._reflow(force=True)

    def _wanted_columns(self) -> int:
        width = max(1, self.width())
        if self.max_columns >= 5 and width >= 1180:
            return 5
        if self.max_columns >= 4 and width >= 980:
            return 4
        if self.max_columns >= 3 and width >= 760:
            return 3
        if self.max_columns >= 2 and width >= 540:
            return 2
        return 1

    def _reflow(self, *, force: bool = False) -> None:
        columns = min(self.max_columns, self._wanted_columns())
        if columns == self._columns and not force:
            return
        self._columns = columns
        for widget in self.widgets:
            self.grid.removeWidget(widget)
        for index, widget in enumerate(self.widgets):
            self.grid.addWidget(widget, index // columns, index % columns)
        for column in range(self.max_columns):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._reflow()


class CoveragePlot(QWidget):
    """Compact honest coverage graph over control categories, not invented history."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._values: list[tuple[str, int]] = []
        self.setMinimumHeight(145)

    def set_values(self, values: Sequence[tuple[str, int]]) -> None:
        self._values = [(str(label), max(0, min(100, int(value)))) for label, value in values]
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = self.width()
        height = self.height()
        left, right, top, bottom = 38, 14, 12, 28
        graph_w = max(10, width - left - right)
        graph_h = max(10, height - top - bottom)

        painter.setPen(QPen(QColor("#EAECF0"), 1))
        font = painter.font()
        font.setPointSize(7)
        painter.setFont(font)
        for pct in (0, 25, 50, 75, 100):
            y = top + graph_h - graph_h * pct / 100
            painter.drawLine(left, int(y), width - right, int(y))
            painter.setPen(QColor(MUTED))
            painter.drawText(0, int(y) - 7, left - 7, 14, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{pct}%")
            painter.setPen(QPen(QColor("#EAECF0"), 1))

        if not self._values:
            painter.setPen(QColor(MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Coverage data unavailable")
            painter.end()
            return

        count = len(self._values)
        points: list[tuple[float, float]] = []
        for index, (label, value) in enumerate(self._values):
            x = left + (graph_w / max(1, count - 1)) * index if count > 1 else left + graph_w / 2
            y = top + graph_h - graph_h * value / 100
            points.append((x, y))
            painter.setPen(QColor(MUTED))
            painter.drawText(
                int(x - 38), height - bottom + 6, 76, 18,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                label,
            )

        line = QPen(QColor(GREEN), 2)
        line.setCapStyle(Qt.PenCapStyle.RoundCap)
        line.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(line)
        for index in range(1, len(points)):
            painter.drawLine(int(points[index - 1][0]), int(points[index - 1][1]), int(points[index][0]), int(points[index][1]))
        for x, y in points:
            painter.setBrush(QColor(WHITE))
            painter.setPen(QPen(QColor(GREEN), 2))
            painter.drawEllipse(QRectF(x - 4, y - 4, 8, 8))
        painter.end()
