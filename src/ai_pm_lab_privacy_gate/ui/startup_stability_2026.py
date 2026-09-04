from __future__ import annotations

"""Startup-only UI hardening for the 2026 PrivacyGate desktop shell.

The startup path builds and refreshes several presentation layers before Qt gets
its first normal event-loop turn. Keep those refreshes invisible until the
window is genuinely ready, and remove replaced dashboard widgets immediately so
an old row cannot be painted on top of its replacement.
"""

from typing import Any

from PySide6.QtWidgets import QPushButton


_INSTALLED = False


def _clear_layout_immediately(layout: Any) -> None:
    """Detach replaced widgets now, then let Qt reclaim them safely later.

    ``deleteLater()`` by itself is correct for object lifetime, but during the
    startup bootstrap it leaves the old widget paintable until the event loop
    processes DeferredDelete events. Repeated dashboard refreshes can therefore
    show two generations of labels at once. Hiding and detaching first removes
    the stale generation from painting/layout immediately.
    """

    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif child is not None:
            _clear_layout_immediately(child)


def _install_personal_workspace_clear_fix() -> None:
    from ai_pm_lab_privacy_gate.ui import mockup_personal_workspace_2026 as base
    from ai_pm_lab_privacy_gate.ui import mockup_personal_workspace_final_2026 as final
    from ai_pm_lab_privacy_gate.ui import mockup_personal_workspace_polish_2026 as polish

    # The render functions in these modules resolve _clear_layout from their own
    # module globals at call time, so one shared immediate implementation covers
    # the base metrics/activity plus the later document/app presentation layers.
    base._clear_layout = _clear_layout_immediately
    polish._clear_layout = _clear_layout_immediately
    final._clear_layout = _clear_layout_immediately


def _install_startup_loading_guard() -> None:
    from ai_pm_lab_privacy_gate.ui.global_loading_runtime import UnifiedLoadingController

    if bool(getattr(UnifiedLoadingController, "_privacygate_startup_guard", False)):
        return

    original_render = UnifiedLoadingController._render

    def render(self: UnifiedLoadingController) -> None:
        # During MainWindow construction page-specific operations may legitimately
        # enter their busy state. They still remain tracked, but the startup
        # splash is the only loading surface shown until app.py declares the first
        # stable paint ready. This prevents e.g. "Team is working" from appearing
        # over a half-built Personal Workspace.
        if not bool(getattr(self.main_window, "_privacygate_startup_ready", False)):
            self.dialog.dismiss()
            return
        original_render(self)

    UnifiedLoadingController._render = render
    UnifiedLoadingController._privacygate_startup_guard = True


def _install_policy_history_lifetime_fix() -> None:
    """Keep the policy-history visibility slot tied to its QPushButton lifetime."""

    from ai_pm_lab_privacy_gate.infrastructure.policy.supabase_team import SupabaseTeamClient
    from ai_pm_lab_privacy_gate.ui import governance_hardening_2026 as governance

    if bool(getattr(governance, "_privacygate_policy_history_lifetime_fix", False)):
        return

    def install_policy_history(main_window) -> None:
        if not hasattr(SupabaseTeamClient, "list_policy_versions"):
            def list_policy_versions(self, session, organization_id: str):
                payload = self._request(
                    "GET",
                    "/rest/v1/privacy_gate_policy_versions",
                    session,
                    params={
                        "organization_id": f"eq.{organization_id}",
                        "select": "version,policy_json,policy_sha256,created_at,created_by",
                        "order": "version.desc",
                        "limit": "100",
                    },
                )
                return [dict(row) for row in payload] if isinstance(payload, list) else []

            SupabaseTeamClient.list_policy_versions = list_policy_versions  # type: ignore[attr-defined]

        page = getattr(main_window, "team_page", None)
        if page is None or bool(getattr(page, "_privacygate_policy_history", False)):
            return
        page._privacygate_policy_history = True

        button = QPushButton("Policy history")
        button.setToolTip(
            "Compare policy versions or republish an older version as a new immutable version."
        )
        layout = governance._find_layout_containing(page.layout(), page.edit_policy_button)
        if layout is not None:
            layout.insertWidget(layout.indexOf(page.edit_policy_button) + 1, button)

        def open_history() -> None:
            if not page.state.organization_id or page.state.role not in {"owner", "admin"}:
                return
            page._run_team_action(
                lambda session: page.team_client.list_policy_versions(
                    session, page.state.organization_id
                ),
                result_handler=lambda rows: governance.PolicyHistoryDialog(
                    page, list(rows or [])
                ).exec(),
                refresh_after=False,
            )

        button.clicked.connect(open_history)

        def visibility(_state=None) -> None:
            button.setVisible(
                bool(page.state.organization_id and page.state.role in {"owner", "admin"})
            )

        def disconnect_visibility(*_args) -> None:
            try:
                page.state_changed.disconnect(visibility)
            except (RuntimeError, TypeError):
                pass

        # The old implementation left this Python closure connected after Qt had
        # destroyed the button. A later state_changed emission then called into a
        # deleted C++ object (libshiboken RuntimeError). Disconnect with the
        # button's actual QObject lifetime instead.
        button.destroyed.connect(disconnect_visibility)
        page.state_changed.connect(visibility)
        visibility()

    governance._install_policy_history = install_policy_history
    governance._privacygate_policy_history_lifetime_fix = True


def install_startup_stability_2026() -> None:
    """Install startup fixes before the first ``MainWindow`` is constructed."""

    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    _install_personal_workspace_clear_fix()
    _install_startup_loading_guard()
    _install_policy_history_lifetime_fix()
