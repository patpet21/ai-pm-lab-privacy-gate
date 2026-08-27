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

    install_redesign()
    install_protect_ghost_cleanup()
    install_protect_quick_actions()
    _INSTALLED = True


def _completed_stages(main_window) -> set[str]:
    stages = getattr(main_window, "_privacygate_protect_runtime_stages", None)
    if not isinstance(stages, set):
        stages = set()
        main_window._privacygate_protect_runtime_stages = stages
    return stages


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
        from .gmail_package_browser import apply_gmail_package_browser
        from .gmail_package_runtime_fix import apply_gmail_package_runtime_fix
        from .gmail_component_session import apply_gmail_component_session
        from .gmail_component_preview_polish import apply_gmail_component_preview_polish
        from .gmail_component_capture_fix import apply_gmail_component_capture_fix
        from .protect_source_state_reset import apply_protect_source_state_reset
        from .protect_workflow_v2 import apply_protect_workflow_v2
        from .protect_surface_guard import apply_protect_surface_guard

        apply_protect_usability_polish(main_window)
        apply_document_pipeline_v2_ui(main_window)
        apply_protect_session_upgrade(main_window)
        apply_protect_session_runtime_fix(main_window)
        apply_gmail_package_browser(main_window)
        apply_gmail_package_runtime_fix(main_window)
        apply_gmail_component_session(main_window)
        apply_gmail_component_preview_polish(main_window)
        apply_gmail_component_capture_fix(main_window)
        apply_protect_source_state_reset(main_window)

        # Fresh workflow boundary: one Scan & Protect action plus a contextual
        # document/session Privacy Check. This intentionally does not reuse the
        # legacy AI Preflight dialog.
        apply_protect_workflow_v2(main_window)

        # Must be last. It observes the final widget tree rather than trying to
        # guess which intermediate patch may still show a detached legacy child.
        apply_protect_surface_guard(main_window)

    completed.add(stage)
