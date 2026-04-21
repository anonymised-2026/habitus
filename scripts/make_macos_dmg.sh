#!/bin/bash
set -e
# Create a .dmg installer from dist/HABITUS.app.

VERSION=$(grep -oE 'APP_VERSION\s*=\s*"[^"]+"' version.py | head -1 | grep -oE '"[^"]+"' | tr -d '"')
: ${VERSION:="1.0.0"}
APP_PATH="dist/HABITUS.app"
DMG="HABITUS_Setup_v${VERSION}_macOS.dmg"

if [ ! -d "$APP_PATH" ]; then
  echo "$APP_PATH not found — cannot build DMG" >&2
  exit 1
fi

rm -f "$DMG"

create-dmg \
  --volname "HABITUS ${VERSION}" \
  --window-size 560 360 \
  --icon-size 100 \
  --icon "HABITUS.app" 140 180 \
  --app-drop-link 420 180 \
  --hide-extension "HABITUS.app" \
  "$DMG" "$APP_PATH"

ls -la "$DMG"
echo "DMG ready: $DMG"
