from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


class OfficePreviewRenderer:
    """Render local Office documents to PDF without uploading their contents."""

    def find_executable(self) -> Path | None:
        names = ("soffice.exe", "soffice") if sys.platform == "win32" else ("soffice",)
        for name in names:
            located = shutil.which(name)
            if located:
                return Path(located)
        candidates: list[Path] = []
        if sys.platform == "win32":
            for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
                root = os.environ.get(variable)
                if root:
                    candidates.append(Path(root) / "LibreOffice" / "program" / "soffice.exe")
        elif sys.platform == "darwin":
            candidates.append(Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"))
        else:
            candidates.extend((Path("/usr/bin/soffice"), Path("/usr/lib/libreoffice/program/soffice")))
        return next((candidate for candidate in candidates if candidate.is_file()), None)

    def render(self, source: str | Path, output_directory: str | Path) -> Path:
        executable = self.find_executable()
        if executable is None:
            raise RuntimeError(
                "Install LibreOffice to enable exact local Word/Excel page previews. "
                "Protection and same-format export remain available without it."
            )
        source_path = Path(source).resolve()
        output = Path(output_directory).resolve()
        output.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [
                str(executable),
                "--headless",
                "--nologo",
                "--nodefault",
                "--nolockcheck",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output),
                str(source_path),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        rendered = output / f"{source_path.stem}.pdf"
        if completed.returncode or not rendered.exists():
            detail = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(f"LibreOffice could not render this document. {detail}".strip())
        return rendered
