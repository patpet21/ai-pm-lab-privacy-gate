from __future__ import annotations

"""Safety bridge for persisted manual sensitive values in the 2026 Protect UI.

The first manual-sensitive refinement correctly stored exact values locally and
encrypted, but its replay hook rendered the ordinary scan once and then rebuilt
the findings/preview a second time in the same Qt result callback.  The current
Protect runtime also routes local/Drive documents through ProtectSessionService,
whose immutable analysis must contain every selected finding.

This final bridge fixes both boundaries without changing the protection engine:
- persisted manual rules are merged *before* the normal analysis-ready render;
- local ProtectSession analysis receives the same namespaced manual findings;
- the existing UI/render path runs exactly once per scan;
- failures in the optional local-rule layer degrade to the normal scan instead of
  terminating the desktop process.

No exact value, document text, path, filename, workspace id or organization id is
sent to Supabase.  The existing encrypted LocalManualSensitiveStore remains the
authoritative persistence boundary.
"""

from dataclasses import replace
from types import MethodType

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QMessageBox

from ai_pm_lab_privacy_gate.application.local_protect_sources import compatibility_sources
from ai_pm_lab_privacy_gate.application.protect_session_service import namespace_findings
from ai_pm_lab_privacy_gate.ui import mockup_protect_manual_sensitive_2026 as manual


def _rules_for_document(page, document) -> tuple[tuple[str, str], ...]:
    store = getattr(page, "_protect_manual_sensitive_store", None)
    if store is None or document is None:
        return ()
    try:
        fingerprint = manual._document_fingerprint(document)
        return tuple(store.list_rules(fingerprint))
    except Exception:
        # A damaged/legacy local sidecar must never make Protect unusable.
        return ()


def _manual_findings(document, rules: tuple[tuple[str, str], ...]):
    rows = []
    seen: set[str] = set()
    for exact_text, entity_type in rules:
        try:
            additions = manual._manual_findings_for_text(document, exact_text, entity_type)
        except Exception:
            additions = ()
        for finding in additions:
            if finding.finding_id in seen:
                continue
            seen.add(finding.finding_id)
            rows.append(finding)
    return tuple(rows)


def _merge_without_duplicate_ids(existing, additions):
    rows = list(tuple(existing or ()))
    ids = {str(getattr(item, "finding_id", "") or "") for item in rows}
    added = 0
    for finding in tuple(additions or ()):
        finding_id = str(getattr(finding, "finding_id", "") or "")
        if not finding_id or finding_id in ids:
            continue
        rows.append(finding)
        ids.add(finding_id)
        added += 1
    return tuple(rows), added


def _inject_into_local_session(page, document, rules: tuple[tuple[str, str], ...]):
    """Return the authoritative session findings after adding local user rules."""

    analysis = getattr(page, "_local_protect_session_analysis", None)
    managed = bool(getattr(page, "_local_protect_session_managed", False))
    if not managed or analysis is None or not tuple(getattr(analysis, "sources", ()) or ()):
        additions = _manual_findings(document, rules)
        merged, added = _merge_without_duplicate_ids(getattr(page, "current_findings", ()), additions)
        return merged, added

    target_fingerprint = manual._document_fingerprint(document)
    updated_sources = []
    total_added = 0

    for source_analysis in analysis.sources:
        source_document = source_analysis.document
        try:
            same_document = manual._document_fingerprint(source_document) == target_fingerprint
        except Exception:
            same_document = source_document is document

        if not same_document:
            updated_sources.append(source_analysis)
            continue

        base_manual = _manual_findings(source_document, rules)
        namespaced = namespace_findings(base_manual, source_analysis.source.key)
        merged, added = _merge_without_duplicate_ids(source_analysis.findings, namespaced)
        updated_sources.append(replace(source_analysis, findings=merged))
        total_added += added

    if not total_added:
        return tuple(analysis.findings), 0

    updated_analysis = replace(analysis, sources=tuple(updated_sources))
    page._local_protect_session_analysis = updated_analysis

    # Keep the compatibility mirrors used by the current review/privacy-check UI
    # aligned with the same immutable session analysis.
    try:
        page._protect_session_sources = compatibility_sources(updated_analysis)
    except Exception:
        pass

    return tuple(updated_analysis.findings), total_added


def _prepare_payload(page, payload: object):
    if not isinstance(payload, tuple) or len(payload) != 2:
        return payload, 0

    document, findings = payload
    if document is None:
        return payload, 0

    rules = _rules_for_document(page, document)
    if not rules:
        return payload, 0

    # For ProtectSession the immutable session analysis is authoritative.  For a
    # legacy/non-session source, merge directly into the payload findings.
    if bool(getattr(page, "_local_protect_session_managed", False)) and getattr(
        page, "_local_protect_session_analysis", None
    ) is not None:
        merged, added = _inject_into_local_session(page, document, rules)
        return (document, merged), added

    additions = _manual_findings(document, rules)
    merged, added = _merge_without_duplicate_ids(findings, additions)
    return (document, merged), added


def _unwrap_pre_manual_analysis_ready(page):
    """Recover the handler captured by the first manual replay wrapper.

    The existing wrapper stores ``previous_analysis_ready`` in a Python closure.
    Reading that closure lets this safety layer replace the double-render wrapper
    without modifying any older Protect runtime or class-level controller.
    """

    current = getattr(page, "_analysis_ready", None)
    function = getattr(current, "__func__", None)
    closure = getattr(function, "__closure__", None) if function is not None else None
    freevars = getattr(getattr(function, "__code__", None), "co_freevars", ()) if function else ()
    if closure and freevars:
        for name, cell in zip(freevars, closure):
            if name != "previous_analysis_ready":
                continue
            try:
                candidate = cell.cell_contents
            except ValueError:
                continue
            if callable(candidate):
                return candidate
    return current


def _add_sensitive_safe(page) -> None:
    if page.current_document is None:
        QMessageBox.information(
            page,
            "Scan a source first",
            "Add a document or pasted text and run Scan & Protect before adding a missed sensitive value.",
        )
        return

    dialog = manual.AddSensitiveValueDialog(page)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    exact_text = dialog.value
    entity_type = dialog.entity_type

    try:
        raw_additions = manual._manual_findings_for_text(
            page.current_document,
            exact_text,
            entity_type,
        )
    except Exception:
        raw_additions = ()

    if not raw_additions:
        manual.ManualValueResultDialog(
            page,
            title="Exact text not found",
            detail=(
                "PrivacyGate could not find that wording in the locally extracted document text. "
                "Copy the exact word or phrase from Protected text or the source and try again."
            ),
            success=False,
        ).exec()
        return

    store = getattr(page, "_protect_manual_sensitive_store", None)
    if store is None:
        QMessageBox.warning(
            page,
            "Local protection rule unavailable",
            "PrivacyGate could not open the local encrypted rule store. Nothing was uploaded or saved remotely.",
        )
        return

    try:
        fingerprint = manual._document_fingerprint(page.current_document)
        stored_new = store.add_rule(
            fingerprint,
            source_kind=str(getattr(page.current_document, "source_kind", "") or ""),
            exact_text=exact_text,
            entity_type=entity_type,
        )

        if bool(getattr(page, "_local_protect_session_managed", False)) and getattr(
            page, "_local_protect_session_analysis", None
        ) is not None:
            merged, added = _inject_into_local_session(
                page,
                page.current_document,
                ((exact_text, entity_type),),
            )
            page.current_findings = merged
        else:
            merged, added = _merge_without_duplicate_ids(
                page.current_findings,
                raw_additions,
            )
            page.current_findings = merged

        # One authoritative regeneration only. This is the same existing review
        # and preview path used by checkbox changes.
        page._populate_findings()
        page._refresh_preview()
    except Exception:
        QMessageBox.warning(
            page,
            "Unable to apply the manual value",
            "The local rule was not applied to the current preview. PrivacyGate kept the document local and did not send the value anywhere.",
        )
        return

    if getattr(page, "_redesign_review_metric", None) is not None:
        page._redesign_review_metric.setText(
            f"Manual value protected · {max(1, added)} occurrence(s)"
        )

    manual.ManualValueResultDialog(
        page,
        title="Sensitive value added",
        detail=(
            f"{len(raw_additions)} occurrence(s) were added to Review and the protected copy was regenerated. "
            + (
                "The encrypted local rule will be reapplied when this same document content is scanned again."
                if stored_new
                else "This encrypted local rule was already saved for the document."
            )
        ),
        success=True,
    ).exec()


def apply_mockup_protect_manual_sensitive_runtime_fix_2026(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_protect_2026_manual_runtime_fixed", False)):
        return
    page._protect_2026_manual_runtime_fixed = True

    # Replace the first manual replay wrapper with a pre-merge wrapper so the
    # standard analysis-ready path renders once instead of twice.
    underlying_analysis_ready = _unwrap_pre_manual_analysis_ready(page)

    def analysis_ready_once(self, payload: object) -> None:
        prepared = payload
        added = 0
        try:
            prepared, added = _prepare_payload(self, payload)
        except Exception:
            # Optional local override failure must never prevent the normal scan.
            prepared, added = payload, 0

        if callable(underlying_analysis_ready):
            underlying_analysis_ready(prepared)

        if added and getattr(self, "_redesign_review_metric", None) is not None:
            QTimer.singleShot(
                0,
                lambda: self._redesign_review_metric.setText(
                    f"Protected copy ready · {added} saved manual finding(s) reapplied"
                ),
            )

    page._analysis_ready = MethodType(analysis_ready_once, page)

    # Replace every previously connected Add-sensitive slot. The button retains
    # its UI identity; only the controller callback is stabilized.
    try:
        page.add_sensitive_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass

    def add_sensitive(self) -> None:
        _add_sensitive_safe(self)

    page._add_sensitive_item = MethodType(add_sensitive, page)
    page.add_sensitive_button.clicked.connect(page._add_sensitive_item)
