# Third-party open-source notices

AI PM LAB Privacy Gate is distributed under the MIT License. Its Windows package includes or depends on open-source components. The list below covers the primary runtime and build components used by version 0.4; their own license texts and notices remain authoritative.

| Component | Version used for 0.4 | License | Project |
|---|---:|---|---|
| Python | 3.12 | PSF License | https://www.python.org/ |
| PySide6 / Qt for Python | 6.11.1 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | https://pyside.org/ |
| Shiboken6 | 6.11.1 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | https://pyside.org/ |
| Microsoft Presidio Analyzer | 2.2.364 | MIT | https://github.com/microsoft/presidio |
| Microsoft Presidio Anonymizer | 2.2.364 | MIT | https://github.com/microsoft/presidio |
| spaCy | 3.8.15 | MIT | https://github.com/explosion/spaCy |
| spaCy `en_core_web_sm` model | 3.8.0 | MIT | https://github.com/explosion/spacy-models |
| pypdf | 6.15.0 | BSD-3-Clause | https://github.com/py-pdf/pypdf |
| pdfplumber | 0.11.10 | MIT | https://github.com/jsvine/pdfplumber |
| pdfminer.six | 20260107 | MIT | https://github.com/pdfminer/pdfminer.six |
| pypdfium2 / PDFium | 5.12.1 | BSD-3-Clause / Apache-2.0 and upstream notices | https://github.com/pypdfium2-team/pypdfium2 |
| ReportLab | 4.5.1 | BSD-style license | https://www.reportlab.com/ |
| Model Context Protocol Python SDK | 2.0.0 | MIT | https://github.com/modelcontextprotocol/python-sdk |
| PyInstaller | 6.22.0 | GPL-2.0-or-later with bootloader exception | https://pyinstaller.org/ |
| Inno Setup | 6.x | Inno Setup License (modified BSD-style) | https://jrsoftware.org/isinfo.php |

Transitive Python packages installed by these components are included only as required for runtime operation and retain their upstream licenses. No dependency is re-licensed by this project.

Qt is used through PySide6 under the LGPL option. The application uses the unmodified dynamically loaded Qt libraries supplied by PySide6. Recipients may replace compatible Qt/PySide shared libraries in accordance with the applicable license. Corresponding Qt and PySide source information is available from https://code.qt.io/ and https://download.qt.io/official_releases/QtForPython/.

Microsoft, Windows, GitHub, Netlify, Google Drive, Formspree, ChatGPT, Claude, n8n, and other product names are the property of their respective owners. Their names identify compatibility or optional services and do not imply endorsement.
