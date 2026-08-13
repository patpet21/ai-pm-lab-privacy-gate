from ai_pm_lab_privacy_gate.infrastructure.updates.update_service import UpdateService, _version_tuple


def test_version_tuple_compares_semantic_versions():
    assert _version_tuple("v0.4.1") > _version_tuple("0.4.0")
    assert _version_tuple("0.10.0") > _version_tuple("0.9.9")


def test_update_service_returns_platform_package(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "version": "0.4.1",
                "notes_url": "https://example.test/notes",
                "downloads": {
                    "windows": {"url": "https://example.test/app.exe", "sha256": "abc"},
                    "macos_apple_silicon": {"url": "https://example.test/arm.dmg", "sha256": "def"},
                    "macos_intel": {"url": "https://example.test/intel.dmg", "sha256": "ghi"},
                },
            }

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr("ai_pm_lab_privacy_gate.infrastructure.updates.update_service.httpx.Client", Client)
    monkeypatch.setattr("ai_pm_lab_privacy_gate.infrastructure.updates.update_service.platform.system", lambda: "Windows")
    update = UpdateService("https://example.test/release.json").check("0.4.0")
    assert update is not None
    assert update.version == "0.4.1"
    assert update.download_url.endswith("app.exe")


def test_update_service_ignores_same_version(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"version": "0.4.0"}

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr("ai_pm_lab_privacy_gate.infrastructure.updates.update_service.httpx.Client", Client)
    assert UpdateService().check("0.4.0") is None
