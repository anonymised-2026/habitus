# -*- coding: utf-8 -*-
"""
Tab ⑦ – Validation
Classification Accuracy and Regression Assessment

Compare two raster maps (model outputs or external) by reclassifying
continuous 0–1 probability surfaces into N equal-interval classes,
then computing standard accuracy metrics.
Also supports CSV field-data validation.
"""

import os
import json
import csv
import numpy as np
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QTextEdit, QGroupBox, QFileDialog,
    QMessageBox, QProgressBar, QRadioButton, QButtonGroup,
    QLineEdit, QDialog, QApplication, QDoubleSpinBox, QFormLayout,
    QInputDialog,
)
from PyQt6.QtCore import Qt

from sklearn.metrics import (
    cohen_kappa_score, accuracy_score, confusion_matrix,
    classification_report, f1_score, precision_score, recall_score,
    mean_squared_error, mean_absolute_error, r2_score,
)


# ---------------------------------------------------------------------------
# Validation Tab
# ---------------------------------------------------------------------------

class ValidationTab(QWidget):

    def __init__(self, main_dialog):
        super().__init__()
        self.dlg = main_dialog
        self._results = None
        self._points = None
        # {name: fpath} for layer combos – populated when tab unlocks
        self._ref_layers = {}
        self._val_layers = {}
        self._build_ui()

    # ══════════════════════════════════════════════════════════════════════
    # UI
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(10)

        # ── 1. Map selection ─────────────────────────────────────────────
        g1 = QGroupBox("1  Map Selection")
        lo1 = QVBoxLayout(g1)

        # Reference
        ref_row = QHBoxLayout()
        ref_row.addWidget(QLabel("Reference Map :"))
        self.ref_combo = QComboBox(); self.ref_combo.setMinimumWidth(320)
        ref_row.addWidget(self.ref_combo, 1)
        btn_ref = QPushButton("Browse…")
        btn_ref.clicked.connect(lambda: self._browse_add(self.ref_combo, self._ref_layers))
        ref_row.addWidget(btn_ref)
        lo1.addLayout(ref_row)

        # Validation
        val_row = QHBoxLayout()
        val_row.addWidget(QLabel("Validation Map :"))
        self.val_combo = QComboBox(); self.val_combo.setMinimumWidth(320)
        val_row.addWidget(self.val_combo, 1)
        btn_val = QPushButton("Browse…")
        btn_val.clicked.connect(lambda: self._browse_add(self.val_combo, self._val_layers))
        val_row.addWidget(btn_val)
        lo1.addLayout(val_row)

        # Quick-fill
        btn_fill = QPushButton("Load HABITUS Output Layers…")
        btn_fill.setToolTip("Populate both combos from the output directory")
        btn_fill.clicked.connect(self._fill_from_output)
        fill_row = QHBoxLayout()
        fill_row.addWidget(btn_fill); fill_row.addStretch()
        lo1.addLayout(fill_row)

        root.addWidget(g1)

        # ── 2. Classification settings ───────────────────────────────────
        g2 = QGroupBox("2  Reclassification (continuous 0–1 → classes)")
        lo2 = QVBoxLayout(g2)

        # Split horizontally: left = Continuous settings, right = Binary toggle
        split = QHBoxLayout()

        # ── LEFT: Continuous settings ───────────────────────────────────
        self._cont_frame = QGroupBox("Continuous (reclassify 0-1 → N classes)")
        cf = QVBoxLayout(self._cont_frame)

        cls_info = QLabel(
            "Class 1 = [0, lower threshold].  The remaining range is divided "
            "equally. Set the threshold from Classification Thresholds "
            "(max_TSS, max_Kappa, etc.).\n"
            "Example: 5 classes, threshold 0.20 → 0-0.20, 0.20-0.40, "
            "0.40-0.60, 0.60-0.80, 0.80-1.0"
        )
        cls_info.setWordWrap(True)
        cls_info.setStyleSheet("color:#3a7050; font-size:10pt;")
        cf.addWidget(cls_info)

        cls_row = QHBoxLayout()
        cls_row.addWidget(QLabel("Number of classes :"))
        self.n_classes = QSpinBox()
        self.n_classes.setRange(2, 10); self.n_classes.setValue(5)
        cls_row.addWidget(self.n_classes); cls_row.addStretch()
        cf.addLayout(cls_row)

        thr_ref_row = QHBoxLayout()
        thr_ref_row.addWidget(QLabel("Reference — lower threshold :"))
        self.thr_ref = QDoubleSpinBox()
        self.thr_ref.setRange(0.0, 0.99); self.thr_ref.setValue(0.20)
        self.thr_ref.setSingleStep(0.01); self.thr_ref.setDecimals(3)
        thr_ref_row.addWidget(self.thr_ref); thr_ref_row.addStretch()
        cf.addLayout(thr_ref_row)

        thr_val_row = QHBoxLayout()
        thr_val_row.addWidget(QLabel("Validation — lower threshold :"))
        self.thr_val = QDoubleSpinBox()
        self.thr_val.setRange(0.0, 0.99); self.thr_val.setValue(0.20)
        self.thr_val.setSingleStep(0.01); self.thr_val.setDecimals(3)
        thr_val_row.addWidget(self.thr_val); thr_val_row.addStretch()
        cf.addLayout(thr_val_row)

        self.breaks_preview = QLabel()
        self.breaks_preview.setStyleSheet("color:#6b8f7a; font-size:9pt; padding:4px;")
        cf.addWidget(self.breaks_preview)
        self.n_classes.valueChanged.connect(self._update_preview)
        self.thr_ref.valueChanged.connect(self._update_preview)
        self.thr_val.valueChanged.connect(self._update_preview)

        cf.addStretch()
        split.addWidget(self._cont_frame, 2)

        # ── RIGHT: Binary radio ─────────────────────────────────────────
        self._bin_frame = QGroupBox("Binary comparison")
        bf = QVBoxLayout(self._bin_frame)

        bin_info = QLabel(
            "<b>Binary mode</b> compares two raster maps whose cells are "
            "already categorical — typically <b>0 = absent</b> and "
            "<b>1 = present</b> (binary presence/absence maps).<br><br>"
            "No reclassification or threshold is applied: the raw integer "
            "classes are compared cell-by-cell. Use this mode when you have "
            "an expert-delineated polygon converted to a raster, a published "
            "SDM binary output, or a field-validated presence/absence layer."
        )
        bin_info.setWordWrap(True)
        bin_info.setTextFormat(Qt.TextFormat.RichText)
        bin_info.setStyleSheet(
            "color:#5c4a1a; font-size:10pt; background:#fff8e7; "
            "border-left:4px solid #c8a046; padding:8px; border-radius:0 4px 4px 0;"
        )
        bf.addWidget(bin_info)

        self._rb_binary = QRadioButton("Use binary comparison (0/1 maps)")
        self._rb_binary.setStyleSheet(
            "QRadioButton { font-weight:bold; color:#1d5235; font-size:11pt; "
            "padding:10px; }"
        )
        self._rb_binary.setChecked(False)
        bf.addWidget(self._rb_binary)

        bf.addStretch()
        split.addWidget(self._bin_frame, 1)

        lo2.addLayout(split)

        # Toggle continuous-frame enablement based on the binary checkbox
        def _toggle_mode():
            is_binary = self._rb_binary.isChecked()
            # Disable all continuous widgets
            self._cont_frame.setEnabled(not is_binary)
            self._update_preview()
        self._rb_binary.toggled.connect(_toggle_mode)
        self._update_preview()

        root.addWidget(g2)

        # ── 3. Sampling settings ─────────────────────────────────────────
        g3 = QGroupBox("3  Sampling Settings")
        lo3 = QVBoxLayout(g3)

        meth_lo = QHBoxLayout()
        self._meth_grp = QButtonGroup(self)
        self._rb_rand  = QRadioButton("Random"); self._rb_rand.setChecked(True)
        self._rb_strat = QRadioButton("Stratified")
        self._rb_sys   = QRadioButton("Systematic")
        self._rb_csv   = QRadioButton("CSV File")
        for idx, rb in enumerate((self._rb_rand, self._rb_strat, self._rb_sys, self._rb_csv)):
            self._meth_grp.addButton(rb, idx)
            meth_lo.addWidget(rb)
        meth_lo.addStretch()
        lo3.addLayout(meth_lo)

        # CSV row (hidden by default)
        self._csv_row = QWidget()
        csv_lo = QHBoxLayout(self._csv_row); csv_lo.setContentsMargins(0, 0, 0, 0)
        csv_lo.addWidget(QLabel("CSV (id, x, y, reference_value):"))
        self.csv_path = QLineEdit()
        csv_lo.addWidget(self.csv_path, 1)
        btn_csv = QPushButton("Browse")
        btn_csv.clicked.connect(lambda: self._browse_csv())
        csv_lo.addWidget(btn_csv)
        self._csv_row.setVisible(False)
        lo3.addWidget(self._csv_row)
        self._rb_csv.toggled.connect(self._csv_row.setVisible)

        # n points
        np_lo = QHBoxLayout()
        np_lo.addWidget(QLabel("Number of points :"))
        self.n_points = QSpinBox()
        self.n_points.setRange(30, 100_000)
        self.n_points.setValue(500)
        self.n_points.setSingleStep(50)
        np_lo.addWidget(self.n_points); np_lo.addStretch()
        lo3.addLayout(np_lo)

        root.addWidget(g3)

        # ── Run button ───────────────────────────────────────────────────
        self.btn_run = QPushButton("Run Validation")
        self.btn_run.setStyleSheet(
            "background:#3a8c60;color:#fff;font-weight:bold;"
            "padding:10px;border-radius:5px;font-size:11pt;"
        )
        self.btn_run.clicked.connect(self._run)
        root.addWidget(self.btn_run)

        self.progress = QProgressBar(); self.progress.setVisible(False)
        root.addWidget(self.progress)

        # ── 4. Results ───────────────────────────────────────────────────
        g4 = QGroupBox("4  Results")
        lo4 = QVBoxLayout(g4)
        self.result_text = QTextEdit(); self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(240)
        self.result_text.setStyleSheet(
            "QTextEdit { font-family:'Arial',sans-serif; font-size:9pt; "
            "background:#f5faf7; color:#1c3328; border:1px solid #b8d4c4; "
            "border-radius:4px; padding:8px; }"
        )
        lo4.addWidget(self.result_text)

        ab = QHBoxLayout()
        self.btn_export = QPushButton("Save Report"); self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export)
        self.btn_pts = QPushButton("Save Points CSV"); self.btn_pts.setEnabled(False)
        self.btn_pts.clicked.connect(self._save_points)
        ab.addWidget(self.btn_export); ab.addWidget(self.btn_pts); ab.addStretch()
        lo4.addLayout(ab)

        root.addWidget(g4, 1)

    # ══════════════════════════════════════════════════════════════════════
    # Layer helpers
    # ══════════════════════════════════════════════════════════════════════

    def _update_preview(self):
        # Skip preview if binary mode is active (no breaks used)
        if hasattr(self, "_rb_binary") and self._rb_binary.isChecked():
            self.breaks_preview.setText(
                "Binary mode active - reclassification skipped.")
            return
        n = self.n_classes.value()
        tr = self.thr_ref.value(); tv = self.thr_val.value()
        rb = self._make_breaks(n, tr)
        vb = self._make_breaks(n, tv)
        rl = "  |  ".join(f"{rb[i]:.3f}-{rb[i+1]:.3f}" for i in range(n))
        vl = "  |  ".join(f"{vb[i]:.3f}-{vb[i+1]:.3f}" for i in range(n))
        self.breaks_preview.setText(f"Ref breaks:  {rl}\nVal breaks:  {vl}")

    @staticmethod
    def _make_breaks(n_classes, lower_threshold):
        """Build class break points: [0, lower_threshold, ..., 1.0].
        Class 1 = [0, lower_threshold].
        Classes 2..n = equal intervals from lower_threshold to 1.0.
        """
        if n_classes < 2 or lower_threshold <= 0 or lower_threshold >= 1:
            return np.linspace(0.0, 1.0, n_classes + 1)
        rest = np.linspace(lower_threshold, 1.0, n_classes)  # n_classes points: thr, ..., 1.0
        return np.concatenate(([0.0], rest))

    def _browse_add(self, combo, layer_dict):
        start = self.dlg.state.get("output_dir", "")
        p, _ = QFileDialog.getOpenFileName(
            self, "Select GeoTIFF", start, "GeoTIFF (*.tif *.tiff);;All (*)")
        if p:
            name = os.path.basename(p)
            if name not in layer_dict:
                layer_dict[name] = p
                combo.addItem(name)
            combo.setCurrentText(name)

    def _browse_csv(self):
        start = self.dlg.state.get("output_dir", "")
        p, _ = QFileDialog.getOpenFileName(self, "Select CSV", start, "CSV (*.csv)")
        if p:
            self.csv_path.setText(p)

    def _fill_from_output(self):
        out = self.dlg.state.get("output_dir", "")
        if not out or not os.path.isdir(out):
            QMessageBox.warning(self, "Warning",
                                "No output directory set yet.  Run the analysis first.")
            return
        tifs = []
        for dirpath, _, fnames in os.walk(out):
            for f in sorted(fnames):
                if f.lower().endswith((".tif", ".tiff")):
                    tifs.append(os.path.join(dirpath, f))
        if not tifs:
            QMessageBox.information(self, "Info", "No GeoTIFF files found.")
            return

        # Populate both combos with the same list
        for combo, ld in ((self.ref_combo, self._ref_layers),
                          (self.val_combo, self._val_layers)):
            combo.blockSignals(True)
            for fp in tifs:
                name = os.path.relpath(fp, out)
                if name not in ld:
                    ld[name] = fp
                    combo.addItem(name)
            combo.blockSignals(False)

        self.dlg.log(f"Validation: loaded {len(tifs)} layers from output directory.")

    def _get_path(self, combo, layer_dict):
        name = combo.currentText()
        return layer_dict.get(name, "")

    # ══════════════════════════════════════════════════════════════════════
    # Raster I/O
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _read_raster(path):
        import rasterio
        with rasterio.open(path) as src:
            data = src.read(1).astype(float)
            nodata = src.nodata
            transform = src.transform
            w, h = src.width, src.height
            bounds = src.bounds
        if nodata is not None:
            data[data == nodata] = np.nan
        return data, transform, w, h, bounds

    # ══════════════════════════════════════════════════════════════════════
    # Reclassification (continuous 0–1 → N equal-interval classes)
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _reclassify(data, breaks):
        """Reclassify a 0–1 probability raster using pre-computed breaks."""
        n_classes = len(breaks) - 1
        out = np.full_like(data, np.nan)
        valid = np.isfinite(data)
        for i in range(n_classes):
            lo, hi = breaks[i], breaks[i + 1]
            if i < n_classes - 1:
                mask = valid & (data >= lo) & (data < hi)
            else:
                mask = valid & (data >= lo) & (data <= hi)
            out[mask] = i + 1
        return out

    @staticmethod
    def _class_labels(breaks):
        n = len(breaks) - 1
        return [f"C{i+1} [{breaks[i]:.3f}–{breaks[i+1]:.3f}]" for i in range(n)]

    # ══════════════════════════════════════════════════════════════════════
    # Sampling
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _sample_random(data, n):
        valid = np.argwhere(np.isfinite(data))
        if len(valid) == 0:
            return []
        idx = valid[np.random.choice(len(valid), min(n, len(valid)), replace=False)]
        return [(int(r), int(c)) for r, c in idx]

    @staticmethod
    def _sample_stratified(data, n):
        classes = np.unique(data[np.isfinite(data)])
        per_cls = max(1, n // len(classes))
        pts = []
        for cv in classes:
            locs = np.argwhere(data == cv)
            k = min(per_cls, len(locs))
            sel = locs[np.random.choice(len(locs), k, replace=False)]
            pts.extend([(int(r), int(c)) for r, c in sel])
        return pts

    @staticmethod
    def _sample_systematic(data, n):
        h, w = data.shape
        g = int(np.sqrt(n))
        rs = np.linspace(0, h - 1, g, dtype=int)
        cs = np.linspace(0, w - 1, g, dtype=int)
        pts = []
        for r in rs:
            for c in cs:
                if np.isfinite(data[r, c]):
                    pts.append((int(r), int(c)))
                if len(pts) >= n:
                    return pts
        return pts

    # ══════════════════════════════════════════════════════════════════════
    # CSV loading
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _load_csv_points(csv_path, transform, w, h):
        pts = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for rec in reader:
                try:
                    x = float(rec["x"]); y = float(rec["y"])
                    rv = float(rec["reference_value"])
                    col, row = ~transform * (x, y)
                    row, col = int(row), int(col)
                    if 0 <= row < h and 0 <= col < w:
                        pts.append({"row": row, "col": col,
                                    "coord_x": x, "coord_y": y,
                                    "ref_value": rv,
                                    "id": rec.get("id", str(len(pts)))})
                except (ValueError, KeyError):
                    continue
        return pts

    # ══════════════════════════════════════════════════════════════════════
    # Main run
    # ══════════════════════════════════════════════════════════════════════

    def _run(self):
        try:
            self._run_inner()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            self.progress.setVisible(False)

    def _run_inner(self):
        import time as _time
        _t0 = _time.perf_counter()

        val_path = self._get_path(self.val_combo, self._val_layers)
        if not val_path or not os.path.isfile(val_path):
            QMessageBox.warning(self, "Warning", "Please select a Validation Map.")
            return

        use_csv = self._rb_csv.isChecked()
        n_cls = self.n_classes.value()
        thr_ref = self.thr_ref.value()
        thr_val = self.thr_val.value()

        # Compute breaks for each map
        ref_breaks = self._make_breaks(n_cls, thr_ref)
        val_breaks = self._make_breaks(n_cls, thr_val)

        self.progress.setVisible(True); self.progress.setValue(0)
        self.result_text.clear()
        self._log("Reading validation raster…")
        QApplication.processEvents()

        val_raw, val_tf, val_w, val_h, _ = self._read_raster(val_path)
        self.progress.setValue(10)

        # If not CSV mode, also read the reference raster dimensions now
        # so we can resample the validation raster to match the reference grid
        if not use_csv:
            ref_path_early = self._get_path(self.ref_combo, self._ref_layers)
            if ref_path_early and os.path.isfile(ref_path_early):
                import rasterio
                from rasterio.enums import Resampling
                with rasterio.open(ref_path_early) as ref_src:
                    r_h, r_w = ref_src.height, ref_src.width
                if r_h != val_h or r_w != val_w:
                    self._log(f"  Resampling validation raster ({val_h}x{val_w}) "
                              f"to match reference ({r_h}x{r_w})…")
                    with rasterio.open(val_path) as src:
                        val_raw = src.read(1, out_shape=(r_h, r_w),
                                          resampling=Resampling.bilinear).astype(float)
                        nd = src.nodata
                        if nd is not None:
                            val_raw[val_raw == nd] = np.nan
                    val_h, val_w = r_h, r_w

        # Diagnostics
        vv = val_raw[np.isfinite(val_raw)]
        self._log(f"  Val raster: {len(vv)} valid px, min={vv.min():.4f} max={vv.max():.4f} "
                  f"mean={vv.mean():.4f}  unique={len(np.unique(vv))}")
        QApplication.processEvents()

        # Binary mode toggle: if enabled, skip all reclassification on BOTH rasters
        binary_mode = self._rb_binary.isChecked()

        if binary_mode:
            self._log("Binary mode: validation raster used as-is (no reclassification).")
            val_cls = np.where(np.isfinite(val_raw), np.round(val_raw), np.nan)
            val_labels = [f"Class {int(c)}" for c in
                          sorted(np.unique(val_cls[np.isfinite(val_cls)]).astype(int))]
        else:
            self._log(f"Reclassifying validation into {n_cls} classes  "
                      f"breaks={[round(x,3) for x in val_breaks]}")
            QApplication.processEvents()
            val_cls = self._reclassify(val_raw, val_breaks)
            val_labels = self._class_labels(val_breaks)

        # Log class distribution
        vc = val_cls[np.isfinite(val_cls)]
        classes_seen = sorted(int(c) for c in np.unique(vc))
        for ci in classes_seen:
            cnt = int(np.sum(vc == ci))
            self._log(f"    Class {ci}: {cnt} pixels")
        QApplication.processEvents()

        ref_labels = self._class_labels(ref_breaks)
        self.progress.setValue(20)

        if use_csv:
            # ── CSV mode ──
            csv_p = self.csv_path.text().strip()
            if not csv_p or not os.path.isfile(csv_p):
                QMessageBox.warning(self, "Warning", "Please select a CSV file.")
                self.progress.setVisible(False); return

            self._log("Loading CSV points…")
            QApplication.processEvents()
            csv_pts = self._load_csv_points(csv_p, val_tf, val_w, val_h)
            if not csv_pts:
                QMessageBox.critical(self, "Error", "No valid points in CSV.")
                self.progress.setVisible(False); return

            # Reclassify CSV reference values using reference breaks
            ref_cats, val_cats = [], []
            valid_pts = []
            for pt in csv_pts:
                rv = pt["ref_value"]
                vc = val_cls[pt["row"], pt["col"]]
                rc = self._value_to_class(rv, ref_breaks, n_cls)
                if np.isfinite(vc) and rc is not None:
                    ref_cats.append(int(rc))
                    val_cats.append(int(vc))
                    pt["ref_class"] = int(rc); pt["val_class"] = int(vc)
                    pt["cls_value"] = float(val_raw[pt["row"], pt["col"]])
                    valid_pts.append(pt)
            self._points = valid_pts
            ref_name = os.path.basename(csv_p)
            method_str = "CSV"
        else:
            # ── Raster vs Raster mode ──
            ref_path = self._get_path(self.ref_combo, self._ref_layers)
            if not ref_path or not os.path.isfile(ref_path):
                QMessageBox.warning(self, "Warning", "Please select a Reference Map.")
                self.progress.setVisible(False); return

            self._log("Reading reference raster…")
            QApplication.processEvents()
            ref_raw, ref_tf, ref_w, ref_h, _ = self._read_raster(ref_path)
            self.progress.setValue(25)

            rv = ref_raw[np.isfinite(ref_raw)]
            self._log(f"  Ref raster: {len(rv)} valid px, min={rv.min():.4f} max={rv.max():.4f} "
                      f"mean={rv.mean():.4f}  unique={len(np.unique(rv))}")
            QApplication.processEvents()

            if binary_mode:
                self._log("Binary mode: reference raster used as-is (no reclassification).")
                ref_cls = np.where(np.isfinite(ref_raw), np.round(ref_raw), np.nan)
                classes_ref = sorted(int(c) for c in
                                    np.unique(ref_cls[np.isfinite(ref_cls)]))
                ref_labels = [f"Class {c}" for c in classes_ref]
            else:
                self._log(f"Reclassifying reference  breaks={[round(x,3) for x in ref_breaks]}")
                ref_cls = self._reclassify(ref_raw, ref_breaks)

            rc = ref_cls[np.isfinite(ref_cls)]
            classes_seen = sorted(int(c) for c in np.unique(rc))
            for ci in classes_seen:
                cnt = int(np.sum(rc == ci))
                self._log(f"    Class {ci}: {cnt} pixels")
            QApplication.processEvents()
            self.progress.setValue(30)

            # Sampling
            n = self.n_points.value()
            mid = self._meth_grp.checkedId()
            method_str = {0: "Random", 1: "Stratified", 2: "Systematic"}[mid]
            self._log(f"Sampling {n} points ({method_str})…")
            QApplication.processEvents()

            if mid == 0:
                pixels = self._sample_random(ref_cls, n)
            elif mid == 1:
                pixels = self._sample_stratified(ref_cls, n)
            else:
                pixels = self._sample_systematic(ref_cls, n)

            ref_cats, val_cats = [], []
            valid_pts = []
            for r, c in pixels:
                if r < ref_h and c < ref_w and r < val_h and c < val_w:
                    rc = ref_cls[r, c]; vc = val_cls[r, c]
                    if np.isfinite(rc) and np.isfinite(vc):
                        ref_cats.append(int(rc))
                        val_cats.append(int(vc))
                        x, y = ref_tf * (c, r)
                        valid_pts.append({
                            "row": r, "col": c,
                            "coord_x": x, "coord_y": y,
                            "ref_value": float(ref_raw[r, c]),
                            "cls_value": float(val_raw[r, c]),
                            "ref_class": int(rc), "val_class": int(vc),
                        })
            self._points = valid_pts
            ref_name = os.path.basename(ref_path)

            # Save reclassified rasters to validation/ subfolder
            self._save_reclassified(ref_path, ref_cls, ref_raw, "Reclassify_ref")
            self._save_reclassified(val_path, val_cls, val_raw, "Reclassify_val")

        self.progress.setValue(50)

        if not ref_cats:
            QMessageBox.critical(self, "Error", "No valid overlapping points found.")
            self.progress.setVisible(False); return

        self._log(f"  {len(ref_cats)} valid points")
        QApplication.processEvents()

        # ── Metrics ──────────────────────────────────────────────────────
        self._log("Computing metrics…")
        QApplication.processEvents()
        self.progress.setValue(70)

        # Build the set of category labels from the actual data so that
        # binary / categorical rasters (0/1/2...) are handled as well as the
        # classical continuous reclassification (classes 1..n_cls).
        all_cats = sorted(set(ref_cats) | set(val_cats))
        if not all_cats:
            all_cats = list(range(1, n_cls + 1))

        cm = confusion_matrix(ref_cats, val_cats, labels=all_cats)
        oa = accuracy_score(ref_cats, val_cats)
        kappa = cohen_kappa_score(ref_cats, val_cats)
        f1_mac = f1_score(ref_cats, val_cats, labels=all_cats, average="macro", zero_division=0)
        f1_wt  = f1_score(ref_cats, val_cats, labels=all_cats, average="weighted", zero_division=0)
        prec   = precision_score(ref_cats, val_cats, labels=all_cats, average="macro", zero_division=0)
        rec    = recall_score(ref_cats, val_cats, labels=all_cats, average="macro", zero_division=0)

        # Regression on raw pixel values
        raw_ref = np.array([p["ref_value"] for p in self._points], float)
        raw_val = np.array([p["cls_value"] for p in self._points], float)
        r2   = r2_score(raw_ref, raw_val) if len(raw_ref) > 1 else 0.0
        rmse = float(np.sqrt(mean_squared_error(raw_ref, raw_val)))
        mae  = float(mean_absolute_error(raw_ref, raw_val))
        bias = float(np.mean(raw_val - raw_ref))

        # Use ref_labels for display; if the number of ref_labels does not
        # match the actual categories (common for binary/categorical rasters),
        # generate generic class labels on the fly.
        if len(ref_labels) == len(all_cats):
            display_labels = ref_labels
        else:
            display_labels = [f"Class {c}" for c in all_cats]

        cls_report = classification_report(
            ref_cats, val_cats, labels=all_cats,
            target_names=display_labels, zero_division=0, output_dict=True)

        elapsed = _time.perf_counter() - _t0

        self._results = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "Binary" if binary_mode else "Continuous",
            "reference": ref_name,
            "validation": os.path.basename(val_path),
            "n_classes": len(all_cats) if binary_mode else n_cls,
            "threshold_ref": thr_ref,
            "threshold_val": thr_val,
            "ref_breaks": ref_breaks.tolist(),
            "val_breaks": val_breaks.tolist(),
            "n_points": len(ref_cats),
            "method": method_str,
            "oa": float(oa), "kappa": float(kappa),
            "f1_macro": float(f1_mac), "f1_weighted": float(f1_wt),
            "precision_macro": float(prec), "recall_macro": float(rec),
            "r2": float(r2), "rmse": rmse, "mae": mae, "bias": bias,
            "cm": cm.tolist(), "labels": display_labels, "categories": all_cats,
            "ref_labels": ref_labels, "val_labels": val_labels,
            "class_report": cls_report,
            "elapsed_s": round(elapsed, 1),
        }

        self.progress.setValue(90)
        self._display()
        self.progress.setValue(100)
        self.btn_export.setEnabled(True)
        self.btn_pts.setEnabled(True)
        self.dlg.log(
            f"Validation complete — OA={oa:.4f}  Kappa={kappa:.4f}  "
            f"({n_cls} classes, {len(ref_cats)} pts, {elapsed:.1f}s)")
        self.progress.setVisible(False)

    def _save_reclassified(self, src_path, classified, raw_data, prefix):
        """Save reclassified raster to output_dir/validation/ folder."""
        import rasterio
        out_base = self.dlg.state.get("output_dir", "")
        if not out_base:
            return
        val_dir = os.path.join(out_base, "validation")
        os.makedirs(val_dir, exist_ok=True)

        src_name = os.path.splitext(os.path.basename(src_path))[0]
        out_path = os.path.join(val_dir, f"{prefix}_{src_name}.tif")

        with rasterio.open(src_path) as src:
            meta = src.meta.copy()
        meta.update(dtype="float32", count=1, nodata=-9999.0)

        out_arr = np.where(np.isfinite(classified), classified, -9999.0).astype(np.float32)
        with rasterio.open(out_path, "w", **meta) as dst:
            dst.write(out_arr, 1)

        self._log(f"  Saved: {out_path}")

    @staticmethod
    def _value_to_class(val, breaks, n_cls=None):
        """Assign a single float value to a class using break points."""
        if not np.isfinite(val):
            return None
        nc = len(breaks) - 1
        for i in range(nc):
            lo, hi = breaks[i], breaks[i + 1]
            if i < nc - 1:
                if lo <= val < hi:
                    return i + 1
            else:
                if lo <= val <= hi:
                    return i + 1
        return None

    # ══════════════════════════════════════════════════════════════════════
    # Display
    # ══════════════════════════════════════════════════════════════════════

    def _log(self, msg):
        self.result_text.append(f"▸ {msg}")

    def _display(self):
        R = self._results
        L = R["labels"]; CM = np.array(R["cm"])
        is_binary = (R.get("mode") == "Binary")

        t  = "=" * 78 + "\n"
        if is_binary:
            t += "  HABITUS Validation — BINARY Classification Accuracy Assessment\n"
        else:
            t += "  HABITUS Validation — Classification Accuracy Assessment\n"
        t += "=" * 78 + "\n\n"
        t += f"  Mode         : {R.get('mode', 'Continuous')}\n"
        t += f"  Date         : {R['timestamp']}\n"
        t += f"  Reference    : {R['reference']}\n"
        t += f"  Validation   : {R['validation']}\n"

        if is_binary:
            t += f"  Classes      : {R['n_classes']}  (binary / categorical - raw cell values)\n"
        else:
            t += f"  Classes      : {R['n_classes']}  (continuous reclassified)\n"
            t += f"  Ref threshold: {R['threshold_ref']:.3f}  ->  breaks: {[round(x,3) for x in R['ref_breaks']]}\n"
            t += f"  Val threshold: {R['threshold_val']:.3f}  ->  breaks: {[round(x,3) for x in R['val_breaks']]}\n"

        t += f"  Points       : {R['n_points']}   Method: {R['method']}\n"
        t += f"  Time         : {R['elapsed_s']}s\n\n"

        t += "-" * 78 + "\n  PRIMARY METRICS\n" + "-" * 78 + "\n"
        t += f"  Overall Accuracy (OA)  : {R['oa']:.4f}  ({R['oa']*100:.2f}%)\n"
        t += f"  Cohen's Kappa (κ)      : {R['kappa']:.4f}\n"
        t += f"  F1-Score (Macro)       : {R['f1_macro']:.4f}\n"
        t += f"  F1-Score (Weighted)    : {R['f1_weighted']:.4f}\n"
        t += f"  Precision (Macro)      : {R['precision_macro']:.4f}\n"
        t += f"  Recall (Macro)         : {R['recall_macro']:.4f}\n\n"

        k = R["kappa"]
        interp = ("Poor" if k < 0 else "Slight" if k < .2 else "Fair" if k < .4
                   else "Moderate" if k < .6 else "Substantial" if k < .8
                   else "Almost Perfect")
        t += f"  Kappa Interpretation   : {interp}\n\n"

        if is_binary:
            # Binary-specific: TP/FP/TN/FN + sensitivity/specificity/TSS
            if len(L) == 2:
                # Assume [Class 0, Class 1] order -> TN FP / FN TP
                tn = int(CM[0, 0]); fp = int(CM[0, 1])
                fn = int(CM[1, 0]); tp = int(CM[1, 1])
                sens = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
                tss  = sens + spec - 1
                t += "-" * 78 + "\n  BINARY SUMMARY\n" + "-" * 78 + "\n"
                t += f"  True Positive  (TP) : {tp}\n"
                t += f"  False Positive (FP) : {fp}\n"
                t += f"  True Negative  (TN) : {tn}\n"
                t += f"  False Negative (FN) : {fn}\n"
                t += f"  Sensitivity         : {sens:.4f}\n"
                t += f"  Specificity         : {spec:.4f}\n"
                t += f"  True Skill Stat TSS : {tss:.4f}\n\n"
        else:
            t += "-" * 78 + "\n  REGRESSION - Raw Pixel Values (0-1)\n" + "-" * 78 + "\n"
            t += f"  R^2  : {R['r2']:.4f}\n  RMSE : {R['rmse']:.4f}\n"
            t += f"  MAE  : {R['mae']:.4f}\n  Bias : {R['bias']:.4f}"
            t += (" (Over)" if R["bias"] > 0 else " (Under)" if R["bias"] < 0 else "") + "\n\n"

        # Confusion matrix
        t += "-" * 78 + "\n  CONFUSION MATRIX\n" + "-" * 78 + "\n"
        cw = max(14, max((len(n) for n in L), default=6) + 2)
        hdr = "  Ref \\ Val".ljust(cw)
        for n in L:
            hdr += f"{n:>{cw}}"
        t += hdr + "\n"
        for i, row in enumerate(CM):
            line = f"  {L[i]:{cw - 2}}"
            for v in row:
                line += f"{v:>{cw}}"
            t += line + "\n"
        t += "\n"

        # Per-class
        t += "-" * 78 + "\n  PER-CLASS METRICS\n" + "-" * 78 + "\n"
        t += f"  {'Class':<22} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}\n"
        for name in L:
            if name in R["class_report"]:
                m = R["class_report"][name]
                t += (f"  {name:<22} {m['precision']:>10.4f} {m['recall']:>10.4f} "
                      f"{m['f1-score']:>10.4f} {int(m['support']):>10}\n")

        # Producer / User accuracy
        t += "\n" + "-" * 78 + "\n  PRODUCER'S & USER'S ACCURACY\n" + "-" * 78 + "\n"
        t += f"  {'Class':<22} {'Producer':>12} {'User':>12}\n"
        for name in L:
            if name in R["class_report"]:
                m = R["class_report"][name]
                t += f"  {name:<22} {m['recall']:>12.4f} {m['precision']:>12.4f}\n"

        t += "\n" + "=" * 78 + "\n  Generated by HABITUS Validation Module\n"
        t += "=" * 78 + "\n"

        self.result_text.setPlainText(t)

    # ══════════════════════════════════════════════════════════════════════
    # Export
    # ══════════════════════════════════════════════════════════════════════

    def _export(self):
        if not self._results:
            return
        out = self.dlg.state.get("output_dir", "")
        default = os.path.join(out, f"validation_report_{datetime.now():%Y%m%d_%H%M%S}")
        p, _ = QFileDialog.getSaveFileName(
            self, "Save Report", default,
            "Text (*.txt);;JSON (*.json);;HTML (*.html)")
        if not p:
            return
        try:
            if p.endswith(".json"):
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(self._results, f, indent=2, ensure_ascii=False)
            elif p.endswith(".html"):
                with open(p, "w", encoding="utf-8") as f:
                    f.write(self._build_html())
            else:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(self.result_text.toPlainText())
            QMessageBox.information(self, "Saved", f"Report saved:\n{p}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _save_points(self):
        if not self._points:
            return
        out = self.dlg.state.get("output_dir", "")
        default = os.path.join(out, f"validation_points_{datetime.now():%Y%m%d_%H%M%S}.csv")
        p, _ = QFileDialog.getSaveFileName(self, "Save Points", default, "CSV (*.csv)")
        if not p:
            return
        try:
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["id", "x", "y", "ref_value", "val_value",
                            "ref_class", "val_class", "match"])
                for i, pt in enumerate(self._points):
                    w.writerow([
                        pt.get("id", i + 1),
                        round(pt["coord_x"], 6), round(pt["coord_y"], 6),
                        round(pt.get("ref_value", 0), 6),
                        round(pt.get("cls_value", 0), 6),
                        pt.get("ref_class", ""),
                        pt.get("val_class", ""),
                        "Yes" if pt.get("ref_class") == pt.get("val_class") else "No",
                    ])
            QMessageBox.information(self, "Saved", f"Points saved:\n{p}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _build_html(self):
        R = self._results
        L = R["labels"]; CM = np.array(R["cm"])
        rows = ""
        for i, row in enumerate(CM):
            cells = "".join(f"<td>{v}</td>" for v in row)
            rows += f"<tr><th>{L[i]}</th>{cells}</tr>\n"
        hdr_cells = "".join(f"<th>{n}</th>" for n in L)

        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>HABITUS Validation Report</title>
<style>
body{{font-family:'Arial',sans-serif;margin:40px;background:#f5f5f5;}}
.c{{max-width:960px;margin:auto;background:#fff;padding:30px;border-radius:8px;
   box-shadow:0 2px 8px rgba(0,0,0,.1);}}
h1{{color:#1d5235;border-bottom:3px solid #3a8c60;padding-bottom:8px;}}
h2{{color:#2a6e45;border-left:4px solid #3a8c60;padding-left:12px;margin-top:28px;}}
.m{{background:#eef6f1;padding:14px;margin:12px 0;border-radius:6px;border-left:4px solid #3a8c60;}}
.v{{font-size:1.2em;font-weight:bold;color:#1d5235;}}
table{{border-collapse:collapse;width:100%;margin:16px 0;}}
th,td{{border:1px solid #cde0d4;padding:10px;text-align:center;}}
th{{background:#3a8c60;color:#fff;}}
tr:nth-child(even){{background:#f0f8f3;}}
.ft{{margin-top:30px;border-top:2px solid #ddeee6;padding-top:12px;color:#7a9988;font-size:.9em;}}
</style></head><body><div class="c">
<h1>HABITUS Validation Report</h1>
<p><b>Date:</b> {R['timestamp']} &nbsp; <b>Points:</b> {R['n_points']}
   &nbsp; <b>Classes:</b> {R['n_classes']} &nbsp; <b>Method:</b> {R['method']}</p>
<p><b>Reference:</b> {R['reference']} &nbsp; <b>Validation:</b> {R['validation']}</p>
<h2>Primary Metrics</h2>
<div class="m"><b>Overall Accuracy:</b> <span class="v">{R['oa']:.4f} ({R['oa']*100:.2f}%)</span></div>
<div class="m"><b>Cohen's Kappa:</b> <span class="v">{R['kappa']:.4f}</span></div>
<div class="m"><b>F1 Macro:</b> {R['f1_macro']:.4f} &nbsp; <b>Weighted:</b> {R['f1_weighted']:.4f}</div>
<div class="m"><b>Precision:</b> {R['precision_macro']:.4f} &nbsp; <b>Recall:</b> {R['recall_macro']:.4f}</div>
<h2>Regression — Raw Values (0–1)</h2>
<div class="m">R²={R['r2']:.4f} &nbsp; RMSE={R['rmse']:.4f} &nbsp; MAE={R['mae']:.4f} &nbsp; Bias={R['bias']:.4f}</div>
<h2>Confusion Matrix</h2>
<table><tr><th>Ref \\ Val</th>{hdr_cells}</tr>{rows}</table>
<div class="ft">Generated by HABITUS Validation Module</div>
</div></body></html>"""
