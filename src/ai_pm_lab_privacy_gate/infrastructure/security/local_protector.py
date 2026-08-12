from __future__ import annotations

import ctypes
import base64
import os
import subprocess
import sys
from ctypes import wintypes
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_MAC_PREFIX = b"PGM1"


@lru_cache(maxsize=1)
def _mac_master_key() -> bytes:
    service = "AI PM LAB Privacy Gate Local Data"
    account = "library-master-key"
    result = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return base64.b64decode(result.stdout.strip(), validate=True)
    key = os.urandom(32)
    encoded = base64.b64encode(key).decode("ascii")
    subprocess.run(
        ["security", "add-generic-password", "-U", "-s", service, "-a", account, "-w", encoded],
        check=True,
        capture_output=True,
        text=True,
    )
    return key


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class LocalProtector:
    """Protect small secrets with Windows DPAPI for the current Windows user."""

    @staticmethod
    def protect(value: str) -> bytes:
        return LocalProtector.protect_bytes(value.encode("utf-8"))

    @staticmethod
    def protect_bytes(raw: bytes) -> bytes:
        if sys.platform == "darwin":
            nonce = os.urandom(12)
            return _MAC_PREFIX + nonce + AESGCM(_mac_master_key()).encrypt(nonce, raw, _MAC_PREFIX)
        if sys.platform != "win32":
            return raw
        source_buffer = ctypes.create_string_buffer(raw)
        source = _DataBlob(len(raw), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
        destination = _DataBlob()
        if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(source),
            "AI PM LAB Privacy Gate",
            None,
            None,
            None,
            0x01,
            ctypes.byref(destination),
        ):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(destination.pbData, destination.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(destination.pbData)

    @staticmethod
    def unprotect(value: bytes) -> str:
        return LocalProtector.unprotect_bytes(value).decode("utf-8")

    @staticmethod
    def unprotect_bytes(value: bytes) -> bytes:
        if sys.platform == "darwin":
            if not value.startswith(_MAC_PREFIX) or len(value) < len(_MAC_PREFIX) + 13:
                raise ValueError("Unsupported or unencrypted Privacy Gate data")
            nonce = value[len(_MAC_PREFIX) : len(_MAC_PREFIX) + 12]
            ciphertext = value[len(_MAC_PREFIX) + 12 :]
            return AESGCM(_mac_master_key()).decrypt(nonce, ciphertext, _MAC_PREFIX)
        if sys.platform != "win32":
            return value
        source_buffer = ctypes.create_string_buffer(value)
        source = _DataBlob(len(value), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
        destination = _DataBlob()
        if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(source),
            None,
            None,
            None,
            None,
            0x01,
            ctypes.byref(destination),
        ):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(destination.pbData, destination.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(destination.pbData)
