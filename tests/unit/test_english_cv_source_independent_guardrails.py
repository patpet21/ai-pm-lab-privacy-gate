from __future__ import annotations

from dataclasses import dataclass, field

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.english.guardrails import (
    filter_english_ner_results,
)


@dataclass
class _Result:
    entity_type: str
    start: int
    end: int
    score: float = 0.85
    recognition_metadata: dict[str, str] = field(
        default_factory=lambda: {"recognizer_name": "UnexpectedRecognizerMetadata"}
    )


def _result(text: str, value: str, entity_type: str, occurrence: int = 1) -> _Result:
    cursor = 0
    start = -1
    for _ in range(occurrence):
        start = text.index(value, cursor)
        cursor = start + len(value)
    return _Result(entity_type=entity_type, start=start, end=start + len(value))


def test_unambiguous_ai_and_skill_tools_are_filtered_even_with_unknown_metadata() -> None:
    text = """PROFILE
M.S. Project Management student and applied AI builder.
Documents are shared with AI systems.
AI governance and AI integration.
AI, RESEARCH & WORKFLOW SKILLS
AI & LLMs: ChatGPT, Claude, OpenAI Codex, Gemini, prompt design
Agents & Automation: MCP, n8n, Make.com, API workflows
Technical & Project Tools: GitHub, Supabase, Cloudflare, Replit, Notion, Asana
Tenex LLC
New York
"""
    results = [
        _result(text, "AI", "LOCATION", occurrence=2),
        _result(text, "Claude", "PERSON"),
        _result(text, "Gemini", "PERSON"),
        _result(text, "Replit", "PERSON"),
        _result(text, "Notion", "ORGANIZATION"),
        _result(text, "Tenex LLC", "ORGANIZATION"),
        _result(text, "New York", "LOCATION"),
    ]

    filtered = filter_english_ner_results(
        text,
        results,
        profile_key="general_business",
    )
    kept = {(item.entity_type, text[item.start:item.end]) for item in filtered}

    assert kept == {
        ("ORGANIZATION", "Tenex LLC"),
        ("LOCATION", "New York"),
    }


def test_remaining_cv_product_ai_and_education_noise_is_filtered_without_hiding_real_entities() -> None:
    text = """SELECTED APPLIED AI PROJECTS
PrivacyGate - local privacy protection for AI workflows.
AI Team collaboration and AI Agent prototypes.
Technical & Project Tools: Google ADK, GitHub, Supabase
EDUCATION
Degree in Civil and Environmental Engineering
Harrisburg University
Tenex LLC
New York
"""
    results = [
        _result(text, "PrivacyGate", "ORGANIZATION"),
        _result(text, "AI Team", "ORGANIZATION"),
        _result(text, "AI Agent", "PERSON"),
        _result(text, "Google ADK", "ORGANIZATION"),
        _result(text, "Degree in", "PERSON"),
        _result(text, "Harrisburg University", "ORGANIZATION"),
        _result(text, "Tenex LLC", "ORGANIZATION"),
        _result(text, "New York", "LOCATION"),
    ]

    filtered = filter_english_ner_results(
        text,
        results,
        profile_key="general_business",
    )
    kept = {(item.entity_type, text[item.start:item.end]) for item in filtered}

    assert kept == {
        ("ORGANIZATION", "Harrisburg University"),
        ("ORGANIZATION", "Tenex LLC"),
        ("LOCATION", "New York"),
    }
