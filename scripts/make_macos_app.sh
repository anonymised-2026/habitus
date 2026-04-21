#!/bin/bash
set -e
# Wrap the PyInstaller one-folder build into a proper macOS .app bundle.

VERSION=$(grep -oE 'APP_VERSION\s*=\s*"[^"]+"' version.py | head -1 | grep -oE '"[^"]+"' | tr -d '"')
: ${VERSION:="1.0.0"}
APP_PATH="dist/HABITUS.app"

if [ -d "$APP_PATH" ]; then
  echo "App bundle already created by PyInstaller: $APP_PATH"
  exit 0
fi

if [ ! -d "dist/HABITUS" ]; then
  echo "dist/HABITUS not found!" >&2
  exit 1
fi

mkdir -p "${APP_PATH}/Contents/MacOS"
mkdir -p "${APP_PATH}/Contents/Resources"
cp -R dist/HABITUS/. "${APP_PATH}/Contents/MacOS/"

if [ -f icon.icns ]; then
  cp icon.icns "${APP_PATH}/Contents/Resources/"
fi

PLIST="${APP_PATH}/Contents/Info.plist"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>                <string>HABITUS</string>
  <key>CFBundleDisplayName</key>         <string>HABITUS</string>
  <key>CFBundleIdentifier</key>          <string>com.habitus.sdm</string>
  <key>CFBundleVersion</key>             <string>${VERSION}</string>
  <key>CFBundleShortVersionString</key>  <string>${VERSION}</string>
  <key>CFBundleExecutable</key>          <string>HABITUS</string>
  <key>CFBundleIconFile</key>            <string>icon.icns</string>
  <key>NSHighResolutionCapable</key>     <true/>
  <key>LSMinimumSystemVersion</key>      <string>11.0</string>
</dict>
</plist>
PLISTEOF

chmod +x "${APP_PATH}/Contents/MacOS/HABITUS" || true
echo "Created ${APP_PATH}"
