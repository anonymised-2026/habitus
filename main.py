# -*- coding: utf-8 -*-
"""
HABITUS – standalone entry point.
Run:  python main.py
Or as a bundled executable built with PyInstaller.
"""

import sys
import os

# When bundled by PyInstaller the package root is in sys._MEIPASS;
# add it to sys.path so relative imports resolve correctly.
if getattr(sys, "frozen", False):
    _bundle_dir = sys._MEIPASS
    if _bundle_dir not in sys.path:
        sys.path.insert(0, _bundle_dir)
else:
    # Running from source — add parent directory so "import habitus" works
    _src_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _src_parent not in sys.path:
        sys.path.insert(0, _src_parent)

# ── Hot-patch system ──────────────────────────────────────────────────────────
# If a "patches/" folder exists next to the exe, prepend it to sys.path so that
# updated .py files override the frozen bytecode. This allows shipping fixes
# without rebuilding the entire installer.
_exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
           else os.path.dirname(os.path.abspath(__file__))
_patches_dir = os.path.join(_exe_dir, "patches")
if os.path.isdir(_patches_dir) and _patches_dir not in sys.path:
    sys.path.insert(0, _patches_dir)

# ── PROJ database path fix ─────────────────────────────────────────────────────
# PROJ_DATA / PROJ_LIB must be set BEFORE any import of rasterio/pyproj/gdal,
# otherwise GDAL logs "Cannot find proj.db".
# We always validate the current values; a stale PROJ_LIB (e.g. from a
# PostgreSQL/PostGIS installation) must be overridden with pyproj's own path.
def _proj_valid(p):
    from pathlib import Path as _P
    return bool(p) and (_P(p) / "proj.db").is_file()

if not _proj_valid(os.environ.get("PROJ_DATA")) and not _proj_valid(os.environ.get("PROJ_LIB")):
    try:
        import importlib.util as _ilu
        from pathlib import Path as _Path

        _proj_db = None  # directory that contains proj.db

        # Strategy 0 (frozen/bundled): proj.db is inside sys._MEIPASS
        if getattr(sys, "frozen", False):
            _mei = _Path(sys._MEIPASS)
            for _db in _mei.rglob("proj.db"):
                _proj_db = _db.parent
                break

        # Strategy 1: rasterio's own bundled proj.db MUST take priority —
        # rasterio links against its own PROJ version whose .db schema may
        # be newer than pyproj's bundled copy (version mismatch → error).
        if _proj_db is None:
            for _pkg_name in ("rasterio", "pyproj"):
                if _proj_db:
                    break
                _spec = _ilu.find_spec(_pkg_name)
                if _spec and _spec.origin:
                    _pkg_dir = _Path(_spec.origin).parent
                    for _db in _pkg_dir.rglob("proj.db"):
                        _proj_db = _db.parent
                        break

        # Strategy 2: conda / OSGeo4W / system PROJ layout
        if _proj_db is None:
            for _base in (sys.prefix, sys.exec_prefix):
                for _sub in ("share/proj", "Library/share/proj", "lib/proj"):
                    _c = _Path(_base) / _sub
                    if (_c / "proj.db").is_file():
                        _proj_db = _c
                        break
                if _proj_db:
                    break

        # Strategy 3: ask pyproj directly
        if _proj_db is None:
            try:
                import pyproj.datadir as _ppd
                _d = _Path(_ppd.get_data_dir())
                if (_d / "proj.db").is_file():
                    _proj_db = _d
            except Exception:
                pass

        if _proj_db:
            os.environ["PROJ_DATA"] = str(_proj_db)
            os.environ["PROJ_LIB"]  = str(_proj_db)
    except Exception:
        pass

# Set matplotlib backend before any GUI import
import matplotlib
matplotlib.use("QtAgg")
# Ensure every figure saved (toolbar save, programmatic savefig) defaults to
# 300 DPI - consistent with Q1 journal requirements for publication figures.
matplotlib.rcParams["savefig.dpi"] = 300
matplotlib.rcParams["figure.dpi"]  = 100  # on-screen only; independent of save
# Standardise all matplotlib text to Arial for consistent publication figures.
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans"]

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

from habitus.main_dialog import SDMMainDialog


def main():
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("HABITUS")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("HABITUS Project")

    # App icon (if available next to main.py or in the package)
    _here = os.path.dirname(os.path.abspath(__file__))
    for _icon_name in ("icon.png", "icon.svg"):
        _icon_path = os.path.join(_here, _icon_name)
        if os.path.isfile(_icon_path):
            app.setWindowIcon(QIcon(_icon_path))
            break

    dialog = SDMMainDialog()
    dialog.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
