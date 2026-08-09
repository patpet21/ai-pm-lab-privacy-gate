from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
BRANDING = ROOT / "resources" / "branding"
WEB_ASSETS = ROOT / "web-demo" / "assets"
SOURCE = BRANDING / "privacy-gate-logo.png"


def content_crop(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    white = Image.new("RGB", rgb.size, "white")
    difference = ImageChops.difference(rgb, white).convert("L")
    difference = difference.point(lambda value: 255 if value > 12 else 0)
    box = difference.getbbox()
    if box is None:
        return image
    left, top, right, bottom = box
    padding = max(18, int(max(right - left, bottom - top) * 0.035))
    return image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )


def build_icon() -> Image.Image:
    source = content_crop(Image.open(SOURCE).convert("RGBA"))
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((18, 18, 1006, 1006), radius=210, fill="#071F36")
    draw.rounded_rectangle((55, 55, 969, 969), radius=180, fill="#FFFFFF", outline="#BD9850", width=18)
    source.thumbnail((820, 820), Image.Resampling.LANCZOS)
    x = (canvas.width - source.width) // 2
    y = (canvas.height - source.height) // 2 - 4
    canvas.alpha_composite(source, (x, y))
    return canvas


def main() -> None:
    WEB_ASSETS.mkdir(parents=True, exist_ok=True)
    icon = build_icon()
    icon.save(BRANDING / "privacy-gate-icon.png", optimize=True)
    icon.save(
        BRANDING / "privacy-gate.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    icon.resize((256, 256), Image.Resampling.LANCZOS).save(
        WEB_ASSETS / "privacy-gate-icon.png", optimize=True
    )


if __name__ == "__main__":
    main()
