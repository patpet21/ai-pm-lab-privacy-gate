from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "resources" / "branding" / "privacy-gate-icon.png"
BACKGROUND = (244, 247, 251, 255)


def render_asset(source: Image.Image, size: tuple[int, int], *, coverage: float) -> Image.Image:
    canvas = Image.new("RGBA", size, BACKGROUND)
    maximum = (max(1, int(size[0] * coverage)), max(1, int(size[1] * coverage)))
    logo = source.copy()
    logo.thumbnail(maximum, Image.Resampling.LANCZOS)
    position = ((size[0] - logo.width) // 2, (size[1] - logo.height) // 2)
    canvas.alpha_composite(logo, position)
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Microsoft Store/MSIX visual assets.")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE).convert("RGBA")
    assets = {
        "StoreLogo.png": ((50, 50), 0.88),
        "Square44x44Logo.png": ((44, 44), 0.88),
        "Square71x71Logo.png": ((71, 71), 0.86),
        "Square150x150Logo.png": ((150, 150), 0.84),
        "Square310x310Logo.png": ((310, 310), 0.78),
        "Wide310x150Logo.png": ((310, 150), 0.70),
        "SplashScreen.png": ((620, 300), 0.62),
    }
    for filename, (size, coverage) in assets.items():
        render_asset(source, size, coverage=coverage).save(args.output / filename, optimize=True)


if __name__ == "__main__":
    main()
