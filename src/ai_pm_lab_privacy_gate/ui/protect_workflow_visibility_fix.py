from __future__ import annotations

from types import MethodType

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


NAVY = "#062B4F"
TEAL = "#0B7180"
MUTED = "#61798A"
BORDER = "#D7E2EA"


def _summary_available(page, original_should_show) -> bool:
    try:
        return bool(original_should_show())
    except Exception:
        return False


def apply_protect_workflow_visibility_fix(main_window) -> None:
    """Keep the established Protect/file workflow as the primary managed view.

    The approved managed Protect & Preflight summary remains available, but it is
    opt-in instead of replacing the existing upload/scan/review controls as soon
    as findings exist. This is presentation-only: ProtectionPage remains the
    controller and no protection, policy, connector or save semantics change.
    """

    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_privacygate_protect_workflow_visibility_fixed", False)):
        return

    summary = getattr(page, "_privacygate_managed_mockup", None)
    original_shell = getattr(page, "_privacygate_original_protect_shell", None)
    if summary is None or original_shell is None:
        return

    page._privacygate_protect_workflow_visibility_fixed = True
    # Existing Protect stays primary. The user explicitly opens the managed
    # summary when they want to review the governance/preflight presentation.
    page._privacygate_force_original_protect = True

    original_should_show = summary.should_show
    original_render = summary.render

    def should_show(self) -> bool:
        return bool(
            _summary_available(page, original_should_show)
            and not bool(getattr(page, "_privacygate_force_original_protect", True))
        )

    summary.should_show = MethodType(should_show, summary)

    # A compact banner in the original Protect page exposes the managed summary
    # without taking away upload, file-change, scan, preview or save controls.
    banner = QFrame(objectName="ManagedPreflightSummaryBanner")
    banner.setStyleSheet(
        "QFrame#ManagedPreflightSummaryBanner{background:#F2FAFA;border:1px solid #CDE7E9;"
        "border-radius:10px;}"
    )
    banner_row = QHBoxLayout(banner)
    banner_row.setContentsMargins(12, 8, 12, 8)
    banner_row.setSpacing(10)

    copy = QVBoxLayout()
    copy.setContentsMargins(0, 0, 0, 0)
    copy.setSpacing(1)
    heading = QLabel("Managed Privacy Preflight available")
    heading.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:900;")
    detail = QLabel(
        "Keep working with your file here, or open the company-policy summary before AI handoff."
    )
    detail.setWordWrap(True)
    detail.setStyleSheet(f"color:{MUTED};font-size:8px;")
    copy.addWidget(heading)
    copy.addWidget(detail)
    banner_row.addLayout(copy, 1)

    open_summary = QPushButton("View Preflight summary")
    open_summary.setMinimumHeight(34)
    open_summary.setStyleSheet(
        "QPushButton{background:#0B7180;color:#FFFFFF;border:none;border-radius:8px;"
        "padding:7px 12px;font-size:9px;font-weight:900;}"
        "QPushButton:hover{background:#096672;}"
    )
    banner_row.addWidget(open_summary, alignment=Qt.AlignmentFlag.AlignVCenter)

    original_layout = original_shell.layout()
    if isinstance(original_layout, QVBoxLayout):
        original_layout.insertWidget(0, banner)
    else:
        banner.hide()

    # The managed summary gets an explicit return action. It does not clear the
    # current document, so the user comes back to the same file and findings.
    back_bar = QFrame(objectName="ManagedPreflightBackBar")
    back_bar.setStyleSheet(
        f"QFrame#ManagedPreflightBackBar{{background:#FFFFFF;border:1px solid {BORDER};border-radius:9px;}}"
    )
    back_row = QHBoxLayout(back_bar)
    back_row.setContentsMargins(10, 7, 10, 7)
    back_row.setSpacing(9)
    back_note = QLabel("Preflight summary · your original Protect controls and current file remain available.")
    back_note.setWordWrap(True)
    back_note.setStyleSheet(f"color:{MUTED};font-size:8px;")
    back_button = QPushButton("← Back to Protect / Files")
    back_button.setMinimumHeight(34)
    back_button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;border-radius:8px;"
        "padding:7px 12px;font-size:9px;font-weight:850;}"
        "QPushButton:hover{background:#F2FAFA;border-color:#96C9CD;color:#0B7180;}"
    )
    back_row.addWidget(back_button)
    back_row.addWidget(back_note, 1)

    summary_layout = summary.layout()
    if isinstance(summary_layout, QVBoxLayout):
        summary_layout.insertWidget(1, back_bar)
    else:
        back_bar.hide()

    def show_summary() -> None:
        if not _summary_available(page, original_should_show):
            return
        page._privacygate_force_original_protect = False
        summary.render()

    def show_protect() -> None:
        page._privacygate_force_original_protect = True
        summary.render()

    open_summary.clicked.connect(show_summary)
    back_button.clicked.connect(show_protect)

    def render_with_navigation(self) -> None:
        original_render()
        available = _summary_available(page, original_should_show)
        banner.setVisible(available and bool(getattr(page, "_privacygate_force_original_protect", True)))
        back_bar.setVisible(available and not bool(getattr(page, "_privacygate_force_original_protect", True)))

    summary.render = MethodType(render_with_navigation, summary)
    summary.render()
