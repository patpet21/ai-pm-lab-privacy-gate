# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


project_dir = Path(SPECPATH).parent.parent
datas = []
binaries = []
hiddenimports = []

for package in (
    "presidio_analyzer", "presidio_anonymizer", "spacy", "spacy_legacy",
    "spacy_loggers", "thinc", "srsly", "tldextract", "en_core_web_sm",
    "xx_ent_wiki_sm", "reportlab", "pdfplumber", "pdfminer", "pypdfium2",
    "docx", "openpyxl", "defusedxml", "rapidocr", "onnxruntime",
):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

for distribution in (
    "presidio-analyzer", "presidio-anonymizer", "spacy", "en-core-web-sm",
    "xx-ent-wiki-sm", "reportlab", "pdfplumber", "pdfminer.six", "pypdfium2",
    "python-docx", "openpyxl", "defusedxml", "rapidocr", "onnxruntime",
):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        pass

datas += [
    (str(project_dir / "resources" / "presidio"), "resources/presidio"),
    (str(project_dir / "resources" / "branding"), "resources/branding"),
]

a = Analysis(
    [str(project_dir / "run_app.py")], pathex=[str(project_dir / "src")],
    binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "notebook"],
    noarchive=False, optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="AI PM LAB Privacy Gate", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon=str(project_dir / "build" / "macos" / "privacy-gate.icns"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="AI PM LAB Privacy Gate")
app = BUNDLE(
    coll, name="AI PM LAB Privacy Gate.app",
    icon=str(project_dir / "build" / "macos" / "privacy-gate.icns"),
    bundle_identifier="xyz.propertydex.privacygate",
    info_plist={
        "CFBundleDisplayName": "AI PM LAB Privacy Gate",
        "CFBundleShortVersionString": "0.4.2",
        "CFBundleVersion": "0.4.2",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    },
)
