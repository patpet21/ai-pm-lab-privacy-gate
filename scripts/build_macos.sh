#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
ARCH="$(uname -m)"
CLOUDFLARED_VERSION="2026.7.3"

if [[ ! -x "$PYTHON" ]]; then
  echo "Project virtual environment not found." >&2
  exit 1
fi
APP_VERSION="$($PYTHON -c 'import ai_pm_lab_privacy_gate; print(ai_pm_lab_privacy_gate.__version__)')"
if [[ ! "$APP_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid PrivacyGate version: $APP_VERSION" >&2
  exit 1
fi

case "$ARCH" in
  arm64)
    RELEASE_ARCH="arm64"; DISPLAY_ARCH="Apple-Silicon"
    CLOUDFLARED_SHA256="90c5a4f914d705fd70c135dba6d80b1791d254b08d6d4136301941f88330dd09" ;;
  x86_64)
    RELEASE_ARCH="amd64"; DISPLAY_ARCH="Intel"
    CLOUDFLARED_SHA256="70d1c8684fa6d14b5843787ec8d1ea8e18b23650e424f4ea43d849a506487c3b" ;;
  *) echo "Unsupported macOS architecture: $ARCH" >&2; exit 1 ;;
esac

cd "$PROJECT_ROOT"
rm -rf build/macos build/macos-mcp build/macos-mcp-dist "dist/AI PM LAB Privacy Gate.app" "release/macos-$RELEASE_ARCH"
mkdir -p build/macos "release/macos-$RELEASE_ARCH"

ICONSET="build/macos/privacy-gate.iconset"
mkdir -p "$ICONSET"
for SIZE in 16 32 128 256 512; do
  sips -z "$SIZE" "$SIZE" resources/branding/privacy-gate-icon.png --out "$ICONSET/icon_${SIZE}x${SIZE}.png" >/dev/null
  DOUBLE=$((SIZE * 2))
  sips -z "$DOUBLE" "$DOUBLE" resources/branding/privacy-gate-icon.png --out "$ICONSET/icon_${SIZE}x${SIZE}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o build/macos/privacy-gate.icns

"$PYTHON" -m pytest
"$PYTHON" -m PyInstaller --noconfirm --clean packaging/macos/privacy_gate.spec
"$PYTHON" -m PyInstaller --noconfirm --clean --onedir \
  --name "AI PM LAB Privacy Gate MCP" --distpath build/macos-mcp-dist \
  --workpath build/macos-mcp --specpath build/macos-mcp --paths src \
  --collect-all mcp --copy-metadata mcp --copy-metadata mcp-types run_mcp.py

APP_RESOURCES="dist/AI PM LAB Privacy Gate.app/Contents/Resources"
cp -R "build/macos-mcp-dist/AI PM LAB Privacy Gate MCP" "$APP_RESOURCES/AI PM LAB Privacy Gate MCP"
CLOUDFLARED_ARCHIVE="build/macos/cloudflared.tgz"
curl --fail --location --retry 3 \
  "https://github.com/cloudflare/cloudflared/releases/download/$CLOUDFLARED_VERSION/cloudflared-darwin-$RELEASE_ARCH.tgz" \
  --output "$CLOUDFLARED_ARCHIVE"
echo "$CLOUDFLARED_SHA256  $CLOUDFLARED_ARCHIVE" | shasum -a 256 -c -
tar -xzf "$CLOUDFLARED_ARCHIVE" -C build/macos
install -m 755 build/macos/cloudflared "$APP_RESOURCES/cloudflared"

# Until Developer ID credentials are configured this remains an ad-hoc build.
# The updater additionally verifies the release SHA-256 and bundle identifier.
codesign --force --deep --sign - "dist/AI PM LAB Privacy Gate.app"
PRIVACY_GATE_SMOKE_TEST=1 "dist/AI PM LAB Privacy Gate.app/Contents/MacOS/AI PM LAB Privacy Gate"
"$APP_RESOURCES/cloudflared" version
test -x "$APP_RESOURCES/AI PM LAB Privacy Gate MCP/AI PM LAB Privacy Gate MCP"

BUNDLE_VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "dist/AI PM LAB Privacy Gate.app/Contents/Info.plist")
BUNDLE_ID=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "dist/AI PM LAB Privacy Gate.app/Contents/Info.plist")
if [[ "$BUNDLE_VERSION" != "$APP_VERSION" ]]; then
  echo "macOS bundle version mismatch: expected $APP_VERSION, found $BUNDLE_VERSION" >&2
  exit 1
fi
if [[ "$BUNDLE_ID" != "xyz.propertydex.privacygate" ]]; then
  echo "macOS bundle identifier mismatch: $BUNDLE_ID" >&2
  exit 1
fi

STAGE="build/macos/dmg-stage"
mkdir -p "$STAGE"
cp -R "dist/AI PM LAB Privacy Gate.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
DMG="release/macos-$RELEASE_ARCH/AI_PM_LAB_Privacy_Gate_${APP_VERSION}_${DISPLAY_ARCH}.dmg"
hdiutil create -volname "AI PM LAB Privacy Gate" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
shasum -a 256 "$DMG" > "release/macos-$RELEASE_ARCH/SHA256SUMS.txt"
cp BUILD_INFO.md CUSTOMER_GUIDE.md PRIVACY.md THIRD_PARTY_NOTICES.md "release/macos-$RELEASE_ARCH/"
