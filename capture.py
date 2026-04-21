# -*- coding: utf-8 -*-
"""
HABITUS Screenshot Capture — Win32 PrintWindow API version.
Works with DPI scaling and GPU-rendered windows.

Usage:
  1. Run HABITUS:  python main.py
  2. In ANOTHER terminal:  python capture.py
  3. Type a name + ENTER to capture, 'q' to quit.
"""

import os
import sys
import ctypes
from ctypes import wintypes

# Set DPI awareness BEFORE any window operations
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import win32gui
import win32ui
import win32con
from PIL import Image

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# ── Q1 journal-quality settings ──────────────────────────────────────────────
#   Target: screenshots suitable for Q1 journals (full-page ~6.5 inch width,
#   double-column ~6.9 inch, high legibility when printed).
#   Strategy:
#     1. Capture the raw pixels of the HABITUS window.
#     2. Upsample 2× with Lanczos for a smooth, high-pixel image.
#     3. Save with 600 DPI metadata so typesetters get full print quality.
#
# With HABITUS maximised on a 1920×1080 monitor this produces a
# 3840×2160 PNG at 600 DPI → 6.4 inch print width (tight two-column) at 600 DPI
# and 12.8 inch at 300 DPI, covering any journal format.
SCALE_FACTOR = 2.0
DPI = 600


def find_habitus_window():
    """Find HABITUS window handle."""
    result = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "HABITUS" in title:
                result.append(hwnd)
        return True
    win32gui.EnumWindows(callback, None)
    return result[0] if result else None


def capture_window(hwnd, filepath):
    """Capture window using PrintWindow API (works with DPI scaling)."""
    # Get CLIENT area (excludes window shadow/border that causes overflow)
    # Use DwmGetWindowAttribute to get the actual visible rect without shadow
    try:
        import ctypes.wintypes
        rect = ctypes.wintypes.RECT()
        DWMWA_EXTENDED_FRAME_BOUNDS = 9
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(rect), ctypes.sizeof(rect))
        left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)

    # Get the full window rect (with shadow) to calculate shadow offset
    full_left, full_top, full_right, full_bottom = win32gui.GetWindowRect(hwnd)
    shadow_left = left - full_left  # pixels of shadow on left side

    w = right - left
    h = bottom - top

    # Create device contexts
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()

    # Create bitmap for FULL window (including shadow)
    full_w = full_right - full_left
    full_h = full_bottom - full_top
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc_dc, full_w, full_h)
    save_dc.SelectObject(bmp)

    # Use PrintWindow (PW_RENDERFULLCONTENT = 2 for Win8+)
    ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)

    # Convert to PIL Image (full window with shadow)
    bmp_info = bmp.GetInfo()
    bmp_bits = bmp.GetBitmapBits(True)
    img_full = Image.frombuffer("RGB", (bmp_info["bmWidth"], bmp_info["bmHeight"]),
                                bmp_bits, "raw", "BGRX", 0, 1)

    # Crop out the shadow — keep only the visible window area
    crop_left = left - full_left
    crop_top = top - full_top
    crop_right = crop_left + w
    crop_bottom = crop_top + h
    img = img_full.crop((crop_left, crop_top, crop_right, crop_bottom))

    # Upsample with high-quality Lanczos for Q1 journal print quality
    if SCALE_FACTOR != 1.0:
        new_w = int(img.width * SCALE_FACTOR)
        new_h = int(img.height * SCALE_FACTOR)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # Save at high DPI (600 by default) — print-ready metadata
    img.save(filepath, "PNG", dpi=(DPI, DPI), optimize=True)

    # Cleanup
    win32gui.DeleteObject(bmp.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    return img.size


def main():
    print("=" * 60)
    print("  HABITUS Screenshot Capture - Q1 Journal Quality")
    print("=" * 60)
    print()
    print(f"  Upsample: {SCALE_FACTOR}x with Lanczos")
    print(f"  DPI metadata: {DPI}")
    print("  Tip: Maximize the HABITUS window for best results.")
    print()
    print("  Type a name + ENTER to capture, 'q' to quit.")
    print(f"  Saving to: {SCREENSHOT_DIR}")
    print()

    counter = 1

    while True:
        user_input = input(f"  [{counter:03d}] Name (or ENTER/q): ").strip()

        if user_input.lower() == 'q':
            print(f"\n  Done! {counter - 1} screenshots saved.")
            break

        hwnd = find_habitus_window()
        if not hwnd:
            print("  ERROR: HABITUS window not found!")
            continue

        # Bring to front
        try:
            win32gui.SetForegroundWindow(hwnd)
        except:
            pass

        import time; time.sleep(0.3)

        if user_input:
            safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in user_input)
            fname = f"Fig_{counter:02d}_{safe}.png"
        else:
            fname = f"Fig_{counter:02d}.png"

        fpath = os.path.join(SCREENSHOT_DIR, fname)
        w, h = capture_window(hwnd, fpath)
        print(f"  -> {fname} ({w}x{h} @ {DPI} DPI)")
        counter += 1


if __name__ == "__main__":
    main()
