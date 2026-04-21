# -*- coding: utf-8 -*-
"""
Embedded raster map viewer — standalone replacement for QGIS canvas.
Uses rasterio + matplotlib (QtAgg backend) embedded in a PyQt6 widget.
"""

import os
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt

try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigCanvas
    from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavBar
    from matplotlib.figure import Figure
    from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm, ListedColormap
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ── Literature-accepted suitability colourmaps ────────────────────────────────
#
# Each entry: (display_label, cmap_or_factory, vmin, vmax, interpolation)
# "factory" means a callable → returns a matplotlib colormap object.
# "name"    means a string   → passed directly to matplotlib / imshow.

def _habitus_cmap():
    """Default HABITUS ramp: neutral grey → teal → green."""
    colors = [
        "#eaedf0", "#c9d5de", "#a0bece", "#72a5b8",
        "#4490a0", "#237a82", "#136860", "#006837", "#1a9641",
    ]
    return LinearSegmentedColormap.from_list("habitus_suit", colors, N=256)

def _rdylgn_r():
    """Red–Yellow–Green reversed so red=low, green=high (intuitive traffic-light)."""
    try:
        import matplotlib.cm as cm
        return cm.get_cmap("RdYlGn")
    except Exception:
        return "RdYlGn"

def _spectral_r():
    """Spectral reversed: violet=unsuitable, red=highly suitable (SDM classic)."""
    try:
        import matplotlib.cm as cm
        return cm.get_cmap("Spectral_r")
    except Exception:
        return "Spectral_r"

def _ylgnbu():
    try:
        import matplotlib.cm as cm
        return cm.get_cmap("YlGnBu")
    except Exception:
        return "YlGnBu"

def _viridis():
    try:
        import matplotlib.cm as cm
        return cm.get_cmap("viridis")
    except Exception:
        return "viridis"

def _magma():
    try:
        import matplotlib.cm as cm
        return cm.get_cmap("magma")
    except Exception:
        return "magma"

def _hot():
    try:
        import matplotlib.cm as cm
        return cm.get_cmap("hot")
    except Exception:
        return "hot"

def _greens():
    try:
        import matplotlib.cm as cm
        return cm.get_cmap("Greens")
    except Exception:
        return "Greens"


# Ordered list of (label, cmap_factory)
# Each factory is a zero-argument callable returning a cmap.
SUIT_STYLES = [
    ("HABITUS Default (Grey→Green)",     _habitus_cmap),
    ("Viridis  [colorblind-safe]",        _viridis),
    ("YlGnBu  [ecology standard]",        _ylgnbu),
    ("RdYlGn  [traffic-light]",           _rdylgn_r),
    ("Spectral_r  [SDM classic]",         _spectral_r),
    ("Magma  [dark-field]",               _magma),
    ("Hot  [heat-map]",                   _hot),
    ("Greens  [simple]",                  _greens),
]

SUIT_STYLE_LABELS = [s[0] for s in SUIT_STYLES]
_SUIT_FACTORY     = {s[0]: s[1] for s in SUIT_STYLES}


# ── Fixed colourmaps for binary / range-change ────────────────────────────────

def _binary_cmap():
    """Binary map: light grey (absent) → green (present)."""
    return LinearSegmentedColormap.from_list(
        "habitus_bin", [(0, "#c8c8c8"), (1, "#1a9641")], N=2
    )

def _range_cmap():
    """Range change: Lost=red, StableAbsent=light-grey, StablePresent=teal, Gained=green."""
    cmap = ListedColormap(["#f03b20", "#f0f0f0", "#99d8c9", "#2ca25f"])
    norm = BoundaryNorm([-2.5, -1.0, 0.5, 1.5, 2.5], cmap.N)
    return cmap, norm


# ── Widget ─────────────────────────────────────────────────────────────────────

class RasterMapWidget(QWidget):
    """
    Embedded raster map viewer.  Replaces the QGIS canvas for standalone use.

    Usage:
        widget.load_raster(fpath, name, style)
            style: "suitability" | "binary" | "range_change"

        widget.add_scatter(lons, lats, color, size, label)
            Overlay occurrence / point data on the current map.

        widget.clear_scatter()   – remove all scatter overlays
        widget.clear_all()       – remove all layers + overlays
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layers       = {}   # name → {"fpath": str, "style": str}
        self._current      = None
        self._scatter_sets = []   # each entry: (lons, lats, color, size, label, ptype)
        self._bg_visible   = True  # toggle for "bg" type scatter points
        self._obs_visible  = True  # toggle for "obs" type scatter points (train/test)
        self._suit_style   = SUIT_STYLE_LABELS[0]   # currently selected suitability cmap
        self._app_state    = None  # will be set by the owning tab via set_app_state()
        self._setup_ui()

    def set_app_state(self, state_dict):
        """Inject the main dialog's state dict so the save dialog can read
        species_name and output_dir without parent traversal."""
        self._app_state = state_dict

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        if not HAS_MPL:
            lbl = QLabel(
                "matplotlib is not installed — maps cannot be displayed.\n"
                "Run:  pip install matplotlib"
            )
            lbl.setStyleSheet("color:#fc8181; padding:12px;")
            layout.addWidget(lbl)
            return

        # ── Top control bar ──
        bar = QHBoxLayout()
        bar.setContentsMargins(4, 2, 4, 2)
        bar.setSpacing(8)

        bar.addWidget(QLabel("Layer:"))
        self.layer_combo = QComboBox()
        self.layer_combo.setMinimumWidth(220)
        self.layer_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.layer_combo.currentIndexChanged.connect(self._on_layer_changed)
        bar.addWidget(self.layer_combo)

        # Style selector — visible only for suitability maps
        self._style_lbl = QLabel("Colormap:")
        self.style_combo = QComboBox()
        self.style_combo.setMinimumWidth(230)
        self.style_combo.addItems(SUIT_STYLE_LABELS)
        self.style_combo.setCurrentText(self._suit_style)
        self.style_combo.setToolTip(
            "Choose a literature-accepted colour scheme for the suitability map.\n"
            "Has no effect on binary or range-change maps (those use fixed colours)."
        )
        self.style_combo.currentTextChanged.connect(self._on_style_changed)
        bar.addWidget(self._style_lbl)
        bar.addWidget(self.style_combo)

        self._btn_bg = QPushButton("Hide BG")
        self._btn_bg.setObjectName("btn_secondary")
        self._btn_bg.setMinimumWidth(75)
        self._btn_bg.setToolTip(
            "Toggle visibility of background / pseudo-absence points."
        )
        self._btn_bg.clicked.connect(self._toggle_bg_points)
        bar.addWidget(self._btn_bg)

        self._btn_obs = QPushButton("Hide T/T")
        self._btn_obs.setObjectName("btn_secondary")
        self._btn_obs.setMinimumWidth(75)
        self._btn_obs.setToolTip(
            "Toggle visibility of train / test occurrence points."
        )
        self._btn_obs.clicked.connect(self._toggle_obs_points)
        bar.addWidget(self._btn_obs)
        bar.addStretch()
        layout.addLayout(bar)

        # ── Matplotlib canvas ──
        self.fig = Figure(facecolor="#f0f5f1")
        self.canvas = FigCanvas(self.fig)
        self.canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.navbar = NavBar(self.canvas, self)
        # Replace the toolbar Save action with our smart-filename version
        for act in self.navbar.actions():
            if act.text() == "Save":
                act.triggered.disconnect()
                act.triggered.connect(self._save_map_figure)
                break
        layout.addWidget(self.navbar)
        layout.addWidget(self.canvas, 1)

        self._draw_placeholder()
        self._update_style_visibility()
        self._refresh_obs_button()

    def _draw_placeholder(self):
        if not HAS_MPL:
            return
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_facecolor("#f5faf7")
        self.fig.patch.set_facecolor("#f0f5f1")
        ax.text(
            0.5, 0.5,
            "Run the models to generate distribution maps.\n"
            "They will appear here automatically.",
            ha="center", va="center",
            color="#3a7050", fontsize=11, fontweight="bold",
            transform=ax.transAxes,
        )
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        self.canvas.draw()

    def _update_style_visibility(self):
        """Show the colormap selector only when displaying a suitability map."""
        is_suit = False
        if self._current and self._current in self._layers:
            is_suit = self._layers[self._current]["style"] == "suitability"
        self._style_lbl.setVisible(is_suit)
        self.style_combo.setVisible(is_suit)

    # ── Public API ─────────────────────────────────────────────────────────────

    def load_raster(self, fpath: str, name: str, style: str = "suitability",
                    display_name: str = None):
        """Load a GeoTIFF and display it immediately.

        display_name: short label shown in the combo; name is used as the map
        title and dict key. If omitted, name is used for both.
        """
        if not HAS_MPL:
            return
        if not os.path.isfile(fpath):
            return
        self._layers[name] = {"fpath": fpath, "style": style}
        label = display_name or name
        # Find existing item by userData (full name)
        existing = next(
            (i for i in range(self.layer_combo.count())
             if self.layer_combo.itemData(i) == name), -1)
        if existing < 0:
            self.layer_combo.addItem(label, userData=name)
            existing = self.layer_combo.count() - 1
        self.layer_combo.setCurrentIndex(existing)

    def add_scatter(self, lons, lats,
                    color: str = "#27ae60", size: float = 12, label: str = "",
                    ptype: str = "obs"):
        """Overlay point data on the current map.

        ptype:
          "obs" (default) — presence points (train / test); always visible.
          "bg"            — background / pseudo-absence points; toggleable via button.
        """
        if not HAS_MPL or not lons:
            return
        self._scatter_sets.append((list(lons), list(lats), color, size, label, ptype))
        self._refresh_bg_button()
        self._refresh_obs_button()
        if self._current:
            self._draw(self._current)

    def _toggle_bg_points(self):
        self._bg_visible = not self._bg_visible
        self._refresh_bg_button()
        if self._current:
            self._draw(self._current)

    def _refresh_bg_button(self):
        has_bg = any(p == "bg" for *_, p in self._scatter_sets)
        self._btn_bg.setEnabled(has_bg)
        self._btn_bg.setText("Hide BG" if self._bg_visible else "Show BG")

    def _toggle_obs_points(self):
        self._obs_visible = not self._obs_visible
        self._refresh_obs_button()
        if self._current:
            self._draw(self._current)

    def _refresh_obs_button(self):
        has_obs = any(p == "obs" for *_, p in self._scatter_sets)
        self._btn_obs.setEnabled(has_obs)
        self._btn_obs.setText("Hide T/T" if self._obs_visible else "Show T/T")

    def clear_scatter(self):
        """Remove ALL scatter overlays (called on full reset only)."""
        self._scatter_sets.clear()
        self._bg_visible  = True
        self._obs_visible = True
        self._refresh_bg_button()
        self._refresh_obs_button()
        if self._current:
            self._draw(self._current)
        elif HAS_MPL:
            self._draw_placeholder()

    def clear_all(self):
        self._layers.clear()
        self._scatter_sets.clear()
        self._bg_visible  = True
        self._obs_visible = True
        self._current = None
        if HAS_MPL:
            self.layer_combo.blockSignals(True)
            self.layer_combo.clear()
            self.layer_combo.blockSignals(False)
            self._draw_placeholder()
        self._refresh_bg_button()
        self._refresh_obs_button()
        self._update_style_visibility()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _save_map_figure(self, *args):
        """Custom save replacing the default matplotlib toolbar save.
        Proposes {species}_{layer}.png as the default filename."""
        import re, os
        from PyQt6.QtWidgets import QFileDialog

        layer = self._current or "map"
        safe_layer = re.sub(r"[^\w.-]", "_", str(layer)).strip("_")

        # Read species name + output dir from the injected state dict
        species, out_dir = "", ""
        if self._app_state:
            species = self._app_state.get("species_name", "")
            out_dir = self._app_state.get("output_dir", "")

        if species:
            safe_sp = re.sub(r"[^\w.-]", "_", str(species)).strip("_")
            default_name = f"{safe_sp}_{safe_layer}.png"
        else:
            default_name = f"{safe_layer}.png"

        start_dir = out_dir or ""
        default_path = os.path.join(start_dir, default_name) if start_dir else default_name

        fpath, _ = QFileDialog.getSaveFileName(
            self, "Save Map Figure", default_path,
            "PNG (*.png);;JPEG (*.jpg);;TIFF (*.tif);;PDF (*.pdf);;SVG (*.svg)")
        if fpath:
            self.fig.savefig(fpath, dpi=300, bbox_inches="tight",
                             facecolor=self.fig.get_facecolor())

    def _on_layer_changed(self, index: int):
        name = self.layer_combo.itemData(index) if index >= 0 else None
        if not name:
            name = self.layer_combo.currentText()
        if name and name in self._layers:
            self._current = name
            self._update_style_visibility()
            self._draw(name)

    def _on_style_changed(self, label: str):
        self._suit_style = label
        if self._current and self._current in self._layers:
            if self._layers[self._current]["style"] == "suitability":
                self._draw(self._current)

    def _get_suit_cmap(self):
        factory = _SUIT_FACTORY.get(self._suit_style, _habitus_cmap)
        return factory()

    def _draw(self, name: str):
        if not HAS_MPL or name not in self._layers:
            return
        entry  = self._layers[name]
        fpath  = entry["fpath"]
        style  = entry["style"]

        # ── Read raster ──
        try:
            import rasterio
            with rasterio.open(fpath) as src:
                data   = src.read(1, masked=True)
                bounds = src.bounds
        except Exception as exc:
            self.fig.clear()
            ax = self.fig.add_subplot(111)
            ax.set_facecolor("#f5faf7")
            self.fig.patch.set_facecolor("#f0f5f1")
            ax.text(0.5, 0.5, f"Cannot read raster:\n{exc}",
                    ha="center", va="center",
                    color="#c0392b", fontweight="bold", transform=ax.transAxes)
            self.canvas.draw()
            return

        extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

        # ── Draw ──
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_facecolor("#f5faf7")
        self.fig.patch.set_facecolor("#f0f5f1")
        ax.tick_params(colors="#1d5235", labelsize=9, width=1.2)
        for tick in ax.get_xticklabels() + ax.get_yticklabels():
            tick.set_fontweight("bold")
        for sp in ax.spines.values():
            sp.set_color("#3a8c60")
            sp.set_linewidth(1.2)
        ax.grid(True, alpha=0.3, color="#8ab4a0", linestyle="--", linewidth=0.6)

        # ── Geographic aspect ratio (cosine latitude correction) ────────────
        import math as _math
        _lon_span  = bounds.right - bounds.left
        _lat_span  = bounds.top   - bounds.bottom
        _lat_mid   = (bounds.top + bounds.bottom) / 2.0
        _lon_scale = _math.cos(_math.radians(_lat_mid))
        # imshow aspect: y-units per x-unit so geographic degrees look correct
        # aspect = (data_height/data_width) * (axes_width/axes_height) is handled
        # by matplotlib when we supply the geographic ratio as the "aspect" value.
        # For plate carrée with lat-correction: 1 lat-deg ≈ 1/cos(lat) lon-deg visually.
        _geo_aspect = _lon_scale  # pass as matplotlib aspect → equal geographic scaling
        # ────────────────────────────────────────────────────────────────────

        if style == "suitability":
            cmap = self._get_suit_cmap()
            im = ax.imshow(
                data, extent=extent, origin="upper",
                cmap=cmap, vmin=0.0, vmax=1.0,
                aspect=1 / max(_geo_aspect, 0.01), interpolation="bilinear",
            )
            cbar = self.fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
            cbar.set_label("Suitability (0–1)", color="#1d5235",
                           fontsize=9, fontweight="bold")
            cbar.ax.yaxis.set_tick_params(color="#1d5235", labelsize=8)
            for lbl in cbar.ax.get_yticklabels():
                lbl.set_color("#1d5235")
                lbl.set_fontweight("bold")
            cbar.outline.set_edgecolor("#3a8c60")

        elif style == "binary":
            cmap = _binary_cmap()
            im = ax.imshow(
                data, extent=extent, origin="upper",
                cmap=cmap, vmin=0.0, vmax=1.0,
                aspect=1 / max(_geo_aspect, 0.01), interpolation="nearest",
            )
            patches = [
                mpatches.Patch(color="#c8c8c8", label="Absent"),
                mpatches.Patch(color="#1a9641", label="Present"),
            ]
            ax.legend(handles=patches, loc="lower right",
                      facecolor="#f5faf7", labelcolor="#1c3328",
                      fontsize=9, edgecolor="#8ab4a0")

        elif style == "range_change":
            rcmap, rnorm = _range_cmap()
            im = ax.imshow(
                data, extent=extent, origin="upper",
                cmap=rcmap, norm=rnorm,
                aspect=1 / max(_geo_aspect, 0.01), interpolation="nearest",
            )
            patches = [
                mpatches.Patch(color="#f03b20", label="Lost (−2)"),
                mpatches.Patch(color="#f0f0f0", label="Stable Absent (0)"),
                mpatches.Patch(color="#99d8c9", label="Stable Present (1)"),
                mpatches.Patch(color="#2ca25f", label="Gained (2)"),
            ]
            ax.legend(handles=patches, loc="lower right",
                      facecolor="#f5faf7", labelcolor="#1c3328",
                      fontsize=9, edgecolor="#8ab4a0")

        else:   # generic fallback
            im = ax.imshow(
                data, extent=extent, origin="upper",
                cmap="viridis", aspect=1 / max(_geo_aspect, 0.01),
                interpolation="bilinear",
            )
            cbar = self.fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
            cbar.ax.yaxis.set_tick_params(color="#1d5235", labelsize=8)
            for lbl in cbar.ax.get_yticklabels():
                lbl.set_color("#1d5235")
                lbl.set_fontweight("bold")

        # Title: italic species name (prominent) + layer name as subtitle
        species = self._app_state.get("species_name", "") if self._app_state else ""
        if species:
            ax.set_title(species, color="#1d5235", fontsize=12, pad=24,
                         fontweight="bold", fontstyle="italic")
            ax.annotate(name,
                        xy=(0.5, 1.0), xycoords="axes fraction",
                        xytext=(0, 2), textcoords="offset points",
                        ha="center", va="bottom",
                        fontsize=9, color="#4a7c62")
        else:
            ax.set_title(name, color="#1d5235", fontsize=11, pad=6, fontweight="bold")
        ax.set_xlabel("Longitude", color="#1d5235", fontsize=10, fontweight="bold")
        ax.set_ylabel("Latitude",  color="#1d5235", fontsize=10, fontweight="bold")

        # ── Scatter overlays ──
        _visible_sets = [
            (lons, lats, color, size, label)
            for lons, lats, color, size, label, ptype in self._scatter_sets
            if (ptype != "bg" or self._bg_visible)
            and (ptype != "obs" or self._obs_visible)
        ]
        for lons, lats, color, size, label in _visible_sets:
            ax.scatter(lons, lats, c=color, s=size, alpha=0.85,
                       linewidths=0, label=label or None, zorder=10)
        if any(lbl for _, _, _, _, lbl in _visible_sets):
            ax.legend(loc="upper right",
                      facecolor="#f5faf7", labelcolor="#1c3328",
                      fontsize=8, edgecolor="#8ab4a0")

        # ── Scale bar (lower-right) ──
        self._draw_scale_bar(ax, extent)

        # Fit the layout to the canvas so title/labels don't get clipped
        try:
            self.fig.tight_layout()
        except Exception:
            pass

        self.canvas.draw()

    def _draw_scale_bar(self, ax, extent):
        """Draw a linear scale bar at the lower-right corner of the map."""
        import math
        lon_min, lon_max, lat_min, lat_max = extent
        mid_lat = (lat_min + lat_max) / 2.0
        km_per_deg = 111.32 * math.cos(math.radians(mid_lat))
        if km_per_deg <= 0:
            return
        map_width_km = (lon_max - lon_min) * km_per_deg

        # Pick a nice round distance (~20% of map width)
        nice_km = [1, 2, 5, 10, 20, 25, 50, 100, 150, 200, 250, 500, 1000, 2000, 5000]
        bar_km  = min(nice_km, key=lambda x: abs(x - map_width_km * 0.2))
        bar_deg = bar_km / km_per_deg

        map_w = lon_max - lon_min
        map_h = lat_max - lat_min
        pad_x = map_w * 0.03
        pad_y = map_h * 0.04
        x_end   = lon_max - pad_x
        x_start = x_end - bar_deg
        y_bar   = lat_min + pad_y
        tick_h  = map_h * 0.012

        ax.plot([x_start, x_end], [y_bar, y_bar],
                color="#1d5235", linewidth=3, solid_capstyle="butt", zorder=20,
                transform=ax.transData)
        for x in (x_start, x_end):
            ax.plot([x, x], [y_bar - tick_h, y_bar + tick_h],
                    color="#1d5235", linewidth=2, zorder=20)
        label = f"{bar_km} km" if bar_km >= 1 else f"{int(bar_km * 1000)} m"
        ax.text((x_start + x_end) / 2, y_bar + tick_h * 1.4,
                label, ha="center", va="bottom", fontsize=8,
                color="#1d5235", fontweight="bold", zorder=21,
                bbox=dict(facecolor="white", alpha=0.6, edgecolor="none", pad=1))
