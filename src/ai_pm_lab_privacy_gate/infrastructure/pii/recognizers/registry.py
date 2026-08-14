from __future__ import annotations

from collections.abc import Callable

from presidio_analyzer import RecognizerRegistry

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
_INSTALLERS: list[RecognizerInstaller] = [
    install_universal_sensitive_recognizers,
    install_real_estate_recognizers,
    install_real_estate_sensitive_pack_recognizers,
]


def register_installer(installer: RecognizerInstaller) -> RecognizerInstaller:
    """Registration hook for future real-estate recognizer modules."""
    _INSTALLERS.append(installer)
    return installer


def install_custom_recognizers(registry: RecognizerRegistry) -> None:
    """Install local, project-specific recognizers."""
    for installer in _INSTALLERS:
        installer(registry)
