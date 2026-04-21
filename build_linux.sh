#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# HABITUS Linux build script
# Usage: ./build_linux.sh   (Ubuntu 20.04+ / Debian 11+ / Fedora 36+)
# Produces: HABITUS_Setup_v<version>_Linux_x64.tar.gz and optional .AppImage
# ──────────────────────────────────────────────────────────────────────────────
set -e

# System packages (Debian/Ubuntu)
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y \
    libgl1 libegl1 libxkbcommon0 libdbus-1-3 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
    libxcb-xinerama0 libxcb-xkb1 libxcb-cursor0 \
    libfontconfig1 libpulse0 gdal-bin libgdal-dev fuse libfuse2
fi

# Python dependencies
python3 -m pip install --upgrade pip
python3 -m pip install pyinstaller pillow
python3 -m pip install PyQt6 matplotlib rasterio numpy pandas scipy \
                      scikit-learn pyproj xgboost lightgbm pygam elapid \
                      geopandas shapely
python3 -m pip install catboost || echo "catboost skipped"

# PyInstaller build
python3 -m PyInstaller habitus.spec --clean -y

# Package
bash scripts/make_linux_archive.sh

echo ""
echo "Linux build complete. Outputs:"
ls -la HABITUS_*.tar.gz 2>/dev/null || true
ls -la HABITUS_*.AppImage 2>/dev/null || true
