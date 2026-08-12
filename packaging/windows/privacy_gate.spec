# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


project_dir = Path(SPECPATH).parent.parent

datas = []
binaries = []
hiddenimports = []

for package in (
    "presidio_analyzer",
    "presidio_anonymizer",
    "spacy",
    "spacy_legacy",
    "spacy_loggers",
    "thinc",
    "srsly",
    "tldextract",
    "en_core_web_sm",
    "reportlab",
    "pdfplumber",
    "pdfminer",
    "pypdfium2",
    "docx",
    "openpyxl",
    "defusedxml",
):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

for distribution in (
    "presidio-analyzer",
    "presidio-anonymizer",
    "spacy",
    "en-core-web-sm",
    "reportlab",
    "pdfplumber",
    "pdfminer.six",
    "pypdfium2",
    "python-docx",
    "openpyxl",
    "defusedxml",
):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        pass

# Keep the Microsoft C/C++ runtime app-local. PyInstaller normally discovers
# these DLLs, but adding them explicitly makes the packaged Python runtime
# independent from the customer's global VC++ Redistributable installation.
runtime_candidates = [
    Path(sys.base_prefix) / "vcruntime140.dll",
    Path(sys.base_prefix) / "vcruntime140_1.dll",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "msvcp140.dll",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "msvcp140_1.dll",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "msvcp140_2.dll",
]
for runtime_dll in runtime_candidates:
    if runtime_dll.exists():
        binaries.append((str(runtime_dll), "."))

datas += [
    (str(project_dir / "resources" / "presidio"), "resources/presidio"),
    (str(project_dir / "resources" / "branding"), "resources/branding"),
]

a = Analysis(
    [str(project_dir / "run_app.py")],
    pathex=[str(project_dir / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "notebook"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI PM LAB Privacy Gate",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_dir / "resources" / "branding" / "privacy-gate.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AI PM LAB Privacy Gate",
)
