# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


project_dir = Path(SPECPATH).parent.parent
version_namespace = {}
exec(
    (project_dir / "src" / "ai_pm_lab_privacy_gate" / "__init__.py").read_text(encoding="utf-8"),
    version_namespace,
)
app_version = str(version_namespace["__version__"])
datas = []
binaries = []
hiddenimports = []

_DEV_ONLY_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cxx", ".cu", ".h", ".hh", ".hpp", ".pxd", ".pyi", ".pyx",
}


def runtime_package_data(entries):
    """Drop test/source-only files accidentally pulled in by collect_all()."""
    kept = []
    for source, destination in entries:
        normalized = destination.replace("\\", "/").lower()
        parts = {part for part in normalized.split("/") if part}
        if parts.intersection({"test", "tests", "testing", "benchmarks"}):
            continue
        if Path(source).suffix.lower() in _DEV_ONLY_SUFFIXES:
            continue
        kept.append((source, destination))
    return kept


for package in (
    "presidio_analyzer", "presidio_anonymizer", "spacy", "spacy_legacy",
    "spacy_loggers", "thinc", "srsly", "tldextract", "en_core_web_sm",
    "xx_ent_wiki_sm", "reportlab", "pdfplumber", "pdfminer", "pypdfium2",
    "docx", "openpyxl", "defusedxml", "rapidocr", "onnxruntime",
):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += runtime_package_data(package_datas)
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
        "CFBundleShortVersionString": app_version,
        "CFBundleVersion": app_version,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    },
)
