def test_ui_redesign_imports():
    from ai_pm_lab_privacy_gate.ui import redesign

    assert callable(redesign.install_redesign)
