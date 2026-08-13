from pathlib import Path

import pytest

from ai_pm_lab_privacy_gate.infrastructure.documents.office_preview import OfficePreviewRenderer


def test_office_preview_explains_optional_renderer(monkeypatch, tmp_path):
    renderer = OfficePreviewRenderer()
    monkeypatch.setattr(renderer, "find_executable", lambda: None)
    source = tmp_path / "sample.docx"
    source.write_bytes(b"not needed for availability test")
    with pytest.raises(RuntimeError, match="LibreOffice"):
        renderer.render(source, tmp_path / "output")


def test_office_preview_finds_configured_path(monkeypatch, tmp_path):
    executable = tmp_path / "soffice.exe"
    executable.write_bytes(b"")
    monkeypatch.setattr("ai_pm_lab_privacy_gate.infrastructure.documents.office_preview.shutil.which", lambda _name: str(executable))
    assert OfficePreviewRenderer().find_executable() == Path(executable)
