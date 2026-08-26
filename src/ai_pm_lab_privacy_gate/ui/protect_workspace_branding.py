from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon

from ai_pm_lab_privacy_gate.ui.organization_workspace_suite import (
    DIRECT_IMPORT_PROVIDERS,
    PROVIDERS,
)
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader


PROVIDER_LABELS = dict(PROVIDERS)


def _action_text(provider: str) -> str:
    if provider == "gmail":
        return "Import email from Gmail"
    if provider == "google_drive":
        return "Import file from Google Drive"
    label = PROVIDER_LABELS.get(provider, provider.replace("_", " ").title())
    return f"Browse {label}"


def _refresh_branding(bar) -> None:
    provider = str(bar.source_combo.currentData() or "")
    if not provider:
        bar.browse.setIcon(QIcon())
        return

    # Keep the source selector visually clean: original provider icon + provider
    # name. Capability detail belongs in the action button/tooltip rather than in
    # every dropdown row.
    for index in range(bar.source_combo.count()):
        item_provider = str(bar.source_combo.itemData(index) or "")
        label = PROVIDER_LABELS.get(
            item_provider, bar.source_combo.itemText(index).split(" ·", 1)[0]
        )
        bar.source_combo.setItemText(index, label)
        capability = (
            "Select content and import it directly into Protect."
            if item_provider in DIRECT_IMPORT_PROVIDERS
            else "Open the connected provider browser. Direct Protect import is not available for this provider yet."
        )
        bar.source_combo.setItemData(
            index, capability, Qt.ItemDataRole.ToolTipRole
        )

    # The account belongs to the selected provider, so repeating the same brand
    # icon beside each account makes multi-login selection much easier to scan.
    def apply_pixmap(pixmap, expected_provider=provider) -> None:
        if str(bar.source_combo.currentData() or "") != expected_provider:
            return
        icon = QIcon(pixmap)
        source_index = bar.source_combo.findData(expected_provider)
        if source_index >= 0:
            bar.source_combo.setItemIcon(source_index, icon)
        for account_index in range(bar.account_combo.count()):
            bar.account_combo.setItemIcon(account_index, icon)
        bar.browse.setIcon(icon)
        bar.browse.setIconSize(QSize(18, 18))

    bar._privacygate_workspace_logo_loader.load(provider, apply_pixmap)

    workspace_key = str(bar.workspace_combo.currentData() or "")
    account_id = str(bar.account_combo.currentData() or "")
    context = bar.store.load()
    descriptor = context.workspaces.get(workspace_key)
    needs_approval = bool(
        descriptor is not None
        and not descriptor.personal
        and provider
        and account_id
        and not bar.store.is_account_available(provider, account_id, workspace_key)
    )
    action = _action_text(provider)
    bar.browse.setText(
        f"Approve account & {action[0].lower() + action[1:]}"
        if needs_approval
        else action
    )
    bar.browse.setToolTip(
        "Choose a Gmail email and bring its local working copy into Protect."
        if provider == "gmail"
        else "Choose a Google Drive file and bring its local working copy into Protect."
        if provider == "google_drive"
        else f"Open {PROVIDER_LABELS.get(provider, provider)} connected content."
    )


def apply_managed_protect_branding(main_window):
    page = getattr(main_window, "protection_page", None)
    bar = getattr(page, "_managed_workspace_context_bar", None) if page is not None else None
    if bar is None or getattr(bar, "_privacygate_branding_applied", False):
        return bar

    bar._privacygate_branding_applied = True
    bar._privacygate_workspace_logo_loader = ProviderLogoLoader(
        bar.team_page.state_store.data_dir, bar
    )
    bar.source_combo.setIconSize(QSize(20, 20))
    bar.account_combo.setIconSize(QSize(18, 18))

    # Existing controller slots continue to own the behavior. These extra slots
    # only update presentation after the controller has rebuilt state/text.
    bar.source_combo.currentIndexChanged.connect(
        lambda *_args: QTimer.singleShot(0, lambda: _refresh_branding(bar))
    )
    bar.account_combo.currentIndexChanged.connect(
        lambda *_args: QTimer.singleShot(0, lambda: _refresh_branding(bar))
    )
    bar.workspace_combo.currentIndexChanged.connect(
        lambda *_args: QTimer.singleShot(0, lambda: _refresh_branding(bar))
    )
    bar.team_page.state_changed.connect(
        lambda _state: QTimer.singleShot(0, lambda: _refresh_branding(bar))
    )

    QTimer.singleShot(0, lambda: _refresh_branding(bar))
    return bar
