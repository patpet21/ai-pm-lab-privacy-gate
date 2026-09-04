from types import SimpleNamespace

from ai_pm_lab_privacy_gate.domain.models import ReplacementMapping
from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_restore_auto import (
    restore_from_local_ai_library,
    token_session_prefixes,
)


class FakeRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    def list_conversations(self):
        return tuple(
            SimpleNamespace(session_id=session_id)
            for session_id in self.sessions
        )

    def load_session(self, session_id):
        mappings = self.sessions.get(session_id)
        if mappings is None:
            return None
        return SimpleNamespace(session_id=session_id, mappings=tuple(mappings))


class FakePrivacyService:
    @staticmethod
    def restore_text(text, mappings):
        restored = text
        for mapping in mappings:
            restored = restored.replace(mapping.token, mapping.original_text)
        return restored


def test_extracts_session_prefix_from_namespaced_token() -> None:
    text = "Hello [[PG_B4A91A3A_T0001_PERSON_001]]"
    assert token_session_prefixes(text) == ("4a91a3a",)


def test_restores_token_from_prior_local_library_session() -> None:
    session_id = "4a91a3a01234567890abcdef12345678"
    token = "[[PG_B4A91A3A_T0001_PERSON_001]]"
    repository = FakeRepository(
        {
            session_id: (
                ReplacementMapping(
                    token=token,
                    entity_type="PERSON",
                    original_text="Pietro Forestieri",
                ),
            )
        }
    )

    restored, resolved = restore_from_local_ai_library(
        repository,  # type: ignore[arg-type]
        FakePrivacyService(),
        f"Candidate: {token}",
    )

    assert restored == "Candidate: Pietro Forestieri"
    assert resolved == (session_id,)


def test_ambiguous_session_prefix_fails_closed() -> None:
    token = "[[PG_B4A91A3A_T0001_PERSON_001]]"
    mapping = ReplacementMapping(
        token=token,
        entity_type="PERSON",
        original_text="Pietro Forestieri",
    )
    repository = FakeRepository(
        {
            "4a91a3a01234567890abcdef12345678": (mapping,),
            "4a91a3a0ffffffffffffffffffffffff": (mapping,),
        }
    )

    restored, resolved = restore_from_local_ai_library(
        repository,  # type: ignore[arg-type]
        FakePrivacyService(),
        token,
    )

    assert restored == token
    assert resolved == ()
