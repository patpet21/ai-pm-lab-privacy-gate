from pathlib import Path

from ai_pm_lab_privacy_gate.infrastructure.security.temporary_workspace import (
    as_read_once_path,
    delete_managed_path,
    is_managed_path,
    new_working_path,
)


def test_managed_working_paths_are_unique_and_inside_privacygate_temp_root():
    first = new_working_path("google_drive", "lease.pdf")
    second = new_working_path("google_drive", "lease.pdf")

    assert first != second
    assert is_managed_path(first)
    assert is_managed_path(second)


def test_delete_managed_path_refuses_normal_user_file(tmp_path):
    user_file = tmp_path / "customer-original.pdf"
    user_file.write_bytes(b"do not delete")

    assert not is_managed_path(user_file)
    assert delete_managed_path(user_file) is False
    assert user_file.read_bytes() == b"do not delete"


def test_gmail_read_once_path_removes_transport_file_after_read():
    target = new_working_path("gmail", "message.txt")
    target.write_text("Sensitive email body", encoding="utf-8")
    read_once = as_read_once_path(target)

    assert isinstance(read_once, Path)
    assert read_once.read_text(encoding="utf-8") == "Sensitive email body"
    assert not target.exists()
