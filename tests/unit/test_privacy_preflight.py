from pathlib import Path
from types import SimpleNamespace

from ai_pm_lab_privacy_gate.ui.privacy_preflight import (
    build_preflight_snapshot,
    get_ai_destination,
)


class _Combo:
    def __init__(self, text: str) -> None:
        self._text = text

    def currentText(self) -> str:
        return self._text


class _Page:
    def __init__(self) -> None:
        self.profile_combo = _Combo("Property Management")
        self.scope_combo = _Combo("Financial + business sensitive")
        self.mode_combo = _Combo("Reversible placeholders")
        self._last_residual = ()

    def window(self):
        raise RuntimeError("No window needed in unit test")


def _finding(finding_id: str):
    return SimpleNamespace(finding_id=finding_id)


def test_preflight_safe_when_all_detected_items_are_protected() -> None:
    page = _Page()
    findings = (_finding("a"), _finding("b"), _finding("c"))
    page.current_findings = findings
    page.current_result = SimpleNamespace(applied_findings=findings)
    page.current_document = SimpleNamespace(source_path=Path("Lease.pdf"), source_kind="pdf")

    destination = get_ai_destination("chatgpt")
    snapshot = build_preflight_snapshot(
        page,
        destination=destination.label,
        delivery=destination.delivery,
        residual_findings=(),
    )

    assert snapshot.detected == 3
    assert snapshot.protected == 3
    assert snapshot.allowed == 0
    assert snapshot.residual == 0
    assert snapshot.ready is True
    assert snapshot.detected_original_data_leaving is False
    assert snapshot.source == "Local file"
    assert snapshot.item == "Lease.pdf"
    assert snapshot.destination == "ChatGPT / GPT"
    assert snapshot.delivery == "clipboard + browser"


def test_preflight_flags_allowed_and_residual_external_content() -> None:
    page = _Page()
    page.current_findings = (_finding("a"), _finding("b"), _finding("c"))
    page.current_result = SimpleNamespace(applied_findings=(_finding("a"), _finding("b")))
    page.current_document = SimpleNamespace(source_path=None, source_kind="txt")
    page._external_source_name = "Gmail • account@example.com • Security alert"
    page._external_source_metadata = {
        "provider": "gmail",
        "provider_label": "Gmail",
        "account_id": "account-1",
        "account_label": "account@example.com",
        "item_id": "message-1",
        "item_title": "Security alert",
        "item_kind": "email",
    }

    destination = get_ai_destination("claude")
    snapshot = build_preflight_snapshot(
        page,
        destination=destination.label,
        delivery=destination.delivery,
        residual_findings=(_finding("possible-1"),),
    )

    assert snapshot.detected == 3
    assert snapshot.protected == 2
    assert snapshot.allowed == 1
    assert snapshot.residual == 1
    assert snapshot.ready is False
    assert snapshot.detected_original_data_leaving is True
    assert snapshot.source == "Gmail"
    assert snapshot.account == "account@example.com"
    assert snapshot.item == "Security alert"
    assert snapshot.destination == "Claude"
    assert snapshot.delivery == "clipboard + browser"
    assert "Gmail" in snapshot.source_line
    assert "account@example.com" in snapshot.source_line
    assert "Security alert" in snapshot.source_line


def test_ai_destination_catalog_supports_chatgpt_claude_and_generic_ai() -> None:
    chatgpt = get_ai_destination("chatgpt")
    claude = get_ai_destination("claude")
    other = get_ai_destination("other")
    fallback = get_ai_destination("unknown-provider")

    assert chatgpt.url == "https://chatgpt.com/"
    assert chatgpt.delivery == "clipboard + browser"
    assert claude.url == "https://claude.ai/"
    assert claude.delivery == "clipboard + browser"
    assert other.url == ""
    assert other.delivery == "clipboard only"
    assert fallback.key == "other"
    assert fallback.delivery == "clipboard only"
