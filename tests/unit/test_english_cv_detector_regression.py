from __future__ import annotations

from dataclasses import dataclass, field

from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, Finding, PageContent
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.english.guardrails import (
    email_linked_person_findings,
    filter_english_ner_results,
    propagate_known_ner_values,
)


@dataclass
class _NerResult:
    entity_type: str
    start: int
    end: int
    score: float = 0.85
    recognition_metadata: dict[str, str] = field(
        default_factory=lambda: {"recognizer_name": "SpacyRecognizer"}
    )


def _result(text: str, value: str, entity_type: str, *, occurrence: int = 1) -> _NerResult:
    start = -1
    cursor = 0
    for _ in range(occurrence):
        start = text.index(value, cursor)
        cursor = start + len(value)
    return _NerResult(entity_type=entity_type, start=start, end=start + len(value))


def _finding(text: str, value: str, entity_type: str, *, occurrence: int = 1) -> Finding:
    result = _result(text, value, entity_type, occurrence=occurrence)
    return Finding(
        finding_id=f"seed-{entity_type}-{result.start}-{result.end}",
        entity_type=entity_type,
        text=text[result.start : result.end],
        start=result.start,
        end=result.end,
        score=0.95,
        page_number=1,
        context=text[max(0, result.start - 20) : result.end + 20],
    )


def test_general_business_cv_filters_obvious_ner_noise() -> None:
    text = """APPLIED AI | PROJECT MANAGEMENT | RESEARCH & AUTOMATION
PROFILE
M.S. Project Management student and applied AI builder with hands-on experience.
AI & LLMs: ChatGPT, Claude, OpenAI Codex, Gemini, prompt design, AI-assisted research
Technical & Project Tools: GitHub, Supabase, Cloudflare, Replit, Notion, Asana, ClickUp, Trello
Coordinated technical activities across private and public projects.
Prepared technical plans, estimates, drawings, reports, and project documentation.
Supported multidisciplinary teams on major infrastructure projects.
Tenex LLC
New York
"""
    results = [
        _result(text, "APPLIED AI", "ORGANIZATION"),
        _result(text, "PROJECT MANAGEMENT", "ORGANIZATION"),
        _result(text, "PROFILE", "ORGANIZATION"),
        _result(text, "AI", "LOCATION", occurrence=3),
        _result(text, "ChatGPT", "ORGANIZATION"),
        _result(text, "Claude", "PERSON"),
        _result(text, "GitHub", "ORGANIZATION"),
        _result(text, "Coordinated", "ORGANIZATION"),
        _result(text, "Prepared", "ORGANIZATION"),
        _result(text, "Supported", "ORGANIZATION"),
        _result(text, "Tenex LLC", "ORGANIZATION"),
        _result(text, "New York", "LOCATION"),
    ]

    filtered = filter_english_ner_results(
        text,
        results,
        profile_key="general_business",
    )
    kept = {(item.entity_type, text[item.start : item.end]) for item in filtered}

    assert kept == {
        ("ORGANIZATION", "Tenex LLC"),
        ("LOCATION", "New York"),
    }


def test_general_business_cv_filters_ai_concepts_and_wrapped_skill_tools() -> None:
    text = """PROFILE
Applied AI builder creating AI-powered tools and local AI models.
Business documents are shared with AI systems.
Built a proof of concept connecting POS data with AI-based operational analysis.
Prototype practical uses of AI-assisted workflows.
AI & LLMs:
ChatGPT, Claude, OpenAI Codex, Gemini, prompt design, Microsoft Presidio, spaCy
Technical & Project Tools:
GitHub, Supabase, Cloudflare, Replit, Notion, Asana, ClickUp, Trello
PROFESSIONAL EXPERIENCE
Coordinated technical activities across private and public projects.
Prepared technical plans, estimates, drawings, reports, and project documentation.
Supported multidisciplinary teams on major infrastructure projects.
Impresa Pizzarotti
Italy
"""
    results = [
        _result(text, "AI-powered tools", "ORGANIZATION"),
        _result(text, "local AI models", "ORGANIZATION"),
        _result(text, "AI systems", "LOCATION"),
        _result(text, "AI-based operational analysis", "LOCATION"),
        _result(text, "AI-assisted workflows", "LOCATION"),
        _result(text, "ChatGPT", "ORGANIZATION"),
        _result(text, "Claude", "PERSON"),
        _result(text, "Microsoft Presidio", "ORGANIZATION"),
        _result(text, "spaCy", "PERSON"),
        _result(text, "GitHub", "ORGANIZATION"),
        _result(text, "Supabase", "PERSON"),
        _result(text, "Coordinated technical activities", "ORGANIZATION"),
        _result(text, "Prepared technical plans", "ORGANIZATION"),
        _result(text, "Supported multidisciplinary teams", "ORGANIZATION"),
        _result(text, "Impresa Pizzarotti", "ORGANIZATION"),
        _result(text, "Italy", "LOCATION"),
    ]

    filtered = filter_english_ner_results(
        text,
        results,
        profile_key="general_business",
    )
    kept = {(item.entity_type, text[item.start : item.end]) for item in filtered}

    assert kept == {
        ("ORGANIZATION", "Impresa Pizzarotti"),
        ("LOCATION", "Italy"),
    }


def test_personal_email_recovers_repeated_full_name_in_cv() -> None:
    text = (
        "Marco Bianchi | AI Talent Intern\n"
        "MARCO BIANCHI\n"
        "New York, NY | marco.bianchi@example.test\n"
    )
    email_start = text.index("marco.bianchi@example.test")
    email = Finding(
        finding_id="email-1",
        entity_type="EMAIL_ADDRESS",
        text="marco.bianchi@example.test",
        start=email_start,
        end=email_start + len("marco.bianchi@example.test"),
        score=0.99,
        page_number=1,
        context=text,
    )
    document = AnalysisDocument(
        source_kind="text",
        pages=(PageContent(page_number=1, text=text),),
    )

    recovered = email_linked_person_findings(document, (email,))
    person_values = [item.text for item in recovered if item.entity_type == "PERSON"]

    assert person_values == ["Marco Bianchi", "MARCO BIANCHI"]


def test_known_english_person_is_propagated_to_missed_duplicate() -> None:
    text = "Marco Bianchi | AI Talent Intern\nMARCO BIANCHI\n"
    document = AnalysisDocument(
        source_kind="text",
        pages=(PageContent(page_number=1, text=text),),
    )
    first = _finding(text, "Marco Bianchi", "PERSON")

    propagated = propagate_known_ner_values(document, (first,))
    person_values = [item.text for item in propagated if item.entity_type == "PERSON"]

    assert person_values == ["Marco Bianchi", "MARCO BIANCHI"]
