from __future__ import annotations

"""Compact, truthful workspace context for the approved Protect surface.

Presentation only. Existing workspace/source/account selectors and policy checks stay
in charge of behavior; this module only removes redundant chrome and summarizes the
already-loaded state as compact chips.
"""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QLayout

from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    AMBER,
    AMBER_SOFT,
    BLUE,
    BLUE_SOFT,
    BORDER,
    GREEN,
    GREEN_SOFT,
    MUTED,
    NEUTRAL_SOFT,
    RED,
    RED_SOFT,
)


def _find_layout(layout: QLayout | None, widget) -> QLayout | None:
    if layout is None:
        return None
    if layout.indexOf(widget) >= 0:
        return layout
    for index in range(layout.count()):
        child = layout.itemAt(index).layout()
        found = _find_layout(child, widget)
        if found is not None:
            return found
    return None


def _chip() -> QLabel:
    label = QLabel()
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setMinimumHeight(27)
    return label


def _set_chip(label: QLabel, text: str, tone: str) -> None:
    palette = {
        "blue": (BLUE_SOFT, BLUE, "#C7D7FE"),
        "green": (GREEN_SOFT, GREEN, "#BBF7D0"),
        "amber": (AMBER_SOFT, AMBER, "#FED7AA"),
        "red": (RED_SOFT, RED, "#FECACA"),
        "neutral": (NEUTRAL_SOFT, MUTED, BORDER),
    }
    bg, fg, border = palette.get(tone, palette["neutral"])
    label.setText(text)
    label.setStyleSheet(
        f"background:{bg};color:{fg};border:1px solid {border};border-radius:8px;"
        "padding:4px 7px;font-size:7.5px;font-weight:850;"
    )


def _refresh_chips(bar) -> None:
    host = getattr(bar, "_protect_2026_policy_chips", None)
    labels = tuple(getattr(bar, "_protect_2026_policy_chip_labels", ()) or ())
    if host is None or len(labels) != 4:
        return

    workspace_key = str(bar.workspace_combo.currentData() or "")
    provider = str(bar.source_combo.currentData() or "")
    account_id = str(bar.account_combo.currentData() or "")
    context = bar.store.load()
    descriptor = context.workspaces.get(workspace_key)

    if descriptor is None:
        values = (
            ("Policy —", "neutral"),
            ("Status Select workspace", "amber"),
            ("Mode —", "neutral"),
            ("Preflight Waiting", "neutral"),
        )
    elif descriptor.personal:
        values = (
            ("Policy Personal", "neutral"),
            ("Status Local", "green"),
            ("Mode Local", "blue"),
            ("Preflight Local", "green"),
        )
    else:
        policy = bar._policy_for(workspace_key)
        if policy is None:
            values = (
                ("Policy Syncing", "amber"),
                ("Status Waiting", "amber"),
                ("Mode Managed", "blue"),
                ("Preflight Waiting", "neutral"),
            )
        else:
            connector_allowed = bool(
                provider
                and policy.allowed_connectors.get(
                    provider, policy.allowed_connectors.get("*", False)
                )
            )
            ready = bool(connector_allowed and account_id)
            values = (
                (f"Policy v{policy.version}", "blue"),
                ("Status Allowed" if connector_allowed else "Status Blocked", "green" if connector_allowed else "red"),
                ("Mode Managed", "blue"),
                ("Preflight Ready" if ready else "Preflight Waiting", "green" if ready else "amber"),
            )

    for label, (text, tone) in zip(labels, values):
        _set_chip(label, text, tone)

    provider_index = bar.source_combo.currentIndex()
    provider_label = (
        str(bar.source_combo.itemText(provider_index) or "").strip()
        if provider_index >= 0
        else ""
    )
    if provider_label:
        bar.source_combo.setToolTip(f"Connected source: {provider_label}")
    account_label = str(bar.account_combo.currentText() or "").strip()
    if account_label:
        bar.account_combo.setToolTip(f"Account: {account_label}")


def apply_mockup_protect_workspace_refinement_2026(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    bar = getattr(page, "_managed_workspace_context_bar", None) if page is not None else None
    if bar is None or bool(getattr(bar, "_protect_2026_workspace_refined", False)):
        return
    bar._protect_2026_workspace_refined = True

    root = bar.layout()
    if root is not None:
        root.setContentsMargins(12, 7, 12, 8)
        root.setSpacing(5)

    for label in bar.findChildren(QLabel):
        text = " ".join(label.text().split())
        if text.startswith("Personal or company context") or text.startswith("Source of the content"):
            label.hide()
            label.setMaximumHeight(0)
        elif text.upper() == "WORKSPACE CONTEXT":
            label.setText("WORKSPACE CONTEXT")
            label.setStyleSheet(
                f"color:{BLUE};font-size:8px;font-weight:950;border:none;background:transparent;"
            )

    bar.workspace_combo.setMinimumWidth(220)
    bar.workspace_combo.setMaximumWidth(270)
    bar.workspace_combo.setMinimumHeight(36)

    # The closed selector is intentionally logo-first. Provider names remain fully
    # readable in the expanded dropdown and in the tooltip.
    bar.source_combo.setMinimumWidth(68)
    bar.source_combo.setMaximumWidth(68)
    bar.source_combo.setMinimumHeight(36)
    bar.source_combo.view().setMinimumWidth(190)
    bar.source_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    bar.source_combo.setMinimumContentsLength(0)

    bar.account_combo.setMinimumWidth(190)
    bar.account_combo.setMaximumWidth(255)
    bar.account_combo.setMinimumHeight(36)
    bar.account_combo.view().setMinimumWidth(260)

    standard_combo_qss = (
        "QComboBox{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
        "border-radius:9px;padding:6px 8px;font-size:8.5px;font-weight:700;}"
        "QComboBox:hover{border-color:#C7D7FE;}"
        f"QComboBox:focus{{border:1px solid {BLUE};}}"
        "QComboBox::drop-down{border:none;width:23px;}"
        "QComboBox QAbstractItemView{background:#FFFFFF;color:#344054;"
        "border:1px solid #D0D5DD;selection-background-color:#EEF4FF;"
        "selection-color:#101828;padding:4px;}"
    )
    bar.workspace_combo.setStyleSheet(standard_combo_qss)
    bar.account_combo.setStyleSheet(standard_combo_qss)
    bar.source_combo.setStyleSheet(
        "QComboBox{background:#FFFFFF;color:transparent;border:1px solid #D0D5DD;"
        "border-radius:9px;padding:6px 6px;font-size:8px;font-weight:700;}"
        "QComboBox:hover{border-color:#C7D7FE;}"
        f"QComboBox:focus{{border:1px solid {BLUE};}}"
        "QComboBox::drop-down{border:none;width:22px;}"
        "QComboBox QAbstractItemView{background:#FFFFFF;color:#344054;"
        "border:1px solid #D0D5DD;selection-background-color:#EEF4FF;"
        "selection-color:#101828;padding:4px;}"
    )

    bar.manage.setText("Team access")
    bar.manage.setMinimumHeight(34)
    bar.manage.setMaximumWidth(116)
    bar.browse.setMinimumHeight(37)
    bar.browse.setMinimumWidth(185)
    bar.browse.setMaximumWidth(230)

    bar.policy.hide()
    bar.policy.setMaximumWidth(0)
    row = _find_layout(root, bar.browse)
    if row is None:
        return

    chips = QFrame(objectName="Protect2026PolicyChips")
    chips.setStyleSheet("QFrame#Protect2026PolicyChips{background:transparent;border:none;}")
    chips_layout = QHBoxLayout(chips)
    chips_layout.setContentsMargins(0, 0, 0, 0)
    chips_layout.setSpacing(5)
    chip_labels = tuple(_chip() for _ in range(4))
    for label in chip_labels:
        chips_layout.addWidget(label)

    browse_index = row.indexOf(bar.browse)
    row.insertWidget(max(0, browse_index), chips, 1)
    bar._protect_2026_policy_chips = chips
    bar._protect_2026_policy_chip_labels = chip_labels

    def schedule(*_args) -> None:
        QTimer.singleShot(0, lambda: _refresh_chips(bar))

    bar.workspace_combo.currentIndexChanged.connect(schedule)
    bar.source_combo.currentIndexChanged.connect(schedule)
    bar.account_combo.currentIndexChanged.connect(schedule)
    bar.team_page.state_changed.connect(schedule)
    bar.team_page.policy_changed.connect(schedule)
    schedule()
