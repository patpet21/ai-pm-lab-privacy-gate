from ai_pm_lab_privacy_gate.ui.protect_workflow_v2 import (
    SourcePrivacyCheck,
    build_privacy_check_summary,
)


def test_privacy_check_low_when_everything_is_protected_and_clean():
    summary = build_privacy_check_summary(
        (
            SourcePrivacyCheck("body", "Email body", detected=2, protected=2, residual=0),
            SourcePrivacyCheck("pdf", "Agreement.pdf", detected=3, protected=3, residual=0),
        )
    )

    assert summary.detected == 5
    assert summary.protected == 5
    assert summary.allowed == 0
    assert summary.residual == 0
    assert summary.risk == "LOW"
    assert summary.ready is True


def test_privacy_check_medium_when_user_keeps_detected_data_visible():
    summary = build_privacy_check_summary(
        (
            SourcePrivacyCheck("doc", "Lease.docx", detected=4, protected=3, residual=0),
        )
    )

    assert summary.allowed == 1
    assert summary.risk == "MEDIUM"
    assert summary.ready is False


def test_privacy_check_high_when_second_scan_finds_residual_data():
    summary = build_privacy_check_summary(
        (
            SourcePrivacyCheck("ppt", "Presentation.pptx", detected=4, protected=4, residual=1),
        )
    )

    assert summary.residual == 1
    assert summary.risk == "HIGH"
    assert summary.ready is False
