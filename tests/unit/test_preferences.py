from __future__ import annotations

import socket

from ai_pm_lab_privacy_gate.infrastructure.settings.preferences import (
    AppPreferences,
    PreferencesStore,
    is_port_available,
)


def test_preferences_round_trip(tmp_path):
    store = PreferencesStore(tmp_path)
    expected = AppPreferences(close_behavior="background", port_mode="manual", manual_port=9876)
    store.save(expected)
    assert store.load() == expected


def test_preferences_invalid_values_fall_back(tmp_path):
    (tmp_path / "preferences.json").write_text(
        '{"close_behavior":"bad","port_mode":"bad","manual_port":1}',
        encoding="utf-8",
    )
    assert store_defaults(PreferencesStore(tmp_path).load())


def store_defaults(prefs: AppPreferences) -> bool:
    return (
        prefs.close_behavior == "ask"
        and prefs.port_mode == "automatic"
        and prefs.manual_port == 8766
    )


def test_port_availability_detects_bound_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        assert not is_port_available(port)
