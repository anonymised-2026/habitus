#!/bin/bash
set -e
# Package the PyInstaller output as a portable tar.gz and build an AppImage.

VERSION=$(grep -oE 'APP_VERSION\s*=\s*"[^"]+"' version.py | head -1 | grep -oE '"[^"]+"' | tr -d '"')
: ${VERSION:="1.0.0"}

if [ ! -d "dist/HABITUS" ]; then
  echo "dist/HABITUS not found" >&2
  exit 1
fi

# ─── 1. tar.gz archive ────────────────────────────────────────────────────────
TAR_NAME="HABITUS_Setup_v${VERSION}_Linux_x64.tar.gz"
tar -czf "$TAR_NAME" -C dist HABITUS
ls -la "$TAR_NAME"

# ─── 2. Portable launcher script ──────────────────────────────────────────────
cat > dist/HABITUS/run_habitus.sh <<'LAUNCHER'
#!/bin/bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/HABITUS" "$@"
LAUNCHER
chmod +x dist/HABITUS/run_habitus.sh

# ─── 3. AppImage (optional, best-effort) ──────────────────────────────────────
APPDIR="HABITUS.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp -R dist/HABITUS/. "$APPDIR/usr/bin/"

# .desktop file
cat > "$APPDIR/HABITUS.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=HABITUS
Comment=Habitat Analysis and Biodiversity Integrated Toolkit for SDM
Exec=HABITUS
Icon=habitus
Categories=Science;Geography;Biology;
Terminal=false
DESKTOP

# Icon (PNG required at root)
if [ -f icon.png ]; then
  cp icon.png "$APPDIR/habitus.png"
fi

# AppRun entry point
cat > "$APPDIR/AppRun" <<APPRUN
#!/bin/bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/usr/bin/HABITUS" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# Download appimagetool if not already present
if ! command -v appimagetool >/dev/null 2>&1; then
  wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage \
       -O appimagetool
  chmod +x appimagetool
  APPIMAGETOOL="./appimagetool"
else
  APPIMAGETOOL="appimagetool"
fi

APPIMAGE_NAME="HABITUS_v${VERSION}_x86_64.AppImage"
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$APPIMAGE_NAME" \
  && echo "AppImage built: $APPIMAGE_NAME" \
  || echo "AppImage build failed (non-fatal)"

ls -la *.tar.gz *.AppImage 2>/dev/null || true
