# -*- coding: utf-8 -*-
"""
Tab ⑤ – Projection
Fixes:
  1. Rasterlar POZISYON bazlı eşlenir (dosya adı değil sıra önemli)
  2. Sadece seçili algoritmalar projekte edilir
  3. "Current" için eğitim rasterları otomatik doldurulur
  4. Tamamlanınca EMca + EMwmean prob haritaları QGIS'e otomatik yüklenir
  5. Değişken sırası ve sayısı uyumsuzsa açık hata mesajı verilir
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLineEdit, QListWidget, QAbstractItemView,
    QGroupBox, QLabel, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox,
    QCheckBox, QComboBox, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from habitus.map_widget import RasterMapWidget


_ENS_DISPLAY = {"wmean": "Weighted Mean", "ca": "Committee Averaging"}
_TYPE_DISPLAY = {"prob": "Probability", "bin": "Binary"}

def _make_future_label(key: str, scenario: str, gcm: str) -> str:
    """Full map title for future projections (shown in map header)."""
    body, _, suffix = key.rpartition("_")
    if not body:
        return f"Future Distribution  ·  {key}"
    type_str = _TYPE_DISPLAY.get(suffix, suffix)
    gcm_part = f"  ·  {gcm}" if gcm else ""
    if body.startswith("EM"):
        ens = _ENS_DISPLAY.get(body[2:], body[2:])
        return f"Future Distribution{gcm_part}  ·  {scenario}  ·  Ensemble: {ens}  ·  {type_str}"
    if "_PA" in body:
        algo, pa = body.rsplit("_PA", 1)
        return f"Future Distribution{gcm_part}  ·  {scenario}  ·  {algo}  ·  PA-{pa}  ·  {type_str}"
    return f"Future Distribution{gcm_part}  ·  {scenario}  ·  {body}  ·  {type_str}"


def _make_future_short_label(key: str) -> str:
    """Short combo label: Algorithm · PA# · Prob/Bin."""
    _ENS_SHORT = {"wmean": "WMean", "ca": "CommAvg"}
    body, _, suffix = key.rpartition("_")
    type_str = "Prob" if suffix == "prob" else "Bin"
    if not body:
        return f"{key} · {type_str}"
    if body.startswith("EM"):
        ens = _ENS_SHORT.get(body[2:], body[2:])
        return f"Ensemble {ens} · {type_str}"
    if "_PA" in body:
        algo, pa = body.rsplit("_PA", 1)
        return f"{algo} · PA{pa} · {type_str}"
    return f"{body} · {type_str}"


# ── Tab ───────────────────────────────────────────────────────────────────────

class ProjectionTab(QWidget):

    def __init__(self, main_dialog):
        super().__init__()
        self.dlg = main_dialog
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Bilgi banner ──
        self._banner = QLabel("")
        self._banner.setWordWrap(True)
        self._banner.setStyleSheet(
            "background:#0d2218;color:#74c69d;padding:8px;"
            "border-radius:5px;border:1px solid #2d6a4f;font-size:11px;")
        layout.addWidget(self._banner)

        # ── Senaryo adı ──
        scen_group  = QGroupBox("Projection Scenario")
        scen_layout = QFormLayout(scen_group)
        scen_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        scen_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        scen_layout.setHorizontalSpacing(12)
        scen_layout.setVerticalSpacing(6)
        self.proj_name = QLineEdit("2050_SSP245")
        self.proj_name.setPlaceholderText("e.g. 2050_SSP245, 2070_BC45, 2080_RCP85…")
        scen_layout.addRow("Scenario name:", self.proj_name)

        self.gcm_model = QLineEdit()
        self.gcm_model.setPlaceholderText("e.g. CNRM-ESM2-1, MPI-ESM1-2-HR, UKESM1-0-LL…")
        scen_layout.addRow("GCM model:", self.gcm_model)
        layout.addWidget(scen_group)

        # ── Algoritma seçimi ──
        algo_group  = QGroupBox("Algorithms to Project")
        algo_layout = QVBoxLayout(algo_group)
        self._algo_note = QLabel(
            "Select which algorithms to project. "
            "Only algorithms trained in ③ Models are available.")
        self._algo_note.setStyleSheet("color:#74c69d;font-size:10px;")
        self._algo_note.setWordWrap(True)
        algo_layout.addWidget(self._algo_note)

        self._algo_checks = {}   # populated in showEvent
        self._algo_box = QWidget()
        self._algo_box_layout = QHBoxLayout(self._algo_box)
        self._algo_box_layout.setContentsMargins(0,0,0,0)
        algo_layout.addWidget(self._algo_box)

        btn_algo_row = QHBoxLayout()
        btn_all  = QPushButton("All");   btn_all.setObjectName("btn_secondary")
        btn_none = QPushButton("None");  btn_none.setObjectName("btn_danger")
        btn_all.clicked.connect(lambda: [c.setChecked(True)  for c in self._algo_checks.values()])
        btn_none.clicked.connect(lambda: [c.setChecked(False) for c in self._algo_checks.values()])
        btn_algo_row.addWidget(btn_all); btn_algo_row.addWidget(btn_none); btn_algo_row.addStretch()
        algo_layout.addLayout(btn_algo_row)
        layout.addWidget(algo_group)

        # ── Raster listesi ──
        rast_group  = QGroupBox("Environmental Rasters for This Scenario")
        rast_layout = QVBoxLayout(rast_group)

        self._rast_hint = QLabel("")
        self._rast_hint.setWordWrap(True)
        self._rast_hint.setStyleSheet("color:#f6ad55;font-size:11px;")
        rast_layout.addWidget(self._rast_hint)

        self.rast_list = QListWidget()
        self.rast_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.rast_list.setMinimumHeight(80)
        rast_layout.addWidget(self.rast_list)

        btn_row = QHBoxLayout()

        btn_folder = QPushButton("Browse Folder…"); btn_folder.setObjectName("btn_primary")
        btn_folder.setToolTip(
            "Select a folder — Habitus will automatically find and list "
            "the rasters matching the model variables.")
        btn_folder.clicked.connect(self._browse_folder)

        btn_add = QPushButton("Add Files…"); btn_add.setObjectName("btn_secondary")
        btn_add.clicked.connect(self._browse_rasters)
        btn_rem = QPushButton("Remove"); btn_rem.setObjectName("btn_danger")
        btn_rem.clicked.connect(self._remove_selected)

        btn_rem_all = QPushButton("Remove All"); btn_rem_all.setObjectName("btn_danger")
        btn_rem_all.setToolTip(
            "Clear all rasters and reset projection results.")
        btn_rem_all.clicked.connect(self._remove_all_and_reset)

        btn_row.addWidget(btn_folder)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_rem)
        btn_row.addWidget(btn_rem_all)
        btn_row.addStretch()
        rast_layout.addLayout(btn_row)
        layout.addWidget(rast_group)

        # ── Output & opsiyon ──
        out_group  = QGroupBox("Output Settings")
        out_layout = QFormLayout(out_group)
        out_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        out_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        out_layout.setHorizontalSpacing(12)
        out_layout.setVerticalSpacing(6)
        self.out_subdir = QLineEdit()
        self.out_subdir.setPlaceholderText("Auto-named from scenario (leave empty)")
        self.chk_auto_load = QCheckBox(
            "Auto-display ensemble probability maps when done")
        self.chk_auto_load.setChecked(True)
        self.chk_load_binary = QCheckBox("Also display binary (presence/absence) maps")
        self.chk_load_binary.setChecked(False)
        out_layout.addRow("Output subdir:", self.out_subdir)
        out_layout.addRow("", self.chk_auto_load)
        out_layout.addRow("", self.chk_load_binary)
        layout.addWidget(out_group)

        # ── Tamamlanan projeksiyonlar tablosu ──
        done_group  = QGroupBox("Completed Projections")
        done_layout = QVBoxLayout(done_group)
        self.done_table = QTableWidget(0, 4)
        self.done_table.setHorizontalHeaderLabels(
            ["Scenario", "Layer", "Type", "File"])
        hdr = self.done_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.done_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.done_table.setAlternatingRowColors(True)
        self.done_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        done_layout.addWidget(self.done_table)

        btn_load_sel = QPushButton("Display Selected Map")
        btn_load_sel.setObjectName("btn_secondary")
        btn_load_sel.clicked.connect(self._load_selected_to_qgis)
        done_layout.addWidget(btn_load_sel)
        layout.addWidget(done_group)

        # ── Embedded map viewer ──
        from PyQt6.QtWidgets import QGroupBox as _GB
        map_view_grp = _GB("Projection Map Viewer")
        map_view_layout = QVBoxLayout(map_view_grp)
        self.map_viewer = RasterMapWidget()
        self.map_viewer.setMinimumHeight(380)
        map_view_layout.addWidget(self.map_viewer)
        layout.addWidget(map_view_grp, 1)

        btn_run = QPushButton("▶  Run Projection")
        btn_run.clicked.connect(self._run)
        layout.addWidget(btn_run)

    # ── showEvent: algoritma checkbox'larını modelden doldur ─────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_algo_checks()
        self._update_banner()

    def _refresh_algo_checks(self):
        modeler = self.dlg.state.get("modeler")
        if not modeler:
            return
        algos = sorted(set(k[0] for k in modeler.fitted_models))
        # Mevcut checkbox'lar ile aynıysa tekrar oluşturma
        if set(self._algo_checks.keys()) == set(algos):
            return
        # Temizle
        for i in reversed(range(self._algo_box_layout.count())):
            w = self._algo_box_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        self._algo_checks = {}
        for algo in algos:
            chk = QCheckBox(algo)
            chk.setChecked(True)
            self._algo_box_layout.addWidget(chk)
            self._algo_checks[algo] = chk
        self._algo_box_layout.addStretch()

    def _update_banner(self):
        var_names = self.dlg.state.get("var_names") or []
        formatter = self.dlg.state.get("formatter")
        import os as _os
        n_vars = len(var_names)
        n_matched = 0
        if formatter and hasattr(formatter, 'env_rasters'):
            stems = {_os.path.splitext(_os.path.basename(p))[0]
                     for p in formatter.env_rasters}
            n_matched = sum(1 for v in var_names if v in stems)

        cat_names = getattr(formatter, "cat_var_names", []) if formatter else []

        if var_names:
            match_note = (
                f"All {n_vars} selected variables have matching rasters."
                if n_matched == n_vars
                else f"Warning: only {n_matched}/{n_vars} variables matched."
            )
            cat_note = ""
            if cat_names:
                cat_note = (
                    f"\nCategorical variables ({', '.join(cat_names)}) are reused from "
                    f"current data automatically — do NOT add them here."
                )
            self._banner.setText(
                f"Model uses {n_vars} continuous variables: {', '.join(var_names)}\n"
                f"⚠ Raster ORDER matters: add files in the same variable order as selected in Tab ②.\n"
                f"{match_note}  Use 'Auto-fill' for current climate scenarios."
                f"{cat_note}"
            )
            self._rast_hint.setText(
                f"Required: {n_vars} continuous rasters in order → "
                + "  |  ".join(f"[{i+1}] {v}" for i, v in enumerate(var_names))
            )
        else:
            self._banner.setText("Complete ① Data and ② Variables steps first.")

    # ── Raster panel helpers ──────────────────────────────────────────────────

    def _autofill_rasters(self):
        """Eğitimde kullanılan rasterları (var_names sırasına göre) otomatik doldur."""
        formatter = self.dlg.state.get("formatter")
        var_names = self.dlg.state.get("var_names") or []
        if not formatter or not hasattr(formatter, "env_rasters"):
            self.dlg.show_error(
                "Training rasters not found. "
                "Please complete ① Data step first."); return
        if not var_names:
            self.dlg.show_error(
                "Variable list is empty. "
                "Complete ② Variables step first."); return

        # formatter.env_rasters listesindeki rasterları var_names sırasına göre eşle
        # env_data dict'indeki sıra var_names ile aynı
        env_rasters = formatter.env_rasters   # orijinal raster yolları listesi
        import re as _re
        def _san(name):
            s = _re.sub(r"[ \(\)\-\.]+", "_", str(name))
            s = _re.sub(r"_+", "_", s)
            return s.strip("_") or "var"
        stem_to_path = {_san(os.path.splitext(os.path.basename(p))[0]): p
                        for p in env_rasters}

        self.rast_list.clear()
        found, missing = [], []
        for vname in var_names:
            if vname in stem_to_path:
                found.append(stem_to_path[vname])
            else:
                missing.append(vname)

        if missing:
            self.dlg.show_error(
                f"Could not match rasters for: {', '.join(missing)}\n"
                f"Available stems: {', '.join(stem_to_path.keys())}\n\n"
                f"Please add rasters manually in the correct order.")
            return

        for p in found:
            self.rast_list.addItem(p)
        self.proj_name.setText("current")
        self.dlg.log(
            f"Auto-filled {len(found)} training rasters for current climate projection.")

    def _browse_folder(self):
        """Select a folder and auto-match rasters to model variable names."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder Containing Future Climate Rasters", "")
        if not folder:
            return

        var_names = self.dlg.state.get("var_names") or []
        formatter = self.dlg.state.get("formatter")
        if formatter and getattr(formatter, "cat_var_names", []):
            var_names = [v for v in var_names if v not in formatter.cat_var_names]

        if not var_names:
            self.dlg.show_error(
                "Variable list is empty. Complete ② Variables step first.")
            return

        import re as _re
        _RAST_EXTS = {".tif", ".tiff", ".asc", ".img", ".nc", ".vrt"}

        def _san(name):
            s = _re.sub(r"[ \(\)\-\.]+", "_", str(name))
            return _re.sub(r"_+", "_", s).strip("_").lower()

        # Collect all raster files in folder
        candidates = {}
        for fname in os.listdir(folder):
            ext = os.path.splitext(fname)[1].lower()
            if ext in _RAST_EXTS:
                stem_san = _san(os.path.splitext(fname)[0])
                candidates[stem_san] = os.path.join(folder, fname)

        # Match each var_name: exact → prefix → contains
        self.rast_list.clear()
        found, missing = [], []
        for vname in var_names:
            vsan = _san(vname)
            match = None
            # 1) exact
            if vsan in candidates:
                match = candidates[vsan]
            else:
                # 2) prefix: file stem starts with var name
                for stem, path in candidates.items():
                    if stem.startswith(vsan):
                        match = path; break
                if match is None:
                    # 3) contains: var name anywhere in stem
                    for stem, path in candidates.items():
                        if vsan in stem:
                            match = path; break
            if match:
                found.append((vname, match))
            else:
                missing.append(vname)

        for vname, path in found:
            self.rast_list.addItem(path)

        if missing:
            QMessageBox.warning(
                self, "Unmatched Variables",
                f"Could not find rasters for {len(missing)} variable(s):\n"
                + "\n".join(f"  • {v}" for v in missing)
                + f"\n\nPlease add these manually via 'Add Files…'")
        else:
            self.dlg.log(
                f"Auto-matched {len(found)} raster(s) from folder: {folder}")

    def _browse_rasters(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Environmental Rasters", "",
            "Raster files (*.tif *.tiff *.asc *.img *.nc *.vrt)"
        )
        for p in paths:
            self.rast_list.addItem(p)

    def _remove_selected(self):
        for item in self.rast_list.selectedItems():
            self.rast_list.takeItem(self.rast_list.row(item))

    def _remove_all_and_reset(self):
        if self.rast_list.count() == 0 and not self.dlg.state.get("projections"):
            return
        reply = QMessageBox.question(
            self, "Remove All & Reset",
            "This will clear all rasters and reset all projection results.\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        # Clear raster list
        self.rast_list.clear()
        # Reset projection state
        self.dlg.state["projections"] = {}
        self.dlg.state["range_results"] = {}
        # Clear this tab's UI
        self.map_viewer.clear_all()
        self.done_table.setRowCount(0)
        # Clear range tab UI
        tab_range = self.dlg.tab_range
        tab_range.map_viewer.clear_all()
        tab_range.stats_table.setRowCount(0)
        # Lock range tab
        self.dlg.tabs.setTabEnabled(self.dlg.TAB_RANGE, False)
        self.dlg.log("Projection results reset.")

    # ── Run ──────────────────────────────────────────────────────────────────

    def _run(self):
        modeler  = self.dlg.state.get("modeler")
        ensemble = self.dlg.state.get("ensemble")
        var_names = self.dlg.state.get("var_names") or []

        if modeler is None or ensemble is None:
            self.dlg.show_error(
                "Complete model fitting (③ Models) and ensemble (④ Ensemble) steps first.")
            return

        proj_name = self.proj_name.text().strip() or "current"

        rasters = [self.rast_list.item(i).text()
                   for i in range(self.rast_list.count())]
        if not rasters:
            self.dlg.show_error(
                "No rasters added.\n"
                "Use 'Auto-fill from Training' for current climate, "
                "or add rasters manually for future scenarios."); return

        # Sayı kontrolü — only continuous variables need rasters;
        # categorical variables (Aspect, Slope, NDVI, CORINE etc.) are reused
        # from the current (training) dataset automatically.
        cont_var_names = var_names  # var_names from VIF = continuous only
        formatter = self.dlg.state.get("formatter")
        if formatter and getattr(formatter, "cat_var_names", []):
            cat_names = formatter.cat_var_names
            # If user accidentally included cat vars, filter them out
            cont_var_names = [v for v in var_names if v not in cat_names]

        if len(rasters) != len(cont_var_names):
            self.dlg.show_error(
                f"Raster count mismatch!\n\n"
                f"Model expects {len(cont_var_names)} continuous rasters:\n"
                f"  {', '.join(cont_var_names)}\n\n"
                f"You added {len(rasters)} rasters.\n\n"
                f"Categorical variables ({', '.join(getattr(formatter, 'cat_var_names', []))}) "
                f"are reused from current data automatically — do NOT include them.\n\n"
                f"Rasters must be in the same ORDER as the variables above.")
            return

        # Seçili algoritmalar
        selected_algos = [k for k, chk in self._algo_checks.items()
                          if chk.isChecked()]
        if not selected_algos:
            self.dlg.show_error("Select at least one algorithm to project.")
            return

        base_dir = self.dlg.state.get("output_dir", ".")
        sub      = self.out_subdir.text().strip() or proj_name
        out_dir  = os.path.join(base_dir, sub)

        self.dlg.set_progress(
            f"Starting projection '{proj_name}' "
            f"({', '.join(selected_algos)})…", 0)

        from habitus.sdm_core import Projector
        from habitus.main_dialog import WorkerThread

        projector = Projector(
            modeler          = modeler,
            ensemble_modeler = ensemble,
            progress_callback= self.dlg.set_progress,
            formatter        = self.dlg.state.get("formatter"),
        )

        _algos = selected_algos[:]   # closure için kopya

        def task(progress_cb):
            return proj_name, projector.project(
                raster_paths        = rasters,
                proj_name           = proj_name,
                output_dir          = out_dir,
                progress_cb         = progress_cb,
                selected_algorithms = _algos,
            )

        self._worker = WorkerThread(task)
        self._worker.progress.connect(self.dlg.set_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(
            lambda e: self.dlg.show_error(f"Projection failed:\n{e}"))
        self._worker.start()

    # ── Tamamlandı ───────────────────────────────────────────────────────────

    def _on_done(self, result):
        proj_name, output_files = result
        self.dlg.state["projections"][proj_name] = output_files

        # Tabloyu doldur
        type_map = {"prob": "Probability (0–1)", "bin": "Binary (0/1)"}
        for key, fpath in output_files.items():
            r = self.done_table.rowCount()
            self.done_table.insertRow(r)
            # Scenario
            self.done_table.setItem(r, 0, QTableWidgetItem(proj_name))
            # Layer name (algo+pa or EM name)
            self.done_table.setItem(r, 1, QTableWidgetItem(key.rsplit("_", 1)[0]))
            # Type (prob/bin)
            suffix = key.rsplit("_", 1)[-1]
            type_item = QTableWidgetItem(type_map.get(suffix, suffix))
            if suffix == "prob":
                type_item.setForeground(QColor("#63b3ed"))
            else:
                type_item.setForeground(QColor("#68d391"))
            self.done_table.setItem(r, 2, type_item)
            # File path
            self.done_table.setItem(r, 3, QTableWidgetItem(fpath))

        n = len(output_files)
        self.dlg.set_progress(
            f"Projection '{proj_name}' complete — {n} rasters saved.", 100)

        # Auto-load ensemble maps
        if self.chk_auto_load.isChecked():
            self._autoload_ensemble(proj_name, output_files)

        self.dlg.unlock_tab(self.dlg.TAB_RANGE)
        self.dlg.unlock_tab(self.dlg.TAB_EVALUATION)

    def _autoload_ensemble(self, proj_name, output_files):
        """Clear viewer and display new projection maps."""
        self.map_viewer.clear_all()
        loaded = []
        for key, fpath in output_files.items():
            is_prob = key.endswith("_prob")
            is_bin  = key.endswith("_bin")

            if is_bin and not self.chk_load_binary.isChecked():
                continue
            if not is_prob and not is_bin:
                continue
            if not os.path.isfile(fpath):
                continue

            gcm = self.gcm_model.text().strip()
            layer_name = _make_future_label(key, proj_name, gcm)
            short_name = _make_future_short_label(key)
            style = "suitability" if is_prob else "binary"
            self.map_viewer.load_raster(fpath, layer_name, style,
                                        display_name=short_name)
            loaded.append(layer_name)

        if loaded:
            self.dlg.log(
                f"Auto-displayed {len(loaded)} ensemble map(s): "
                + ", ".join(loaded))
        else:
            self.dlg.log(
                "No ensemble maps displayed "
                "(check that ensemble step completed).")

    # ── Manuel yükleme ───────────────────────────────────────────────────────

    def _load_selected_to_qgis(self):
        rows_done = set()
        for item in self.done_table.selectedItems():
            row = item.row()
            if row in rows_done:
                continue
            rows_done.add(row)

            key   = self.done_table.item(row, 1).text()
            suf   = self.done_table.item(row, 2).text()
            fpath = self.done_table.item(row, 3).text()
            scen  = self.done_table.item(row, 0).text()

            if not os.path.isfile(fpath):
                self.dlg.show_error(f"File not found:\n{fpath}")
                continue

            gcm = self.gcm_model.text().strip()
            layer_name = _make_future_label(key, scen, gcm)
            short_name = _make_future_short_label(
                key + ("_prob" if "Probability" in suf else "_bin"))
            style = "suitability" if "Probability" in suf else "binary"
            self.map_viewer.load_raster(fpath, layer_name, style,
                                        display_name=short_name)
            self.dlg.log(f"Loaded: {layer_name}")
