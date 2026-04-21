# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for HABITUS standalone app.

Build command (from D:/claude_project/habitus):
    pyinstaller habitus.spec --clean

Output: dist/HABITUS/HABITUS.exe
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

# SPECPATH = D:/claude_project/habitus
# PROJ_ROOT = D:/claude_project  (so "import habitus" works)
PROJ_ROOT = str(Path(SPECPATH).parent)

# ── Collect packages with binary/data payloads ────────────────────────────────
rasterio_datas, rasterio_binaries, rasterio_hiddenimports = collect_all("rasterio")
mpl_datas    = collect_data_files("matplotlib")
elapid_datas, elapid_bins, elapid_hidden = collect_all("elapid")
xgb_datas,   xgb_bins,   xgb_hidden   = collect_all("xgboost")
lgb_datas,   lgb_bins,   lgb_hidden   = collect_all("lightgbm")
cat_datas,   cat_bins,   cat_hidden   = collect_all("catboost")
pygam_datas  = collect_data_files("pygam")
pyproj_datas = collect_data_files("pyproj")

# ── Data files ────────────────────────────────────────────────────────────────
datas = (
    rasterio_datas
    + mpl_datas
    + elapid_datas
    + xgb_datas
    + lgb_datas
    + cat_datas
    + pygam_datas
    + pyproj_datas
    + [
        # App assets
        (os.path.join(SPECPATH, "icon.png"),                "."),
        (os.path.join(SPECPATH, "icon.svg"),                "."),
        (os.path.join(SPECPATH, "habitus_suitability.qml"), "."),
    ]
)

binaries = rasterio_binaries + elapid_bins + xgb_bins + lgb_bins + cat_bins

# ── Hidden imports ────────────────────────────────────────────────────────────
hiddenimports = (
    rasterio_hiddenimports
    + elapid_hidden
    + xgb_hidden
    + lgb_hidden
    + cat_hidden
    + [
        # PyQt6
        "PyQt6.QtWidgets",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtNetwork",
        # matplotlib
        "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.backend_qt",
        # sklearn
        "sklearn.ensemble._forest",
        "sklearn.ensemble._gb",
        "sklearn.linear_model._logistic",
        "sklearn.svm._classes",
        "sklearn.neural_network._multilayer_perceptron",
        "sklearn.preprocessing._data",
        "sklearn.utils._cython_blas",
        "sklearn.neighbors.typedefs",
        "sklearn.neighbors._partition_nodes",
        "sklearn.tree._utils",
        "sklearn.inspection._permutation_importance",
        # scipy
        "scipy.special._ufuncs_cxx",
        "scipy.linalg.cython_blas",
        "scipy.linalg.cython_lapack",
        "scipy.sparse.csgraph._flow",
        "scipy.sparse.csgraph._matching",
        "scipy.sparse.csgraph._min_spanning_tree",
        "scipy.sparse.csgraph._tools",
        "scipy.sparse.csgraph._traversal",
        "scipy.sparse.linalg._dsolve.umfpack",
        # geo
        "pyproj",
        "pyproj.datadir",
        "geopandas",
        "shapely",
        "rtree",
        # boosting
        "xgboost",
        "lightgbm",
        "catboost",
        # GAM
        "pygam",
        "pygam.terms",
        "pygam.callbacks",
        "pygam.utils",
        # habitus modules
        "habitus",
        "habitus.version",
        "habitus.updater",
        "habitus.sdm_core",
        "habitus.map_widget",
        "habitus.main_dialog",
        "habitus.tabs.tab_data",
        "habitus.tabs.tab_vif",
        "habitus.tabs.tab_models",
        "habitus.tabs.tab_projection",
        "habitus.tabs.tab_range",
        "habitus.tabs.tab_evaluation",
        "habitus.tabs.tab_validation",
        "habitus.tabs.tab_report",
        "habitus.tabs.tab_help",
        # stdlib used at runtime
        "urllib.request",
        "urllib.error",
        "json",
        "csv",
        "warnings",
        "traceback",
        "datetime",
        "collections",
    ]
)

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [os.path.join(SPECPATH, "main.py")],
    pathex=[PROJ_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "qgis",
        "IPython", "jupyter", "notebook",
        "tkinter", "_tkinter",
        "torch", "tensorflow",
        "pytest", "sphinx",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HABITUS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(SPECPATH, "icon.png"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["HABITUS.exe", "*.dll", "*.pyd"],
    name="HABITUS",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="HABITUS.app",
        icon=os.path.join(SPECPATH, "icon.png"),
        bundle_identifier="com.habitus.sdm",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
        },
    )
