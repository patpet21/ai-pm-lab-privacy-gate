from __future__ import annotations

from dataclasses import dataclass, field

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.english.guardrails import (
    filter_english_contextual_results,
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


def test_general_document_labels_and_procedure_words_are_not_private_ner() -> None:
    text = """Residential Lease Agreement - Synthetic Test Document
COMPLETELY FICTITIOUS DATA - FOR PRIVACYGATE TESTING ONLY
Landlord: Michael Romano
EIN: 12-3456789
NY DOS Entity ID: 7654321
US_EIN / TAX_ID (Employer Identification Number)
PHONE_NUMBER
New York State Driver License No.: 123 456 789
U.S. Passport No.: 123456789
Vehicle license plate
Appendix A - Categories PrivacyGate should detect
Open Protect and select Document language: English.
Run Scan & Protect.
Verify the local Privacy Check.
Save or download the protected copy and inspect the TXT companion.
AI PM LAB PrivacyGate | Synthetic Test Fixture
Hudson Bridge Property Management LLC
Michael Romano
New York
"""
    results = [
        _result(text, "Synthetic Test", "ORGANIZATION"),
        _result(text, "COMPLETELY FICTITIOUS DATA", "ORGANIZATION"),
        _result(text, "Landlord", "PERSON"),
        _result(text, "EIN", "ORGANIZATION", occurrence=1),
        _result(text, "NY DOS Entity ID", "ORGANIZATION"),
        _result(text, "TAX_ID", "PERSON"),
        _result(text, "PHONE_NUMBER", "PERSON"),
        _result(text, "Driver License", "PERSON"),
        _result(text, "U.S. Passport", "ORGANIZATION"),
        _result(text, "Vehicle", "ORGANIZATION"),
        _result(text, "PrivacyGate", "ORGANIZATION", occurrence=2),
        _result(text, "Document", "PERSON", occurrence=2),
        _result(text, "English", "PERSON"),
        _result(text, "Scan & Protect", "ORGANIZATION"),
        _result(text, "Privacy Check", "PERSON"),
        _result(text, "TXT", "ORGANIZATION"),
        _result(text, "AI PM LAB", "ORGANIZATION"),
        _result(text, "Hudson Bridge Property Management LLC", "ORGANIZATION"),
        _result(text, "Michael Romano", "PERSON"),
        _result(text, "New York", "LOCATION", occurrence=2),
    ]

    filtered = filter_english_ner_results(
        text,
        results,
        profile_key="general_business",
    )
    kept = {(item.entity_type, text[item.start:item.end]) for item in filtered}

    assert kept == {
        ("ORGANIZATION", "Hudson Bridge Property Management LLC"),
        ("PERSON", "Michael Romano"),
        ("LOCATION", "New York"),
    }


def test_numeric_identifiers_are_not_kept_as_date_time_guesses() -> None:
    text = """Entity ID: 7654321
Registration No.: 004821
Block: 1165
BBL: 1011650042
Account number: 000123456789
Monthly rent amount
Date: March 14, 1981
Compact date: 20260901
Year: 2026
"""
    results = [
        _result(text, "7654321", "DATE_TIME"),
        _result(text, "004821", "DATE_TIME"),
        _result(text, "1165", "DATE_TIME"),
        _result(text, "1011650042", "DATE_TIME"),
        _result(text, "000123456789", "DATE_TIME"),
        _result(text, "Monthly", "DATE_TIME"),
        _result(text, "March 14, 1981", "DATE_TIME"),
        _result(text, "20260901", "DATE_TIME"),
        _result(text, "2026", "DATE_TIME"),
    ]

    filtered = filter_english_contextual_results(text, results)
    kept = {text[item.start:item.end] for item in filtered}

    assert kept == {"March 14, 1981", "20260901", "2026"}
