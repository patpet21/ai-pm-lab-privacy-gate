from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class LocalProtector:
    """Protect small secrets with Windows DPAPI for the current Windows user."""

    @staticmethod
    def protect(value: str) -> bytes:
        raw = value.encode("utf-8")
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
        if sys.platform != "win32":
            return value.decode("utf-8")
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
            return ctypes.string_at(destination.pbData, destination.cbData).decode("utf-8")
        finally:
            ctypes.windll.kernel32.LocalFree(destination.pbData)
