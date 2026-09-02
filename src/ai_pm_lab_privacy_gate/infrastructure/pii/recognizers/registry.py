from __future__ import annotations

from collections.abc import Callable, Iterable

from presidio_analyzer import RecognizerRegistry

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.english.address_v2 import (
    install_english_address_v2_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.english.residual_cleanup import (
    install_english_residual_cleanup_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.english.safe_recall import (
    install_english_safe_recall_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.english.semantic_context import (
    install_english_semantic_context_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian import (
    install_italian_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.real_estate import (
    install_real_estate_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.real_estate_sensitive_pack import (
    install_real_estate_sensitive_pack_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.universal_sensitive import (
    install_universal_sensitive_recognizers,
)


RecognizerInstaller = Callable[[RecognizerRegistry], None]
_ENGLISH_INSTALLERS: list[RecognizerInstaller] = [
    install_universal_sensitive_recognizers,
    install_english_address_v2_recognizers,
    install_english_safe_recall_recognizers,
    install_english_semantic_context_recognizers,
    install_english_residual_cleanup_recognizers,
    install_real_estate_recognizers,
    install_real_estate_sensitive_pack_recognizers,
]
_LANGUAGE_INSTALLERS: dict[str, list[RecognizerInstaller]] = {
    "en": _ENGLISH_INSTALLERS,
    "it": [install_italian_recognizers],
}


def register_installer(
    installer: RecognizerInstaller,
    language: str = "en",
) -> RecognizerInstaller:
    """Register a project recognizer installer for one document language."""
    code = language.strip().lower()
    _LANGUAGE_INSTALLERS.setdefault(code, []).append(installer)
    return installer


def install_custom_recognizers(
    registry: RecognizerRegistry,
    languages: Iterable[str] = ("en",),
) -> None:
    """Install local, project-specific recognizers for the requested languages."""
    installed: set[tuple[str, int]] = set()
    for language in languages:
        code = language.strip().lower()
        for installer in _LANGUAGE_INSTALLERS.get(code, ()):
            key = (code, id(installer))
            if key in installed:
                continue
            installer(registry)
            installed.add(key)
