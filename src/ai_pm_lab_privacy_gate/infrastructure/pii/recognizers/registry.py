from __future__ import annotations

from collections.abc import Callable

from presidio_analyzer import RecognizerRegistry


RecognizerInstaller = Callable[[RecognizerRegistry], None]
_INSTALLERS: list[RecognizerInstaller] = []


def register_installer(installer: RecognizerInstaller) -> RecognizerInstaller:
    """Registration hook for future real-estate recognizer modules."""
    _INSTALLERS.append(installer)
    return installer


def install_custom_recognizers(registry: RecognizerRegistry) -> None:
    """Install project-specific recognizers. The v0.1 registry is intentionally empty."""
    for installer in _INSTALLERS:
        installer(registry)

