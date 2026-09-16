from __future__ import annotations

import hashlib
import json

from ai_pm_lab_privacy_gate.domain.profiles import (
    BUSINESS_CONFIDENTIAL_ENTITIES,
    COMMON_US_ENTITIES,
    DEFAULT_PROFILE_KEY,
    DEFAULT_SCOPE_KEY,
    FINANCIAL_SENSITIVE_ENTITIES,
    OPERATIONAL_IDENTIFIER_ENTITIES,
    REAL_ESTATE_SENSITIVE_ENTITIES,
    TECHNICAL_SECRET_ENTITIES,
    list_profiles,
    list_scopes,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.languages import (
    DEFAULT_DOCUMENT_LANGUAGE,
    LANGUAGE_CONFIGS,
)

DETECTION_PACK_SCHEMA = "privacygate-detection-pack"
DETECTION_PACK_SCHEMA_VERSION = 1

_SCOPE_RULES: dict[str, tuple[str, tuple[str, ...]]] = {
    "essential": ("intersection", ("common_us", "real_estate_sensitive")),
    "financial": (
        "intersection",
        ("common_us", "financial_sensitive", "real_estate_sensitive"),
    ),
    "business": (
        "intersection",
        (
            "common_us",
            "operational_identifier",
            "business_confidential",
            "real_estate_sensitive",
        ),
    ),
    "maximum": ("all_profiles", ()),
    "custom": ("profile", ()),
}


def _dedupe(values) -> list[str]:
    return list(dict.fromkeys(values))


def _canonical_payload(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build_detection_pack() -> dict[str, object]:
    """Build the portable detection taxonomy from Desktop source-of-truth data.

    This pack contains taxonomy/configuration only. It intentionally contains no
    user content, detector findings, restore mappings, secrets, or pairing data.
    """

    entity_groups = {
        "common_us": list(COMMON_US_ENTITIES),
        "financial_sensitive": list(FINANCIAL_SENSITIVE_ENTITIES),
        "business_confidential": list(BUSINESS_CONFIDENTIAL_ENTITIES),
        "technical_secret": list(TECHNICAL_SECRET_ENTITIES),
        "operational_identifier": list(OPERATIONAL_IDENTIFIER_ENTITIES),
        "real_estate_sensitive": list(REAL_ESTATE_SENSITIVE_ENTITIES),
    }

    profiles = [
        {
            "key": profile.key,
            "name": profile.name,
            "description": profile.description,
            "threshold": float(profile.threshold),
            "entities": list(profile.entities),
        }
        for profile in list_profiles()
    ]
    scopes = []
    for scope in list_scopes():
        mode, groups = _SCOPE_RULES[scope.key]
        scopes.append(
            {
                "key": scope.key,
                "name": scope.name,
                "description": scope.description,
                "mode": mode,
                "groups": list(groups),
            }
        )

    languages = [
        {
            "code": config.code,
            "label": config.label,
            "desktop_model": config.model_name,
        }
        for config in LANGUAGE_CONFIGS.values()
    ]
    all_entities = _dedupe(
        entity for profile in list_profiles() for entity in profile.entities
    )

    payload: dict[str, object] = {
        "schema": DETECTION_PACK_SCHEMA,
        "schema_version": DETECTION_PACK_SCHEMA_VERSION,
        "default_profile_key": DEFAULT_PROFILE_KEY,
        "default_scope_key": DEFAULT_SCOPE_KEY,
        "default_language": DEFAULT_DOCUMENT_LANGUAGE,
        "entity_groups": entity_groups,
        "profiles": profiles,
        "scopes": scopes,
        "languages": languages,
        "semantic_entities": ["PERSON", "ORGANIZATION", "LOCATION"],
        "all_entities": all_entities,
        "engines": {
            "desktop": {
                "kind": "presidio_spacy",
                "semantic_ner": True,
            },
            "mobile_basic": {
                "kind": "deterministic_rules",
                "semantic_ner": False,
            },
            "mobile_enhanced": {
                "kind": "onnx_ner",
                "semantic_ner": True,
                "availability": "optional",
            },
        },
    }
    payload["sha256"] = hashlib.sha256(_canonical_payload(payload)).hexdigest()
    return payload


def detection_pack_json(*, indent: int | None = 2) -> str:
    return json.dumps(build_detection_pack(), ensure_ascii=False, indent=indent)


def render_flutter_detection_pack() -> str:
    """Render the checked-in Mobile snapshot; never hand-edit that Dart file."""

    payload = detection_pack_json(indent=2)
    return (
        "// GENERATED FROM PRIVACYGATE DESKTOP. DO NOT EDIT BY HAND.\n"
        "// Source: ai_pm_lab_privacy_gate.domain.detection_pack\n\n"
        "const generatedDetectionPackJson = r'''\n"
        f"{payload}\n"
        "''';\n"
    )
