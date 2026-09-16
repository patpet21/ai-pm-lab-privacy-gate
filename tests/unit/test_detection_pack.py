from __future__ import annotations

import hashlib
import json

from ai_pm_lab_privacy_gate.domain.detection_pack import (
    DETECTION_PACK_SCHEMA,
    DETECTION_PACK_SCHEMA_VERSION,
    build_detection_pack,
    render_flutter_detection_pack,
)


def _without_digest(pack: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in pack.items() if key != "sha256"}


def test_detection_pack_is_stable_and_self_verifying() -> None:
    pack = build_detection_pack()

    assert pack["schema"] == DETECTION_PACK_SCHEMA
    assert pack["schema_version"] == DETECTION_PACK_SCHEMA_VERSION
    assert pack["default_profile_key"] == "general_business"
    assert pack["default_scope_key"] == "maximum"
    assert pack["default_language"] == "en"

    canonical = json.dumps(
        _without_digest(pack),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert pack["sha256"] == hashlib.sha256(canonical).hexdigest()


def test_detection_pack_contains_desktop_profiles_scopes_and_languages() -> None:
    pack = build_detection_pack()

    assert [item["key"] for item in pack["profiles"]] == [
        "general_business",
        "property_management",
        "realtor_brokerage",
        "projects_renovations",
        "construction",
        "legal",
        "healthcare_general",
    ]
    assert [item["key"] for item in pack["scopes"]] == [
        "essential",
        "financial",
        "business",
        "maximum",
        "custom",
    ]
    assert [item["code"] for item in pack["languages"]] == ["en", "it"]
    assert {"TENANT_ID", "RENT_AMOUNT", "PROPERTY_ACCESS_CODE"} <= set(
        pack["all_entities"]
    )


def test_flutter_export_is_generated_from_same_pack() -> None:
    rendered = render_flutter_detection_pack()

    assert "GENERATED FROM PRIVACYGATE DESKTOP" in rendered
    assert "generatedDetectionPackJson" in rendered
    assert build_detection_pack()["sha256"] in rendered
