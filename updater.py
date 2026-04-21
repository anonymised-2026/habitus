# -*- coding: utf-8 -*-
"""
Background GitHub release checker and hot-patch downloader for HABITUS.

- UpdateChecker:  queries GitHub Releases API for new versions.
- PatchDownloader: downloads changed .py files into a local patches/ folder
  so the running (or next-launched) instance uses the updated code without
  reinstalling the exe.
"""

import json
import os
import sys
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal


def _ver_tuple(v: str):
    """Convert "1.2.3" or "v1.2.3" → (1, 2, 3) for comparison."""
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split(".") if x.isdigit())
    except Exception:
        return (0,)


def get_patches_dir():
    """Return the patches/ directory next to the running exe (or script)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "patches")


# ── Files that can be hot-patched ─────────────────────────────────────────────
# These are downloaded from GitHub main branch into patches/habitus/…
PATCHABLE_FILES = [
    "sdm_core.py",
    "map_widget.py",
    "main_dialog.py",
    "version.py",
    "updater.py",
    "tabs/tab_data.py",
    "tabs/tab_vif.py",
    "tabs/tab_models.py",
    "tabs/tab_projection.py",
    "tabs/tab_range.py",
    "tabs/tab_evaluation.py",
    "tabs/tab_validation.py",
    "tabs/tab_help.py",
    "tabs/tab_ensemble.py",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Update Checker (existing)
# ═══════════════════════════════════════════════════════════════════════════════

class UpdateChecker(QThread):
    """Queries the GitHub Releases API in a background thread."""

    update_available = pyqtSignal(str, str)   # (latest_version, release_url)
    check_failed     = pyqtSignal(str)
    up_to_date       = pyqtSignal(str)

    def __init__(self, current_version: str, repo: str, parent=None):
        super().__init__(parent)
        self._current = current_version
        self._repo    = repo

    def run(self):
        try:
            api_url = f"https://api.github.com/repos/{self._repo}/releases/latest"
            req = urllib.request.Request(
                api_url,
                headers={"User-Agent": f"HABITUS/{self._current}",
                         "Accept": "application/vnd.github+json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            tag         = data.get("tag_name", "").strip()
            release_url = data.get("html_url",
                          f"https://github.com/{self._repo}/releases")

            if not tag:
                self.check_failed.emit("No release tag found.")
                return

            if _ver_tuple(tag) > _ver_tuple(self._current):
                self.update_available.emit(tag.lstrip("v"), release_url)
            else:
                self.up_to_date.emit(self._current)

        except Exception as exc:
            self.check_failed.emit(str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# Patch Downloader
# ═══════════════════════════════════════════════════════════════════════════════

class PatchDownloader(QThread):
    """
    Downloads updated .py files from GitHub main branch into patches/habitus/.

    Signals
    -------
    progress(message: str, percent: int)
    finished(n_updated: int, n_failed: int)
    error(message: str)
    """

    progress = pyqtSignal(str, int)
    finished = pyqtSignal(int, int)
    error    = pyqtSignal(str)

    def __init__(self, repo: str, parent=None):
        super().__init__(parent)
        self._repo = repo

    def run(self):
        try:
            patches_dir = get_patches_dir()
            hab_dir     = os.path.join(patches_dir, "habitus")
            tabs_dir    = os.path.join(hab_dir, "tabs")
            os.makedirs(tabs_dir, exist_ok=True)

            # Write __init__.py files so Python treats them as packages
            for d in (hab_dir, tabs_dir):
                init = os.path.join(d, "__init__.py")
                if not os.path.exists(init):
                    with open(init, "w") as f:
                        f.write("")

            n_ok = 0
            n_fail = 0
            total = len(PATCHABLE_FILES)

            for i, rel_path in enumerate(PATCHABLE_FILES):
                pct = int(100 * (i + 1) / total)
                self.progress.emit(f"Downloading {rel_path}…", pct)

                raw_url = (f"https://raw.githubusercontent.com/"
                           f"{self._repo}/main/{rel_path}")
                dest = os.path.join(hab_dir, rel_path.replace("/", os.sep))

                try:
                    req = urllib.request.Request(
                        raw_url,
                        headers={"User-Agent": "HABITUS-patcher/1.0"}
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        content = resp.read()

                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, "wb") as f:
                        f.write(content)
                    n_ok += 1

                except Exception:
                    n_fail += 1

            self.finished.emit(n_ok, n_fail)

        except Exception as exc:
            self.error.emit(str(exc))
