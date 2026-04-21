# -*- coding: utf-8 -*-
"""
Tab ① – Data Formatting

Background / Pseudo-Absence explained:
  • ML models (GLM, RF, GBM, SVM, ANN, BRT, GAM):
      Use PSEUDO-ABSENCES — randomly sampled background cells treated as
      absence observations. Number = n_absences, repetitions = n_pa_rep.

  • MaxEnt:
      Uses BACKGROUND POINTS — random sample of the study area that
      characterises the available environment. MaxEnt does NOT treat these
      as absences; it uses them to define the background distribution.
      Number = n_background (typically 10 000).
      Both sets are generated here and stored separately.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QComboBox,
    QGroupBox, QFileDialog, QListWidget,
    QAbstractItemView, QMessageBox, QTabWidget,
    QDoubleSpinBox, QCheckBox
)
from PyQt6.QtCore import Qt


class DataTab(QWidget):

    def __init__(self, main_dialog):
        super().__init__()
        self.dlg = main_dialog
        self._worker = None
        self._csv_cols = None   # (species_col, lon_col, lat_col) set by _inspect_csv
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        # ── Occurrence CSV ──────────────────────────────────────────────
        occ_group = QGroupBox("Occurrence Data (CSV)")
        occ_form  = QFormLayout(occ_group)
        occ_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        occ_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        occ_form.setHorizontalSpacing(12)
        occ_form.setVerticalSpacing(6)

        self.occ_path = QLineEdit()
        self.occ_path.setPlaceholderText("Path to presence/occurrence CSV file…")
        btn_occ = QPushButton("Browse…"); btn_occ.setObjectName("btn_secondary")
        btn_occ.clicked.connect(self._browse_occ)
        occ_row = QHBoxLayout(); occ_row.addWidget(self.occ_path); occ_row.addWidget(btn_occ)

        # Column preview label — filled automatically when a CSV is loaded
        self._col_preview = QLabel(
            "ℹ  The first 3 columns will always be used:  "
            "① Species name  ·  ② Longitude  ·  ③ Latitude")
        self._col_preview.setWordWrap(True)
        self._col_preview.setStyleSheet(
            "color:#1c3328; background:#d4edda; border:1px solid #52b788;"
            "border-radius:4px; padding:5px 8px; font-size:11px;")

        occ_form.addRow("CSV file:", occ_row)
        occ_form.addRow("", self._col_preview)
        layout.addWidget(occ_group)

        # ── Environmental Rasters — iki ayrı grup ───────────────────────
        rast_tabs = QTabWidget(); rast_tabs.setObjectName("sdm_tabs")
        rast_tabs.addTab(self._build_cont_rasters(), "Continuous Rasters")
        rast_tabs.addTab(self._build_cat_rasters(),  "Categorical Rasters")
        layout.addWidget(rast_tabs)

        # ── Background / Pseudo-absence settings ────────────────────────
        bg_group = QGroupBox(
            "Background & Pseudo-Absence Settings")
        bg_tabs  = QTabWidget(); bg_tabs.setObjectName("sdm_tabs")

        bg_tabs.addTab(self._build_pa_tab(),    "ML Models (Pseudo-Absences)")
        bg_tabs.addTab(self._build_mx_tab(),    "MaxEnt (Background Points)")
        bg_tabs.addTab(self._build_ponly_tab(), "ENFA / Mahalanobis (Presence-Only)")

        bg_layout = QVBoxLayout(bg_group)
        bg_layout.addWidget(bg_tabs)
        layout.addWidget(bg_group)

        # ── Output directory ────────────────────────────────────────────
        out_group  = QGroupBox("Output Directory")
        out_layout = QHBoxLayout(out_group)
        self.out_dir = QLineEdit()
        self.out_dir.setPlaceholderText("Directory for all HABITUS outputs…")
        btn_out = QPushButton("Browse…"); btn_out.setObjectName("btn_secondary")
        btn_out.clicked.connect(self._browse_outdir)
        out_layout.addWidget(self.out_dir); out_layout.addWidget(btn_out)
        layout.addWidget(out_group)


        btn_run = QPushButton("▶  Load Data & Generate Background/Pseudo-Absence Points")
        btn_run.clicked.connect(self._run)
        layout.addWidget(btn_run)

    # ── Pseudo-absence tab ────────────────────────────────────────────────

    def _build_pa_tab(self):
        w = QWidget(); f = QFormLayout(w); f.setContentsMargins(8, 8, 8, 8)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        f.setHorizontalSpacing(12); f.setVerticalSpacing(6)

        note = QLabel(
            "Pseudo-absences are randomly sampled background cells treated as "
            "'absent' observations when training GLM, RF, GBM, SVM, ANN, BRT and GAM.\n"
            "Multiple repetitions reduce sampling bias.")
        note.setWordWrap(True); note.setStyleSheet("font-size:10px;")
        f.addRow(note)

        self.n_pa_rep   = QSpinBox()
        self.n_pa_rep.setRange(1, 10); self.n_pa_rep.setValue(2)
        self.n_pa_rep.setToolTip(
            "Number of independent PA sets — models are run once per set, "
            "then results are averaged. 2–5 recommended.")

        self.n_absences = QSpinBox()
        self.n_absences.setRange(100, 100000); self.n_absences.setValue(1000)
        self.n_absences.setSingleStep(500)
        self.n_absences.setToolTip(
            "Pseudo-absences per repetition. "
            "Typically 1 000–10 000; should be ≥ number of presences.")

        self.pa_strategy = QComboBox()
        self.pa_strategy.addItems(["random", "disk", "sre"])
        self.pa_strategy.setToolTip(
            "random: uniform random sampling (Barbet-Massin et al. 2012)\n"
            "disk:   exclude cells within min-distance from presences\n"
            "sre:    Surface Range Envelope (Busby 1991; Thuiller et al. 2003)\n"
            "        Samples from cells OUTSIDE the bioclimatic envelope\n"
            "        (5th-95th pctile of each variable at presence locs).")

        self.pa_min_dist = QDoubleSpinBox()
        self.pa_min_dist.setRange(0, 500); self.pa_min_dist.setValue(10)
        self.pa_min_dist.setSuffix(" km")
        self.pa_min_dist.setToolTip(
            "Minimum distance from any presence point (used for 'disk' strategy only)")

        f.addRow("PA repetitions:", self.n_pa_rep)
        f.addRow("Pseudo-absences per repetition:", self.n_absences)
        f.addRow("Sampling strategy:", self.pa_strategy)
        f.addRow("Min. distance from presences (disk):", self.pa_min_dist)
        return w

    # ── MaxEnt background tab ─────────────────────────────────────────────

    def _build_mx_tab(self):
        w = QWidget(); f = QFormLayout(w); f.setContentsMargins(8, 8, 8, 8)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        f.setHorizontalSpacing(12); f.setVerticalSpacing(6)

        note = QLabel(
            "MaxEnt uses BACKGROUND POINTS to characterise the available environment. "
            "These are NOT absence records — MaxEnt learns to distinguish presence "
            "locations from random background.\n\n"
            "Rule of thumb: 10 000 background points for regional studies; "
            "fewer for small study areas. "
            "Background is sampled once and reused across all MaxEnt runs.")
        note.setWordWrap(True); note.setStyleSheet("font-size:10px;")
        f.addRow(note)

        self.n_background = QSpinBox()
        self.n_background.setRange(100, 200000); self.n_background.setValue(10000)
        self.n_background.setSingleStep(1000)
        self.n_background.setToolTip(
            "Number of random background points for MaxEnt. "
            "10 000 is a common default (Phillips et al. 2006).")

        self.mx_bg_strategy = QComboBox()
        self.mx_bg_strategy.addItems(["random", "disk"])
        self.mx_bg_strategy.setToolTip(
            "random: uniform random sample from the study extent\n"
            "disk: sample at least min_dist away from any presence point "
            "(reduces spatial autocorrelation)")

        self.mx_min_dist = QDoubleSpinBox()
        self.mx_min_dist.setRange(0, 500); self.mx_min_dist.setValue(0)
        self.mx_min_dist.setSuffix(" km")
        self.mx_min_dist.setToolTip("Minimum distance from presences (disk only; 0 = no constraint)")

        self.chk_mx_bias = QCheckBox(
            "Apply geographic bias correction (use presence density as sampling weight)")
        self.chk_mx_bias.setChecked(False)
        self.chk_mx_bias.setToolTip(
            "Weights background sampling by presence-record density — "
            "reduces the effect of uneven survey effort (Phillips & Dudík 2008)")

        self.chk_mx_save_csv = QCheckBox(
            "Save background points to CSV  (background_maxent.csv)")
        self.chk_mx_save_csv.setChecked(False)
        self.chk_mx_save_csv.setToolTip(
            "Saves the sampled background point coordinates and extracted "
            "environmental values to a CSV file in the output directory.\n"
            "Columns: longitude, latitude, <variable names>")

        f.addRow("Background points:", self.n_background)
        f.addRow("Sampling strategy:", self.mx_bg_strategy)
        f.addRow("Min. distance from presences:", self.mx_min_dist)
        f.addRow("", self.chk_mx_bias)
        f.addRow("", self.chk_mx_save_csv)
        return w

    def _build_ponly_tab(self):
        """Settings for presence-only algorithms: ENFA and Mahalanobis."""
        from PyQt6.QtWidgets import QFormLayout as _FL
        w = QWidget(); f = _FL(w)
        f.setContentsMargins(8, 8, 8, 8)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        f.setFieldGrowthPolicy(_FL.FieldGrowthPolicy.ExpandingFieldsGrow)
        f.setHorizontalSpacing(12); f.setVerticalSpacing(6)

        note = QLabel(
            "ENFA and Mahalanobis are presence-only algorithms.\n"
            "They do NOT use pseudo-absences.\n\n"
            "Background points are used ONLY to estimate the global environmental\n"
            "distribution (ENFA marginality axis). If not set, the pseudo-absence\n"
            "pool from the ML Models tab is used as a fallback.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #94A3B8; font-size: 10px; font-style: italic;")
        f.addRow(note)

        self.ponly_use_bg = QCheckBox("Use dedicated background sample (recommended)")
        self.ponly_use_bg.setChecked(True)
        self.ponly_use_bg.setToolTip(
            "When checked, a random background sample is drawn from the raster extent\n"
            "to estimate global environmental conditions.\n"
            "When unchecked, the PA pool from the ML tab is reused.")
        f.addRow("", self.ponly_use_bg)

        self.ponly_n_bg = QSpinBox()
        self.ponly_n_bg.setRange(100, 100000); self.ponly_n_bg.setValue(5000)
        self.ponly_n_bg.setSingleStep(1000)
        self.ponly_n_bg.setToolTip(
            "Number of random background points for global niche estimation.\n"
            "5000–10000 is sufficient for most study areas.")
        f.addRow("Background points:", self.ponly_n_bg)

        self.ponly_strategy = QComboBox()
        self.ponly_strategy.addItems(["random", "disk"])
        self.ponly_strategy.setToolTip(
            "random: uniform sampling over raster extent.\n"
            "disk: exclude a buffer around presence records.")
        f.addRow("Sampling strategy:", self.ponly_strategy)

        self.ponly_min_dist = QDoubleSpinBox()
        self.ponly_min_dist.setRange(0, 500); self.ponly_min_dist.setValue(0)
        self.ponly_min_dist.setSuffix(" km")
        self.ponly_min_dist.setToolTip("Minimum distance from presences (disk strategy only)")
        f.addRow("Min. distance from presences:", self.ponly_min_dist)

        # Toggle visibility
        def _toggle(state):
            for w in [self.ponly_n_bg, self.ponly_strategy, self.ponly_min_dist]:
                w.setEnabled(bool(state))
        self.ponly_use_bg.stateChanged.connect(_toggle)
        return w

    # ── File dialogs ──────────────────────────────────────────────────────

    def _build_cont_rasters(self):
        """Sürekli (continuous) raster listesi — bioklimatik, topografik sayısal değişkenler."""
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(6,6,6,6); v.setSpacing(4)
        note = QLabel(
            "Continuous rasters: bioclimatic variables (bio_1-bio_19), elevation, slope, "
            "NDVI, precipitation, temperature etc. "
            "File stem = variable name.  These go through VIF + correlation analysis (② Variables)."
        )
        note.setWordWrap(True); note.setStyleSheet("font-size:10px;")
        v.addWidget(note)
        self.env_list = QListWidget()
        self.env_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.env_list.setMinimumHeight(60)
        v.addWidget(self.env_list)
        br = QHBoxLayout()
        ba = QPushButton("Add Continuous Rasters…"); ba.setObjectName("btn_secondary")
        ba.clicked.connect(lambda: self._browse_rasters(self.env_list))
        br2 = QPushButton("Remove Selected"); br2.setObjectName("btn_danger")
        br2.clicked.connect(lambda: self._remove_rasters(self.env_list))
        br.addWidget(ba); br.addWidget(br2); br.addStretch()
        v.addLayout(br)
        return w

    def _build_cat_rasters(self):
        """Kategorik (categorical) raster listesi — arazi örtüsü, toprak tipi, bakı sınıfı vb."""
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(6,6,6,6); v.setSpacing(4)
        note = QLabel(
            "Categorical rasters: land cover, soil type, aspect class, geology etc. ""Values must be integer class codes (e.g. 1=forest, 2=grassland). ""These SKIP VIF/correlation analysis and are one-hot encoded before modelling. ""MaxEnt uses them as categorical features natively."
        )
        note.setWordWrap(True); note.setStyleSheet("font-size:10px;")
        v.addWidget(note)

        # Kategorik değişken listesi — her satırda yol + "integer raster" etiketi
        self.cat_list = QListWidget()
        self.cat_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.cat_list.setMinimumHeight(60)
        v.addWidget(self.cat_list)

        br = QHBoxLayout()
        ba = QPushButton("Add Categorical Rasters…"); ba.setObjectName("btn_secondary")
        ba.clicked.connect(lambda: self._browse_rasters(self.cat_list))
        br2 = QPushButton("Remove Selected"); br2.setObjectName("btn_danger")
        br2.clicked.connect(lambda: self._remove_rasters(self.cat_list))
        br.addWidget(ba); br.addWidget(br2); br.addStretch()
        v.addLayout(br)

        # Encoding seçeneği
        from PyQt6.QtWidgets import QFormLayout, QComboBox, QCheckBox
        enc_form = QFormLayout()
        enc_lbl = QLabel(
            "Encoding: Label (integer class code, single column per raster).\n"
            "e.g. land cover class 1=forest, 2=grassland → stored as 1.0, 2.0\n"
            "Tree models (RF, XGB, LightGBM, CatBoost) handle this natively.\n"
            "GLM/ANN/SVM treat these as continuous — use with caution.")
        enc_lbl.setWordWrap(True)
        enc_lbl.setStyleSheet("font-size:10px; color: palette(mid);")
        enc_form.addRow(enc_lbl)
        # Keep a dummy attribute so _run() doesn't fail
        self.cat_encoding = type("_", (), {"currentText": lambda self: "label  (integer code, 1 column per raster)"})()
        v.addLayout(enc_form)
        return w

    def _browse_occ(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Occurrence CSV", "", "CSV files (*.csv)")
        if not path:
            return
        self.occ_path.setText(path)
        self._inspect_csv(path)
        self._auto_set_output_dir(path)

    def _inspect_csv(self, path):
        """Read CSV header, update column preview, warn if >3 columns."""
        try:
            import pandas as pd
            df = pd.read_csv(path, nrows=3)
        except Exception as e:
            self._col_preview.setText(f"⚠  Could not read CSV: {e}")
            self._col_preview.setStyleSheet(
                "color:#7b2d00; background:#fdecea; border:1px solid #fc8181;"
                "border-radius:4px; padding:5px 8px; font-size:11px;")
            return

        cols = list(df.columns)
        n    = len(cols)

        if n < 3:
            self._col_preview.setText(
                f"⚠  CSV has only {n} column(s). "
                "At least 3 are required (Species · Longitude · Latitude).")
            self._col_preview.setStyleSheet(
                "color:#7b2d00; background:#fdecea; border:1px solid #fc8181;"
                "border-radius:4px; padding:5px 8px; font-size:11px;")
            return

        c1, c2, c3 = cols[0], cols[1], cols[2]

        # Update the green info banner
        preview_text = (
            f"✔  Detected columns —  "
            f"① Presence/Species: \"{c1}\"  ·  "
            f"② Longitude: \"{c2}\"  ·  "
            f"③ Latitude: \"{c3}\""
        )
        if n > 3:
            extra = cols[3:]
            preview_text += (
                f"\n⚠  {n - 3} additional column(s) will be ignored: "
                + ", ".join(f'"{c}"' for c in extra)
            )
        self._col_preview.setText(preview_text)
        self._col_preview.setStyleSheet(
            "color:#1c3328; background:#d4edda; border:1px solid #52b788;"
            "border-radius:4px; padding:5px 8px; font-size:11px;")

        # Store detected column names so _run() can pass them to DataFormatter
        self._csv_cols = (c1, c2, c3)

        # Show warning dialog only if extra columns exist
        if n > 3:
            extra_list = "\n".join(f"  • {c}" for c in extra)
            QMessageBox.information(
                self,
                "Extra Columns Detected",
                f"Your CSV has {n} columns. Only the first 3 will be used:\n\n"
                f"  ① Presence / Species name : \"{c1}\"\n"
                f"  ② Longitude               : \"{c2}\"\n"
                f"  ③ Latitude                : \"{c3}\"\n\n"
                f"The following {n - 3} column(s) will be ignored:\n"
                f"{extra_list}"
            )

    def _auto_set_output_dir(self, csv_path):
        """When the user picks a CSV, auto-create an analysis folder
        Documents/HABITUS/<species>_YYYYMMDD_HHMMSS and display its path
        in the Output Directory field."""
        if self.out_dir.text().strip():
            return  # user already set one manually
        try:
            import pandas as pd
            species = "analysis"
            try:
                df = pd.read_csv(csv_path, nrows=5)
                first_col = df.columns[0]
                values = df[first_col].dropna().astype(str)
                if len(values) > 0:
                    from collections import Counter
                    species = Counter(values).most_common(1)[0][0]
            except Exception:
                pass

            from habitus.main_dialog import SDMMainDialog
            target = SDMMainDialog._make_analysis_dir(species)
            self.out_dir.setText(target)
            # Sync into application state so screenshot button / log files
            # use the same folder immediately (even before Run Data Formatting).
            self.dlg.state["output_dir"] = target
            self.dlg.state["species_name"] = species
            self.dlg.log(f"Analysis folder auto-created: {target}")
        except Exception as e:
            self.dlg.log(f"Could not auto-create analysis folder: {e}")

    def _browse_rasters(self, list_widget):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Environmental Rasters", "",
            "Raster files (*.tif *.tiff *.asc *.img *.nc *.vrt)")
        existing = {list_widget.item(i).text()
                    for i in range(list_widget.count())}
        for p in paths:
            if p not in existing:
                list_widget.addItem(p)

    def _remove_rasters(self, list_widget):
        for item in list_widget.selectedItems():
            list_widget.takeItem(list_widget.row(item))

    def _browse_outdir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path: self.out_dir.setText(path)

    # ── Run ───────────────────────────────────────────────────────────────

    def _run(self):
        if not self.occ_path.text() or not os.path.isfile(self.occ_path.text()):
            self.dlg.show_error("Please select a valid occurrence CSV file."); return
        if self.env_list.count() == 0:
            self.dlg.show_error("Please add at least one environmental raster."); return
        if not self.out_dir.text():
            self.dlg.show_error("Please specify an output directory."); return

        env_paths = [self.env_list.item(i).text()
                     for i in range(self.env_list.count())]
        if not env_paths:
            self.dlg.show_error(
                "Please add at least one continuous environmental raster. "
                "(Categorical rasters alone are not sufficient for SDM.)"); return

        # ── Reset all downstream results if a previous run exists ─────────────
        if self.dlg.state.get("formatter") is not None:
            self.dlg.reset_all_downstream_from_data()

        self.dlg.set_progress("Loading data…", 0)

        from habitus.sdm_core import DataFormatter
        from habitus.main_dialog import WorkerThread

        cat_paths = [self.cat_list.item(i).text()
                     for i in range(self.cat_list.count())]
        cat_encoding = self.cat_encoding.currentText().split()[0]  # "one-hot"|"label"|"target"

        # Use the column names detected when the CSV was loaded;
        # fall back to positional defaults if _inspect_csv was never called.
        _csv_cols = getattr(self, "_csv_cols", None)
        if _csv_cols:
            _species_col, _lon_col, _lat_col = _csv_cols
        else:
            # Read header on-the-fly as a fallback
            try:
                import pandas as _pd
                _hdr = list(_pd.read_csv(self.occ_path.text(), nrows=0).columns)
                _species_col = _hdr[0] if len(_hdr) > 0 else "species"
                _lon_col     = _hdr[1] if len(_hdr) > 1 else "longitude"
                _lat_col     = _hdr[2] if len(_hdr) > 2 else "latitude"
            except Exception:
                _species_col, _lon_col, _lat_col = "species", "longitude", "latitude"

        params = dict(
            presence_csv     = self.occ_path.text(),
            env_rasters      = env_paths,
            cat_rasters      = cat_paths,
            cat_encoding     = cat_encoding,
            species_col      = _species_col,
            lon_col          = _lon_col,
            lat_col          = _lat_col,
            n_pa_rep         = self.n_pa_rep.value(),
            n_absences       = self.n_absences.value(),
            pa_strategy      = self.pa_strategy.currentText(),
            pa_min_dist_km   = self.pa_min_dist.value(),
            # MaxEnt background
            n_background     = self.n_background.value(),
            mx_bg_strategy   = self.mx_bg_strategy.currentText(),
            mx_min_dist_km   = self.mx_min_dist.value(),
            mx_bias_correct  = self.chk_mx_bias.isChecked(),
            # Presence-only background (ENFA / Mahalanobis)
            ponly_use_bg      = self.ponly_use_bg.isChecked(),
            ponly_n_bg        = self.ponly_n_bg.value(),
            ponly_strategy    = self.ponly_strategy.currentText(),
            ponly_min_dist_km = self.ponly_min_dist.value(),
            # MaxEnt background CSV export
            save_bg_csv       = self.chk_mx_save_csv.isChecked(),
        )

        def task(progress_cb):
            _save_bg = params.pop("save_bg_csv", False)
            _out_dir = self.out_dir.text()
            formatter = DataFormatter(
                **params, progress_callback=progress_cb)
            formatter.load_data()
            formatter.generate_pa_datasets()
            # Save MaxEnt background CSV if requested
            if _save_bg and formatter.background_X is not None and _out_dir:
                try:
                    import pandas as _pd, os as _os
                    bg_df = formatter.background_X.copy()
                    if formatter.background_coords:
                        bg_df.insert(0, "latitude",
                            formatter.background_coords.get("lat", []))
                        bg_df.insert(0, "longitude",
                            formatter.background_coords.get("lon", []))
                    out_path = _os.path.join(_out_dir, "background_maxent.csv")
                    bg_df.to_csv(out_path, index=False)
                    progress_cb(f"Saved: {out_path}", 49)
                except Exception as _e:
                    progress_cb(f"Background CSV save failed: {_e}", 49)
            return formatter

        self._worker = WorkerThread(task)
        self._worker.progress.connect(self.dlg.set_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(
            lambda e: self.dlg.show_error(f"Data formatting failed:\n{e}"))
        self._worker.start()

    def _on_done(self, formatter):
        self.dlg.state["formatter"]    = formatter
        self.dlg.state["pa_datasets"]  = formatter.pa_datasets
        self.dlg.state["var_names"]    = formatter.var_names
        self.dlg.state["output_dir"]   = self.out_dir.text()
        self.dlg.state["species_name"] = getattr(formatter, "species_name", "")

        dropped  = getattr(formatter, "dropped_points", [])
        n_orig   = len(formatter.occ_df)
        n_kept   = n_orig - len(dropped)
        n_rep    = len(formatter.pa_datasets)
        n_bg     = (len(formatter.background_X)
                    if getattr(formatter, "background_X", None) is not None else 0)
        n_cat    = len(getattr(formatter, "cat_var_names", []))

        # ── If any points were dropped show a warning first ───────────────────
        if dropped:
            dup_section    = [p for p in dropped if p["reason"] == "duplicate coordinate"]
            out_section    = [p for p in dropped if p["reason"] == "outside raster extent"]
            nodata_section = [p for p in dropped if p["reason"] == "falls on NoData cell"]

            warn_lines = [
                f"⚠  {len(dropped)} of {n_orig} occurrence point(s) were excluded "
                f"before modelling:\n"
            ]
            if dup_section:
                warn_lines.append(
                    f"  Duplicate coordinates ({len(dup_section)} point(s)):")
                for p in dup_section:
                    warn_lines.append(
                        f"    • lon={p['lon']:.5f}, lat={p['lat']:.5f}")
            if out_section:
                warn_lines.append(
                    f"\n  Outside raster extent ({len(out_section)} point(s)):")
                for p in out_section:
                    warn_lines.append(
                        f"    • lon={p['lon']:.5f}, lat={p['lat']:.5f}")
            if nodata_section:
                warn_lines.append(
                    f"\n  Falls on NoData cell ({len(nodata_section)} point(s)):")
                for p in nodata_section:
                    warn_lines.append(
                        f"    • lon={p['lon']:.5f}, lat={p['lat']:.5f}")

            warn_lines.append(
                f"\n✔  {n_kept} valid point(s) will be used for modelling.\n\n"
                "Tip: verify that your occurrence CSV and rasters share the "
                "same coordinate reference system (CRS).")
            QMessageBox.warning(self, "Invalid Occurrence Points Detected",
                                "\n".join(warn_lines))
            self.dlg.log("\n".join(warn_lines))

        # ── Summary info dialog ───────────────────────────────────────────────
        drop_note = (f"  Excluded points    : {len(dropped)} "
                     f"(outside extent or NoData)\n") if dropped else ""
        msg = (
            f"Data ready!\n\n"
            f"  Presences (used)   : {n_kept}"
            + (f"  /  {n_orig} loaded" if dropped else "") + "\n"
            + drop_note +
            f"  PA sets (ML)       : {n_rep} × {self.n_absences.value()} = "
            f"{n_rep * self.n_absences.value()} pseudo-absences\n"
            f"  Background (MaxEnt): {n_bg} points\n"
            f"  Continuous vars    : {', '.join(formatter.var_names)}\n"
            + (f"  Categorical vars   : {', '.join(formatter.cat_var_names)}"
               if n_cat else "")
        )
        self.dlg.set_progress(
            f"Ready: {n_kept} presences, {n_rep} PA sets, "
            f"{len(formatter.var_names)} cont + {n_cat} cat vars", 100)
        self.dlg.unlock_tab(self.dlg.TAB_VIF)
        self.dlg.goto_tab(self.dlg.TAB_VIF)
        self.dlg.show_info(msg)
