#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# HABITUS macOS build script
# Usage: ./build_mac.sh   (from the habitus project root on macOS)
# Produces: dist/HABITUS.app and HABITUS_Setup_v<version>_macOS.dmg
# ──────────────────────────────────────────────────────────────────────────────
set -e

# 1. Dependencies
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Install from https://brew.sh/ first."; exit 1
fi
brew list create-dmg >/dev/null 2>&1 || brew install create-dmg

python3 -m pip install --upgrade pip
python3 -m pip install pyinstaller pillow
python3 -m pip install PyQt6 matplotlib rasterio numpy pandas scipy \
                      scikit-learn pyproj xgboost lightgbm pygam elapid \
                      geopandas shapely
python3 -m pip install catboost || echo "catboost skipped (no arm wheel)"

# 2. PyInstaller build
python3 -m PyInstaller habitus.spec --clean -y

# 3. Wrap into .app if needed
VERSION=$(python3 -c "from habitus.version import APP_VERSION; print(APP_VERSION)")
APP_PATH="dist/HABITUS.app"

if [ ! -d "$APP_PATH" ]; then
  mkdir -p "${APP_PATH}/Contents/MacOS"
  mkdir -p "${APP_PATH}/Contents/Resources"
  cp -R dist/HABITUS/* "${APP_PATH}/Contents/MacOS/"
  [ -f icon.icns ] && cp icon.icns "${APP_PATH}/Contents/Resources/"
  cat > "${APP_PATH}/Contents/Info.plist" <<EOF
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
EOF
fi

# 4. Create DMG
DMG="HABITUS_Setup_v${VERSION}_macOS.dmg"
rm -f "$DMG"
create-dmg \
  --volname "HABITUS ${VERSION}" \
  --window-size 560 360 \
  --icon-size 100 \
  --icon "HABITUS.app" 140 180 \
  --app-drop-link 420 180 \
  --hide-extension "HABITUS.app" \
  "$DMG" "$APP_PATH"

echo ""
echo "Build complete:"
echo "   App:  $APP_PATH"
echo "   DMG:  $DMG"
