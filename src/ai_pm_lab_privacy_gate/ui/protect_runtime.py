from __future__ import annotations

"""Single orchestration point for the Protect desktop experience.

The application historically accumulated Protect features as independent UI
patches. Keeping their imports and ordering here gives us one controlled
migration boundary: behavior remains compatible today, while each legacy layer
can be replaced behind this module without growing ``ui.__init__`` again.
"""

PROTECT_RUNTIME_STAGES = (
    "source",
    "managed",
    "layout",
    "visibility",
    "final",
)

_INSTALLED = False


def install_protect_runtime() -> None:
    """Install class-level Protect hooks exactly once, before MainWindow exists."""
    global _INSTALLED
    if _INSTALLED:
        return

    # Preserve the proven installation order. Imports stay lazy so this module
    # cannot create circular imports while the ``ui`` package is initializing.
    from .redesign import install_redesign
    from .protect_ghost_cleanup import install_protect_ghost_cleanup
    from .protect_quick_actions import install_protect_quick_actions
    from .protect_document_language import install_protect_document_language

    install_redesign()
    install_protect_ghost_cleanup()
    install_protect_quick_actions()
    install_protect_document_language()
    _INSTALLED = True


def _completed_stages(main_window) -> set[str]:
    stages = getattr(main_window, "_privacygate_protect_runtime_stages", None)
    if not isinstance(stages, set):
        stages = set()
        main_window._privacygate_protect_runtime_stages = stages
    return stages


def _wire_privacy_check_refresh_triggers(page) -> None:
    """Refresh Privacy Check after the authoritative protected-copy update.

    ``protect_workflow_v2`` already wraps ``_refresh_preview``. During the
    compatibility migration, however, some older signal connections can still
    reach a previously-bound refresh callable. The hidden redesign Protect
    action and its review debounce timer are the stable points that run *after*
    the protected result has been rebuilt, regardless of whether the source is
    local, Drive, or Gmail.

    Track the Privacy Check generation so this bridge does not launch a duplicate
    second scan when the normal ``_refresh_preview`` wrapper already did so.
    """
    if page is None or getattr(page, "_privacygate_privacy_check_trigger_wired", False):
        return
    if not callable(getattr(page, "_refresh_privacy_check", None)):
        return

    from PySide6.QtCore import QTimer

    page._privacygate_privacy_check_observed_generation = int(
        getattr(page, "_privacy_check_generation", 0) or 0
    )

    def schedule_refresh(*_args) -> None:
        current_generation = int(getattr(page, "_privacy_check_generation", 0) or 0)
        observed_generation = int(
            getattr(page, "_privacygate_privacy_check_observed_generation", 0) or 0
        )

        # The ordinary workflow path already started a check synchronously while
        # rebuilding the protected result. Record that generation and do nothing.
        if current_generation != observed_generation:
            page._privacygate_privacy_check_observed_generation = current_generation
            return

        def refresh_if_needed() -> None:
            latest_generation = int(getattr(page, "_privacy_check_generation", 0) or 0)
            observed = int(
                getattr(page, "_privacygate_privacy_check_observed_generation", 0) or 0
            )
            if latest_generation != observed:
                page._privacygate_privacy_check_observed_generation = latest_generation
                return
            refresh = getattr(page, "_refresh_privacy_check", None)
            if callable(refresh):
                refresh()
                page._privacygate_privacy_check_observed_generation = int(
                    getattr(page, "_privacy_check_generation", latest_generation) or 0
                )

        QTimer.singleShot(0, refresh_if_needed)

    protect_button = getattr(page, "_redesign_protect_button", None)
    if protect_button is not None:
        protect_button.clicked.connect(schedule_refresh)

    selection_timer = getattr(page, "_redesign_selection_timer", None)
    if selection_timer is not None:
        selection_timer.timeout.connect(schedule_refresh)

    page._privacygate_privacy_check_trigger_wired = True


def apply_protect_runtime(main_window, stage: str) -> None:
    """Apply one ordered Protect stage to ``main_window`` exactly once.

    Stages intentionally mirror the old startup positions. That lets us clean
    the architecture without changing connector routing, workspace policy,
    preview generation, Gmail multi-source behavior, or export semantics.
    """
    if stage not in PROTECT_RUNTIME_STAGES:
        raise ValueError(f"Unknown Protect runtime stage: {stage}")

    completed = _completed_stages(main_window)
    if stage in completed:
        return

    if stage == "source":
        from .protect_source_picker import apply_protect_source_picker

        apply_protect_source_picker(main_window)

    elif stage == "managed":
        from .protect_workspace_controls import apply_managed_protect_context
        from .protect_workspace_branding import apply_managed_protect_branding

        apply_managed_protect_context(main_window)
        apply_managed_protect_branding(main_window)

    elif stage == "layout":
        # Compatibility cleanup retained during migration. The final surface
        # guard below becomes the authoritative protection against detached
        # legacy widgets after *all* later Gmail/session passes have run.
        from .protect_late_cleanup import apply_protect_late_cleanup

        apply_protect_late_cleanup(main_window)

    elif stage == "visibility":
        from .protect_workflow_visibility_fix import apply_protect_workflow_visibility_fix

        apply_protect_workflow_visibility_fix(main_window)

    elif stage == "final":
        # Keep the tested order from the previous startup chain. This is the
        # compatibility bridge while the underlying modules are progressively
        # folded into the generic ProtectSession implementation.
        from .protect_usability_polish import apply_protect_usability_polish
        from .document_pipeline_v2_ui import apply_document_pipeline_v2_ui
        from .protect_session_upgrade import apply_protect_session_upgrade
        from .protect_session_runtime_fix import apply_protect_session_runtime_fix
        from .local_protect_session_runtime import apply_local_protect_session_runtime
        from .gmail_package_browser import apply_gmail_package_browser
        from .gmail_package_runtime_fix import apply_gmail_package_runtime_fix
        from .gmail_component_session import apply_gmail_component_session
        from .gmail_protect_package_bridge import apply_gmail_protect_package_bridge
        from .gmail_component_preview_polish import apply_gmail_component_preview_polish
        from .gmail_component_capture_fix import apply_gmail_component_capture_fix
        from .protect_source_state_reset import apply_protect_source_state_reset
        from .protect_workflow_v2 import apply_protect_workflow_v2
        from .protect_top_area_design import apply_protect_top_area_design
        from .protect_view_experience import apply_protect_view_experience
        from .protect_privacy_check_persistence import (
            apply_protect_privacy_check_persistence,
        )
        from .protect_readability_finish import apply_protect_readability_finish
        from .protect_surface_guard import apply_protect_surface_guard

        apply_protect_usability_polish(main_window)
        apply_document_pipeline_v2_ui(main_window)
        apply_protect_session_upgrade(main_window)
        apply_protect_session_runtime_fix(main_window)

        # First engine migration: local Upload/Paste and materialized Drive files
        # now enter the generic ProtectPackage -> ProtectSessionService core. The
        # adapter deliberately mirrors compatibility state so the approved desktop
        # UI does not move. Gmail retains its proven route until its own migration.
        apply_local_protect_session_runtime(main_window)

        apply_gmail_package_browser(main_window)
        apply_gmail_package_runtime_fix(main_window)
        apply_gmail_component_session(main_window)
        apply_gmail_component_preview_polish(main_window)
        apply_gmail_component_capture_fix(main_window)
        apply_protect_source_state_reset(main_window)

        # Fresh workflow boundary: one Scan + Protect action plus a contextual
        # document/session Privacy Check. This intentionally does not reuse the
        # legacy AI Preflight dialog.
        apply_protect_workflow_v2(main_window)

        # First Gmail migration checkpoint: keep the proven Gmail component UI
        # authoritative, but mirror every selected body/attachment package into
        # the generic ProtectPackage contract. Install this after workflow-v2 so
        # its Clear/Scan signal rewiring cannot remove the shadow-state bridge.
        apply_gmail_protect_package_bridge(main_window)

        # Ensure the Privacy Check follows the actual protected-copy completion
        # even while older compatibility signals still hold bound callables from
        # before the workflow wrapper was installed.
        _wire_privacy_check_refresh_triggers(
            getattr(main_window, "protection_page", None)
        )

        # Approved visual hierarchy. Presentation only: the same controllers and
        # original provider logos remain in place underneath this treatment.
        apply_protect_top_area_design(main_window)

        # View/navigation clarity is intentionally layered after the approved
        # top design: it does not move controls or alter connector/protect logic;
        # it only makes SOURCE/VIEW state truthful and renders the active source's
        # protected text consistently.
        apply_protect_view_experience(main_window)

        # Privacy Check belongs to the completed protected session. Keep a stable
        # third VIEW control after the user opens document/text comparison views;
        # Clear (or an invalidated session) is the only thing that removes it.
        apply_protect_privacy_check_persistence(main_window)

        # Final readability polish for dense review controls and the findings
        # table. Presentation only; behavior and layout structure remain intact.
        apply_protect_readability_finish(main_window)

        # Must be last. It observes the final widget tree rather than trying to
        # guess which intermediate patch may still show a detached legacy child.
        apply_protect_surface_guard(main_window)

    completed.add(stage)