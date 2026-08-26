from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


NAVY = "#062B4F"
TEAL = "#0B7180"


def _account_icon(size: int = 24) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor("#EAF7F7"))
    pen.setWidthF(max(1.7, size / 11.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    s = size / 24.0
    painter.drawEllipse(int(8 * s), int(3 * s), int(8 * s), int(8 * s))
    painter.drawArc(int(4 * s), int(11 * s), int(16 * s), int(10 * s), 0, 180 * 16)
    painter.end()
    return QIcon(pixmap)


def _place_and_style(controller) -> None:
    main_window = controller.main_window
    button = controller.button
    privacy_note = getattr(main_window, "privacy_note", None)

    if privacy_note is not None:
        privacy_note.hide()

    layout = getattr(main_window, "side_layout", None)
    if layout is not None:
        try:
            layout.removeWidget(button)
        except RuntimeError:
            pass
        target = layout.indexOf(privacy_note) if privacy_note is not None else layout.count()
        layout.insertWidget(max(0, target), button)

    expanded = bool(getattr(main_window, "sidebar_expanded", True))
    button.setVisible(True)
    button.show()
    button.raise_()
    button.setIcon(_account_icon(24))
    button.setIconSize(QSize(24, 24))

    display_name = controller._display_name()
    plan_line = controller._plan_line()
    if expanded:
        button.setMaximumHeight(16777215)
        button.setText(f"  ACCOUNT\n  {display_name} · {plan_line}")
        button.setMinimumHeight(62)
        button.setToolTip(
            f"Account\n{display_name}\n{plan_line}"
            + (f"\n{controller.email}" if controller.email else "")
        )
        button.setStyleSheet(
            "QPushButton#AccountMenuButton{background:#0A4D67;color:#FFFFFF;"
            "border:1px solid #16758A;border-radius:11px;text-align:left;"
            "padding:9px 11px;font-size:10px;font-weight:850;}"
            "QPushButton#AccountMenuButton:hover{background:#0D5C77;border-color:#2D8EA0;}"
            "QPushButton#AccountMenuButton:pressed{background:#0B7180;border-color:#1595A3;}"
        )
    else:
        button.setText("")
        button.setMinimumHeight(48)
        button.setMaximumHeight(48)
        button.setToolTip(
            f"Account\n{display_name}\n{plan_line}"
            + (f"\n{controller.email}" if controller.email else "")
        )
        button.setStyleSheet(
            "QPushButton#AccountMenuButton{background:#0A4D67;color:#FFFFFF;"
            "border:1px solid #16758A;border-radius:11px;padding:10px;}"
            "QPushButton#AccountMenuButton:hover{background:#0D5C77;border-color:#2D8EA0;}"
            "QPushButton#AccountMenuButton:pressed{background:#0B7180;border-color:#1595A3;}"
        )


def apply_account_sidebar_polish(main_window) -> None:
    controller = getattr(main_window, "_privacygate_account_menu_controller", None)
    if controller is None:
        return

    if not bool(getattr(controller, "_privacygate_account_sidebar_polished", False)):
        original_render = controller._render

        def render_with_account_polish(self) -> None:
            original_render()
            _place_and_style(self)

        controller._render = MethodType(render_with_account_polish, controller)
        controller._privacygate_account_sidebar_polished = True

        original_sidebar = main_window._set_sidebar_expanded

        def set_sidebar_expanded(expanded: bool) -> None:
            original_sidebar(expanded)
            note = getattr(main_window, "privacy_note", None)
            if note is not None:
                note.hide()
            _place_and_style(controller)

        main_window._set_sidebar_expanded = set_sidebar_expanded

    _place_and_style(controller)
