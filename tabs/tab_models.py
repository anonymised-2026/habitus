# -*- coding: utf-8 -*-
"""
Tab ③ – Models + Current Distribution Map

Workflow (all in one tab):
  1. Select algorithms & options
  2. Run individual models (cross-validation + evaluation)
  3. Automatically project onto CURRENT climate rasters → map loaded into QGIS
  4. Simple ensemble combining (no biomod2 jargon)

The "current map" is produced immediately after fitting — no separate step needed.
"""

import os
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox,
    QGroupBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QComboBox, QLineEdit,
    QTabWidget, QSizePolicy, QFileDialog, QScrollArea, QFrame,
    QRadioButton, QButtonGroup, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette

from habitus.map_widget import RasterMapWidget


_ENS_DISPLAY = {"wmean": "Weighted Mean", "ca": "Committee Averaging"}
_TYPE_DISPLAY = {"prob": "Probability", "bin": "Binary"}

def _make_current_label(key: str) -> str:
    """Convert raw key like 'Maxent_PA1_prob' → readable map title."""
    body, _, suffix = key.rpartition("_")
    if not body:
        return f"Current Distribution  ·  {key}"
    type_str = _TYPE_DISPLAY.get(suffix, suffix)
    if body.startswith("EM"):
        ens = _ENS_DISPLAY.get(body[2:], body[2:])
        return f"Current Distribution  ·  Ensemble: {ens}  ·  {type_str}"
    if "_PA" in body:
        algo, pa = body.rsplit("_PA", 1)
        return f"Current Distribution  ·  {algo}  ·  PA-{pa}  ·  {type_str}"
    return f"Current Distribution  ·  {body}  ·  {type_str}"


def _theme_fg(role: str):
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QColor, QPalette
    bg = QApplication.instance().palette().color(QPalette.ColorRole.Window)
    dark = bg.lightness() < 128
    table = {
        "ok":      ("#52b788", "#1a7a4a"),
        "warn":    ("#f6ad55", "#b45309"),
        "bad":     ("#fc8181", "#c0392b"),
        "neutral": ("#74c69d", "#0e6655"),
    }
    d, l = table.get(role, ("#888888", "#444444"))
    return QColor(d if dark else l)




class ModelsTab(QWidget):

    def __init__(self, main_dialog):
        super().__init__()
        self.dlg = main_dialog
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Sub-tabs: Algorithms | Results | Current Map ──────────────────
        self.sub = QTabWidget(); self.sub.setObjectName("sdm_tabs")
        layout.addWidget(self.sub, 1)

        self.sub.addTab(self._build_algo_tab(),    "Algorithm Settings")
        self.sub.addTab(self._build_results_tab(), "Evaluation Results")
        self.sub.addTab(self._build_map_tab(),     "Current Distribution Map")

        btn_run = QPushButton("▶  Run Models + Generate Current Distribution Map")
        btn_run.clicked.connect(self._run)
        layout.addWidget(btn_run)

    # ── Sub-tab 1: Algorithm settings ─────────────────────────────────────

    def _build_algo_tab(self):
        outer = QWidget(); ov = QVBoxLayout(outer)
        ov.setContentsMargins(0,0,0,0); ov.setSpacing(0)
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.Shape.NoFrame)
        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(6); v.setContentsMargins(6,6,6,6)

        split = QHBoxLayout()

        # Algorithm checkboxes
        ag = QGroupBox("Select Algorithms"); al = QVBoxLayout(ag); al.setSpacing(5)
        self._algo_checks = {}
        for key, label, default in [
            ("GLM",    "GLM      – Generalised Linear Model",      True),
            ("GBM",    "GBM      – Gradient Boosting (sklearn)",   False),
            ("BRT",    "BRT      – Boosted Regression Trees",      False),
            ("RF",     "RF       – Random Forest",                 True),
            ("SVM",    "SVM      – Support Vector Machine  (kernel, auto-scaled)",  False),
            ("ANN",    "ANN      – Neural Network (MLP)",          False),
            ("XGB",    "XGBoost  – Extreme Gradient Boosting",     False),
            ("LGB",    "LightGBM – Light Gradient Boosting",       False),
            ("CAT",    "CatBoost – Categorical Boosting",          False),
            ("GAM",    "GAM      – Generalised Additive Model",    False),
            ("MAXENT", "MaxEnt   – Maximum Entropy  (presence-only, background points)", False),
            ("ENFA",   "ENFA     – Ecol. Niche Factor Analysis (presence-only)",   False),
            ("MAHAL",  "Mahalanobis – Distance-Based Niche (presence-only)",       False),
        ]:
            chk = QCheckBox(label); chk.setChecked(default)
            al.addWidget(chk); self._algo_checks[key] = chk

        # Disable checkboxes whose required package is not installed.
        from habitus.sdm_core import ALGORITHM_INFO
        _install_hints = {
            "GAM":    "pip install pygam",
            "MAXENT": "pip install elapid",
            "XGB":    "pip install xgboost",
            "LGB":    "pip install lightgbm",
            "CAT":    "pip install catboost",
        }
        for key, chk in self._algo_checks.items():
            info = ALGORITHM_INFO.get(key, {})
            if not info.get("available", True):
                chk.setChecked(False)
                chk.setEnabled(False)
                hint = _install_hints.get(key, "")
                chk.setToolTip(f"Not installed — {hint}" if hint else "Not installed")
                chk.setText(chk.text() + "  [not installed]")
        al.addStretch()
        split.addWidget(ag, 2)

        # Algorithm options
        og = QGroupBox("Algorithm Options"); ol = QVBoxLayout(og)
        self.opts_tabs = QTabWidget(); self.opts_tabs.setObjectName("sdm_tabs")
        self.opts_tabs.addTab(self._glm_opts(), "GLM")
        self.opts_tabs.addTab(self._gbm_opts(), "GBM")
        self.opts_tabs.addTab(self._brt_opts(), "BRT")
        self.opts_tabs.addTab(self._rf_opts(),  "RF")
        self.opts_tabs.addTab(self._svm_opts(), "SVM")
        self.opts_tabs.addTab(self._ann_opts(), "ANN")
        self.opts_tabs.addTab(self._xgb_opts(), "XGBoost")
        self.opts_tabs.addTab(self._lgb_opts(), "LightGBM")
        self.opts_tabs.addTab(self._cat_opts(), "CatBoost")
        self.opts_tabs.addTab(self._gam_opts(),   "GAM")
        self.opts_tabs.addTab(self._mx_opts(),    "MaxEnt")
        self.opts_tabs.addTab(self._enfa_opts(),  "ENFA")
        self.opts_tabs.addTab(self._mahal_opts(), "Mahalanobis")
        ol.addWidget(self.opts_tabs)
        split.addWidget(og, 3)
        v.addLayout(split)

        # CV settings
        cg = QGroupBox("Training Settings"); cf = QFormLayout(cg)
        cf.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        cf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        cf.setHorizontalSpacing(12)
        cf.setVerticalSpacing(6)
        self.n_cv    = QSpinBox(); self.n_cv.setRange(1,10); self.n_cv.setValue(2)
        self.n_cv.setToolTip("Number of cross-validation runs per algorithm")
        self.v_imp   = QSpinBox(); self.v_imp.setRange(0,10); self.v_imp.setValue(3)
        self.v_imp.setToolTip("Permutation repetitions for variable importance")

        # ── Test data mode ───────────────────────────────────────────────
        self._rdo_random   = QRadioButton("Random split")
        self._rdo_external = QRadioButton("External test points (CSV)")
        self._rdo_random.setChecked(True)
        self._split_grp = QButtonGroup(self)
        self._split_grp.addButton(self._rdo_random,   0)
        self._split_grp.addButton(self._rdo_external, 1)

        self.split = QSpinBox()
        self.split.setRange(50, 95); self.split.setValue(80); self.split.setSuffix(" %")
        self.split.setToolTip("% of occurrence data used for training; remainder used as test set")

        self._test_csv_edit = QLineEdit()
        self._test_csv_edit.setPlaceholderText("Select external test occurrence CSV…")
        self._test_csv_edit.setEnabled(False)
        self._btn_test_csv = QPushButton("Browse…")
        self._btn_test_csv.setObjectName("btn_secondary")
        self._btn_test_csv.setEnabled(False)
        self._btn_test_csv.clicked.connect(self._browse_test_csv)

        self._rdo_random.toggled.connect(self._on_test_mode_changed)

        rdo_row = QHBoxLayout()
        rdo_row.addWidget(self._rdo_random)
        rdo_row.addWidget(self._rdo_external)
        rdo_row.addStretch()

        test_csv_row = QHBoxLayout()
        test_csv_row.addWidget(self._test_csv_edit)
        test_csv_row.addWidget(self._btn_test_csv)

        cf.addRow("Cross-validation runs:", self.n_cv)
        cf.addRow("Test data source:", rdo_row)
        cf.addRow("Training data %:", self.split)
        cf.addRow("External test CSV:", test_csv_row)
        cf.addRow("Variable importance reps:", self.v_imp)
        v.addWidget(cg)

        # Ensemble combining options
        eg = QGroupBox("Combining Results & Binary Threshold Method"); ef = QFormLayout(eg)
        ef.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        ef.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        ef.setHorizontalSpacing(12)
        ef.setVerticalSpacing(6)
        ef.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        ef.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        ef.setHorizontalSpacing(12)
        ef.setVerticalSpacing(6)
        note = QLabel(
            "After fitting, individual model predictions are combined into one map.\n"
            "Committee Averaging = majority vote (binary).  "
            "Weighted Mean = weighted probability average.")
        note.setWordWrap(True); note.setStyleSheet("font-size:10px;")
        self.ens_method = QComboBox()
        self.ens_method.addItems([
            "Weighted Mean (recommended – weights by evaluation score)",
            "Committee Averaging (majority vote)",
            "Both",
        ])
        self.ens_metric = QComboBox(); self.ens_metric.addItems(["TSS","ROC","Boyce"])
        self.ens_thr    = QDoubleSpinBox(); self.ens_thr.setRange(0,1); self.ens_thr.setValue(0.6)
        self.ens_thr.setDecimals(2); self.ens_thr.setSingleStep(0.05)
        self.ens_thr.setToolTip(
            "Minimum score threshold: models below this score are excluded from the combined map")

        self.bin_thr_method = QComboBox()
        self.bin_thr_method.addItems([
            "max_tss       – Maximise TSS (Allouche 2006)  [default]",
            "max_kappa     – Maximise Cohen's Kappa",
            "sens_spec_eq  – Equal sensitivity & specificity (Liu 2005)",
            "p10           – 10th percentile of presence predictions (Pearson 2007)",
            "min_roi       – Min distance to perfect ROC point",
        ])
        self.bin_thr_method.setToolTip(
            "Statistical method for converting probability maps to binary presence/absence.\n"
            "max_tss: best for most SDM applications (prevalence-independent).\n"
            "p10: recommended for MaxEnt (minimal predicted area).\n"
            "sens_spec_eq: when commission and omission errors are equally important.")

        ef.addRow(note)
        ef.addRow("Combining method:", self.ens_method)
        ef.addRow("Score metric:", self.ens_metric)
        ef.addRow("Min score to include model:", self.ens_thr)
        ef.addRow("Binary threshold method:", self.bin_thr_method)
        v.addWidget(eg)
        sa.setWidget(w); ov.addWidget(sa)
        return outer

    # ── Sub-tab 2: Evaluation results ─────────────────────────────────────

    def _build_results_tab(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(8,8,8,8)
        lbl = QLabel(
            "ROC-AUC: discrimination ability (0.5=random, 1.0=perfect)\n"
            "TSS: true skill statistic (0=random, 1=perfect, <0=worse than random)\n"
            "Boyce: continuous Boyce index (>0.5=good, ~0=random, <0=counter-useful)")
        lbl.setStyleSheet("font-size:10px;"); lbl.setWordWrap(True)
        v.addWidget(lbl)
        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(
            ["Algorithm", "PA Set", "CV Run", "ROC-AUC", "TSS", "Boyce"])
        hdr = self.results_table.horizontalHeader()
        for i in range(6): hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        v.addWidget(self.results_table, 1)
        return w

    # ── Sub-tab 3: Current distribution map ───────────────────────────────

    def _build_map_tab(self):
        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10); v.setContentsMargins(8,8,8,8)

        # Status banner
        self.map_status = QLabel(
            "Run the models first (▶ button below). "
            "The current distribution map will appear here automatically.")
        self.map_status.setWordWrap(True)
        self.map_status.setStyleSheet(
            "padding:10px; border-radius:5px; border:1px solid palette(mid);"
            "font-size:11px;")
        v.addWidget(self.map_status)

        # Map output table
        map_grp = QGroupBox("Generated Maps"); ml = QVBoxLayout(map_grp)
        self.map_table = QTableWidget(0, 3)
        self.map_table.setHorizontalHeaderLabels(["Layer name", "Type", "File"])
        hdr = self.map_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.map_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.map_table.setAlternatingRowColors(True)
        self.map_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        ml.addWidget(self.map_table)

        btn_row = QHBoxLayout()
        btn_load = QPushButton("Display Selected Map")
        btn_load.setObjectName("btn_secondary")
        btn_load.clicked.connect(self._load_selected)
        btn_load_all = QPushButton("Display All Ensemble Maps")
        btn_load_all.clicked.connect(self._load_all_ensemble)
        btn_row.addWidget(btn_load); btn_row.addWidget(btn_load_all); btn_row.addStretch()
        ml.addLayout(btn_row)
        v.addWidget(map_grp)

        # Output dir
        od = QGroupBox("Output Directory (for saving map files)")
        ol = QHBoxLayout(od)
        self.out_dir = QLineEdit()
        self.out_dir.setPlaceholderText("Uses main output directory from ① Data (auto-filled)")
        btn_od = QPushButton("Browse…"); btn_od.setObjectName("btn_secondary")
        btn_od.clicked.connect(self._browse_outdir)
        ol.addWidget(self.out_dir); ol.addWidget(btn_od)
        v.addWidget(od)

        # ── Embedded map viewer ──
        from PyQt6.QtWidgets import QGroupBox as _GB
        map_view_grp = _GB("Distribution Map Viewer")
        map_view_layout = QVBoxLayout(map_view_grp)
        self.map_viewer = RasterMapWidget()
        self.map_viewer.setMinimumHeight(380)
        map_view_layout.addWidget(self.map_viewer)
        v.addWidget(map_view_grp, 1)
        return w

    # ── Algorithm option panels ────────────────────────────────────────────

    def _fw(self):
        w = QWidget(); f = QFormLayout(w); f.setContentsMargins(8,8,8,8); return w, f
    def _note(self, t):
        l = QLabel(t); l.setStyleSheet("font-size:10px;"); l.setWordWrap(True); return l

    def _glm_opts(self):
        w, f = self._fw()
        self.glm_deg = QComboBox(); self.glm_deg.addItems(["linear","quadratic"]); self.glm_deg.setCurrentIndex(1)
        self.glm_C   = QDoubleSpinBox(); self.glm_C.setRange(0.001,1000); self.glm_C.setValue(1.0)
        f.addRow("Polynomial degree:", self.glm_deg); f.addRow("Regularisation C:", self.glm_C); return w

    def _gbm_opts(self):
        w, f = self._fw()
        self.gbm_n = QSpinBox(); self.gbm_n.setRange(50,5000); self.gbm_n.setValue(500); self.gbm_n.setSingleStep(100)
        self.gbm_d = QSpinBox(); self.gbm_d.setRange(1,10); self.gbm_d.setValue(3)
        self.gbm_lr = QDoubleSpinBox(); self.gbm_lr.setRange(0.001,1.0); self.gbm_lr.setValue(0.05); self.gbm_lr.setDecimals(3)
        f.addRow("n_estimators:", self.gbm_n); f.addRow("max_depth:", self.gbm_d); f.addRow("learning_rate:", self.gbm_lr); return w

    def _brt_opts(self):
        w, f = self._fw()
        self.brt_n   = QSpinBox(); self.brt_n.setRange(100,10000); self.brt_n.setValue(1000); self.brt_n.setSingleStep(100)
        self.brt_d   = QSpinBox(); self.brt_d.setRange(1,10); self.brt_d.setValue(5)
        self.brt_lr  = QDoubleSpinBox(); self.brt_lr.setRange(0.001,0.5); self.brt_lr.setValue(0.01); self.brt_lr.setDecimals(3)
        self.brt_sub = QDoubleSpinBox(); self.brt_sub.setRange(0.1,1.0); self.brt_sub.setValue(0.75); self.brt_sub.setDecimals(2)
        self.brt_lf  = QSpinBox(); self.brt_lf.setRange(1,100); self.brt_lf.setValue(10)
        f.addRow(self._note("Ecological defaults (Elith et al. 2008)"))
        f.addRow("n_estimators:", self.brt_n); f.addRow("max_depth:", self.brt_d)
        f.addRow("learning_rate:", self.brt_lr); f.addRow("subsample:", self.brt_sub)
        f.addRow("min_samples_leaf:", self.brt_lf); return w

    def _rf_opts(self):
        w, f = self._fw()
        self.rf_n  = QSpinBox(); self.rf_n.setRange(50,2000); self.rf_n.setValue(500); self.rf_n.setSingleStep(100)
        self.rf_lf = QSpinBox(); self.rf_lf.setRange(1,50); self.rf_lf.setValue(1)
        f.addRow("n_estimators:", self.rf_n); f.addRow("min_samples_leaf:", self.rf_lf); return w

    def _svm_opts(self):
        w, f = self._fw()
        self.svm_C = QDoubleSpinBox(); self.svm_C.setRange(0.001,1000); self.svm_C.setValue(1.0)
        self.svm_k = QComboBox(); self.svm_k.addItems(["rbf","linear","poly","sigmoid"])
        self.svm_g = QComboBox(); self.svm_g.addItems(["scale","auto"])
        f.addRow(self._note("StandardScaler applied automatically"))
        f.addRow("C:", self.svm_C); f.addRow("kernel:", self.svm_k); f.addRow("gamma:", self.svm_g); return w

    def _ann_opts(self):
        w, f = self._fw()
        self.ann_h   = QLineEdit("100,50")
        self.ann_act = QComboBox(); self.ann_act.addItems(["relu","tanh","logistic"])
        self.ann_it  = QSpinBox(); self.ann_it.setRange(100,5000); self.ann_it.setValue(2000)
        f.addRow(self._note("MLP. StandardScaler applied automatically. Hidden layers e.g. '100,50'"))
        f.addRow("Hidden layers:", self.ann_h); f.addRow("Activation:", self.ann_act); f.addRow("max_iter:", self.ann_it); return w

    def _xgb_opts(self):
        w, f = self._fw()
        f.addRow(self._note(
            "XGBoost: Extreme Gradient Boosting.\n"
            "Regularised tree boosting — very fast, handles missing values.\n"
            "Requires: pip install xgboost"))
        self.xgb_n   = QSpinBox();  self.xgb_n.setRange(50,5000);   self.xgb_n.setValue(500);  self.xgb_n.setSingleStep(50)
        self.xgb_d   = QSpinBox();  self.xgb_d.setRange(1,12);      self.xgb_d.setValue(6)
        self.xgb_lr  = QDoubleSpinBox(); self.xgb_lr.setRange(0.001,0.5); self.xgb_lr.setValue(0.05); self.xgb_lr.setDecimals(3)
        self.xgb_sub = QDoubleSpinBox(); self.xgb_sub.setRange(0.1,1.0); self.xgb_sub.setValue(0.8); self.xgb_sub.setDecimals(2)
        self.xgb_cbt = QDoubleSpinBox(); self.xgb_cbt.setRange(0.1,1.0); self.xgb_cbt.setValue(0.8); self.xgb_cbt.setDecimals(2); self.xgb_cbt.setToolTip("colsample_bytree: fraction of features per tree")
        self.xgb_ra  = QDoubleSpinBox(); self.xgb_ra.setRange(0,10);  self.xgb_ra.setValue(0); self.xgb_ra.setDecimals(2); self.xgb_ra.setToolTip("reg_alpha: L1 regularisation")
        self.xgb_rl  = QDoubleSpinBox(); self.xgb_rl.setRange(0,10);  self.xgb_rl.setValue(1); self.xgb_rl.setDecimals(2); self.xgb_rl.setToolTip("reg_lambda: L2 regularisation")
        f.addRow("n_estimators:", self.xgb_n)
        f.addRow("max_depth:", self.xgb_d)
        f.addRow("learning_rate:", self.xgb_lr)
        f.addRow("subsample:", self.xgb_sub)
        f.addRow("colsample_bytree:", self.xgb_cbt)
        f.addRow("reg_alpha (L1):", self.xgb_ra)
        f.addRow("reg_lambda (L2):", self.xgb_rl)
        return w

    def _lgb_opts(self):
        w, f = self._fw()
        f.addRow(self._note(
            "LightGBM: histogram-based gradient boosting.\n"
            "Faster than XGBoost on large datasets, lower memory usage.\n"
            "Requires: pip install lightgbm"))
        self.lgb_n   = QSpinBox();  self.lgb_n.setRange(50,5000);   self.lgb_n.setValue(500);  self.lgb_n.setSingleStep(50)
        self.lgb_d   = QSpinBox();  self.lgb_d.setRange(-1,100);    self.lgb_d.setValue(-1);   self.lgb_d.setToolTip("-1 = no limit")
        self.lgb_lr  = QDoubleSpinBox(); self.lgb_lr.setRange(0.001,0.5); self.lgb_lr.setValue(0.05); self.lgb_lr.setDecimals(3)
        self.lgb_lv  = QSpinBox();  self.lgb_lv.setRange(2,255);    self.lgb_lv.setValue(31);  self.lgb_lv.setToolTip("num_leaves: max leaves per tree (controls model complexity)")
        self.lgb_sub = QDoubleSpinBox(); self.lgb_sub.setRange(0.1,1.0); self.lgb_sub.setValue(0.8); self.lgb_sub.setDecimals(2)
        self.lgb_cbt = QDoubleSpinBox(); self.lgb_cbt.setRange(0.1,1.0); self.lgb_cbt.setValue(0.8); self.lgb_cbt.setDecimals(2)
        self.lgb_mc  = QSpinBox();  self.lgb_mc.setRange(1,200);    self.lgb_mc.setValue(20);  self.lgb_mc.setToolTip("min_child_samples: min samples per leaf")
        self.lgb_ra  = QDoubleSpinBox(); self.lgb_ra.setRange(0,10); self.lgb_ra.setValue(0); self.lgb_ra.setDecimals(2)
        self.lgb_rl  = QDoubleSpinBox(); self.lgb_rl.setRange(0,10); self.lgb_rl.setValue(0); self.lgb_rl.setDecimals(2)
        f.addRow("n_estimators:", self.lgb_n)
        f.addRow("max_depth (-1=∞):", self.lgb_d)
        f.addRow("learning_rate:", self.lgb_lr)
        f.addRow("num_leaves:", self.lgb_lv)
        f.addRow("subsample:", self.lgb_sub)
        f.addRow("colsample_bytree:", self.lgb_cbt)
        f.addRow("min_child_samples:", self.lgb_mc)
        f.addRow("reg_alpha (L1):", self.lgb_ra)
        f.addRow("reg_lambda (L2):", self.lgb_rl)
        return w

    def _cat_opts(self):
        w, f = self._fw()
        f.addRow(self._note(
            "CatBoost: gradient boosting with native categorical support.\n"
            "Symmetric trees, ordered boosting — less overfitting.\n"
            "Requires: pip install catboost"))
        self.cat_it  = QSpinBox();  self.cat_it.setRange(50,5000);  self.cat_it.setValue(500); self.cat_it.setSingleStep(50)
        self.cat_d   = QSpinBox();  self.cat_d.setRange(1,16);      self.cat_d.setValue(6)
        self.cat_lr  = QDoubleSpinBox(); self.cat_lr.setRange(0.001,0.5); self.cat_lr.setValue(0.05); self.cat_lr.setDecimals(3)
        self.cat_l2  = QDoubleSpinBox(); self.cat_l2.setRange(0,20);  self.cat_l2.setValue(3); self.cat_l2.setDecimals(1); self.cat_l2.setToolTip("L2 leaf regularisation")
        self.cat_rs  = QDoubleSpinBox(); self.cat_rs.setRange(0.01,10); self.cat_rs.setValue(1); self.cat_rs.setDecimals(2); self.cat_rs.setToolTip("random_strength: noise for score stdevs")
        self.cat_bt  = QDoubleSpinBox(); self.cat_bt.setRange(0,10);  self.cat_bt.setValue(1); self.cat_bt.setDecimals(2); self.cat_bt.setToolTip("bagging_temperature: Bayesian bootstrap strength")
        self.cat_bc  = QSpinBox();  self.cat_bc.setRange(1,255);    self.cat_bc.setValue(128); self.cat_bc.setToolTip("border_count: feature quantisation borders")
        f.addRow("iterations:", self.cat_it)
        f.addRow("depth:", self.cat_d)
        f.addRow("learning_rate:", self.cat_lr)
        f.addRow("l2_leaf_reg:", self.cat_l2)
        f.addRow("random_strength:", self.cat_rs)
        f.addRow("bagging_temperature:", self.cat_bt)
        f.addRow("border_count:", self.cat_bc)
        return w

    def _gam_opts(self):
        w, f = self._fw()
        f.addRow(self._note("LogisticGAM with smoothing splines.\nRequires: pip install pygam")); return w

    def _mx_opts(self):
        w, f = self._fw()
        self.mx_ft = QLineEdit("linear,hinge,product")
        self.mx_b  = QDoubleSpinBox(); self.mx_b.setRange(0.1,10); self.mx_b.setValue(1.0); self.mx_b.setDecimals(1)
        self.mx_lm = QComboBox(); self.mx_lm.addItems(["best","last"])
        self.mx_nh = QSpinBox(); self.mx_nh.setRange(10,200); self.mx_nh.setValue(50)
        f.addRow(self._note("Maximum Entropy via elapid.\nRequires: pip install elapid"))
        f.addRow("Feature types:", self.mx_ft); f.addRow("Regularisation β:", self.mx_b)
        f.addRow("Use lambdas:", self.mx_lm); f.addRow("N hinge features:", self.mx_nh); return w

    def _enfa_opts(self):
        w, f = self._fw()
        self.enfa_k = QSpinBox()
        self.enfa_k.setRange(1, 10); self.enfa_k.setValue(3)
        self.enfa_k.setToolTip("Number of specialisation axes to retain (K). "
                                "Higher values capture more variance but may overfit.")
        f.addRow(self._note(
            "Ecological Niche Factor Analysis (Hirzel et al. 2002).\n"
            "Presence-only algorithm — no pseudo-absences needed.\n"
            "Uses background rows (pseudo-absences) only to estimate the "
            "global environmental distribution.\n"
            "Requires: scikit-learn (already installed)"))
        f.addRow("Specialisation axes (K):", self.enfa_k)
        return w

    def _mahal_opts(self):
        w, f = self._fw()
        self.mahal_reg = QDoubleSpinBox()
        self.mahal_reg.setRange(0.0, 1.0); self.mahal_reg.setValue(1e-6)
        self.mahal_reg.setDecimals(8); self.mahal_reg.setSingleStep(1e-6)
        self.mahal_reg.setToolTip(
            "Regularisation added to diagonal of covariance matrix "
            "to prevent singularity. Increase if you get LinAlgError.")
        self.mahal_shrink = QCheckBox("Ledoit-Wolf shrinkage (recommended)")
        self.mahal_shrink.setChecked(True)
        self.mahal_shrink.setToolTip(
            "Use Ledoit-Wolf optimal shrinkage estimator for the covariance "
            "matrix. More stable than the sample covariance for small samples.")
        f.addRow(self._note(
            "Mahalanobis Distance Niche Model (Farber & Kadmon 2003).\n"
            "Presence-only algorithm — models the multivariate Gaussian niche.\n"
            "Suitability = exp(−0.5 · D²) where D² is the Mahalanobis distance\n"
            "from a point to the species' mean environmental conditions.\n"
            "Requires: scikit-learn (already installed)"))
        f.addRow("Regularisation (ε):", self.mahal_reg)
        f.addRow("", self.mahal_shrink)
        return w

    # ── Test data mode helpers ────────────────────────────────────────────

    def _on_test_mode_changed(self, random_checked: bool):
        self.split.setEnabled(random_checked)
        self._test_csv_edit.setEnabled(not random_checked)
        self._btn_test_csv.setEnabled(not random_checked)

    def _browse_test_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select External Test Occurrence CSV", "",
            "CSV files (*.csv)")
        if path:
            self._test_csv_edit.setText(path)

    # ── Run ───────────────────────────────────────────────────────────────

    def _browse_outdir(self):
        p = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if p: self.out_dir.setText(p)

    def showEvent(self, event):
        super().showEvent(event)
        # Auto-fill output dir from state
        if not self.out_dir.text():
            od = self.dlg.state.get("output_dir", "")
            if od: self.out_dir.setText(od)

        # Show categorical variable info in status banner
        formatter = self.dlg.state.get("formatter")
        if formatter:
            cat_rasters = getattr(formatter, "cat_var_names", [])
            cont_vars = self.dlg.state.get("var_names") or []
            if cat_rasters:
                encoded = getattr(formatter, "encoded_cat_names", cat_rasters)
                self.map_status.setText(
                    f"Continuous variables ({len(cont_vars)}): "
                    f"{', '.join(cont_vars[:10])}{'…' if len(cont_vars)>10 else ''}\n\n"
                    f"Categorical variables ({len(cat_rasters)} raster → "
                    f"{len(encoded)} encoded): {', '.join(encoded)}\n\n"
                    "Categorical variables are included in all models automatically (no VIF filtering).")
            elif cont_vars:
                self.map_status.setText(
                    f"Variables ({len(cont_vars)}): {', '.join(cont_vars)}\n"
                    "No categorical variables.")

    def _run(self):
        pa_datasets = self.dlg.state.get("pa_datasets")
        var_names   = self.dlg.state.get("var_names")
        formatter   = self.dlg.state.get("formatter")
        if not pa_datasets:
            self.dlg.show_error("Complete ① Data and ② Variables steps first."); return

        algos = [k for k, chk in self._algo_checks.items()
                 if chk.isChecked() and chk.isEnabled()]
        if not algos:
            self.dlg.show_error("Select at least one algorithm."); return

        # Training rasters for current projection
        # Map each selected variable name → its raster path (by stem matching)
        if not formatter or not hasattr(formatter, "env_rasters"):
            self.dlg.show_error(
                "Training rasters not found.\n"
                "Please complete ① Data step first."); return

        import os as _os
        # Build stem → path lookup — apply SAME sanitize as load_data()
        # so keys match the sanitized var_names stored in formatter
        import re as _re
        def _san(name):
            s = _re.sub(r"[ \(\)\-\.]+", "_", str(name))
            s = _re.sub(r"_+", "_", s)
            return s.strip("_") or "var"

        stem_to_path = {}
        for rpath in formatter.env_rasters:
            raw_stem = _os.path.splitext(_os.path.basename(rpath))[0]
            sanitized = _san(raw_stem)
            stem_to_path[sanitized] = rpath

        # Match CONTINUOUS selected var_names to raster paths
        training_rasters = []
        missing = []
        for vname in var_names:
            if vname in stem_to_path:
                training_rasters.append(stem_to_path[vname])
            else:
                missing.append(vname)

        if missing:
            self.dlg.show_error(
                f"Cannot find raster files for {len(missing)} selected variable(s):\n"
                f"  Missing: {', '.join(missing)}\n\n"
                f"Available raster stems:\n  {', '.join(sorted(stem_to_path.keys()))}\n\n"
                f"Make sure raster file names match the variable names shown in ② Variables."
            ); return

        # Categorical raster paths and encoded names (from formatter)
        cat_raster_paths  = list(formatter.cat_rasters) if hasattr(formatter, "cat_rasters") else []
        cat_encoding      = getattr(formatter, "cat_encoding", "one-hot")

        # encoded_cat_names: populated by generate_pa_datasets after load_data
        # If empty (no categoricals added, or not yet generated), default to []
        encoded_cat_names = getattr(formatter, "encoded_cat_names", []) or []

        if cat_raster_paths and not encoded_cat_names:
            # Categoricals were added but encoding names not yet computed —
            # compute them now from cat_classes
            cat_classes = getattr(formatter, "cat_classes", {})
            cat_var_names = getattr(formatter, "cat_var_names", [])
            if cat_encoding == "one-hot":
                encoded_cat_names = [
                    f"{vn}_{cls}"
                    for vn in cat_var_names
                    for cls in cat_classes.get(vn, [])
                ]
            else:
                encoded_cat_names = list(cat_var_names)
            self.dlg.log(
                f"Categorical variables: {len(cat_var_names)} rasters → "
                f"{len(encoded_cat_names)} encoded features ({cat_encoding}): "
                f"{', '.join(encoded_cat_names[:8])}{'…' if len(encoded_cat_names)>8 else ''}")

        out_dir = self.out_dir.text().strip() or self.dlg.state.get("output_dir", ".")
        self.dlg.state["output_dir"] = out_dir

        def _h(t):
            try: return tuple(int(x.strip()) for x in t.split(","))
            except: return (100, 50)
        def _f(t): return [x.strip() for x in t.split(",") if x.strip()]

        algo_opts = {
            "GLM":    {"type": self.glm_deg.currentText(), "C": self.glm_C.value()},
            "GBM":    {"n_estimators": self.gbm_n.value(), "max_depth": self.gbm_d.value(), "learning_rate": self.gbm_lr.value()},
            "BRT":    {"n_estimators": self.brt_n.value(), "max_depth": self.brt_d.value(), "learning_rate": self.brt_lr.value(), "subsample": self.brt_sub.value(), "min_samples_leaf": self.brt_lf.value()},
            "RF":     {"n_estimators": self.rf_n.value(), "min_samples_leaf": self.rf_lf.value()},
            "SVM":    {"C": self.svm_C.value(), "kernel": self.svm_k.currentText(), "gamma": self.svm_g.currentText()},
            "ANN":    {"hidden_layer_sizes": _h(self.ann_h.text()), "activation": self.ann_act.currentText(), "max_iter": self.ann_it.value()},
            "XGB":    {"n_estimators": self.xgb_n.value(), "max_depth": self.xgb_d.value(),
                       "learning_rate": self.xgb_lr.value(), "subsample": self.xgb_sub.value(),
                       "colsample_bytree": self.xgb_cbt.value(),
                       "reg_alpha": self.xgb_ra.value(), "reg_lambda": self.xgb_rl.value()},
            "LGB":    {"n_estimators": self.lgb_n.value(), "max_depth": self.lgb_d.value(),
                       "learning_rate": self.lgb_lr.value(), "num_leaves": self.lgb_lv.value(),
                       "subsample": self.lgb_sub.value(), "colsample_bytree": self.lgb_cbt.value(),
                       "min_child_samples": self.lgb_mc.value(),
                       "reg_alpha": self.lgb_ra.value(), "reg_lambda": self.lgb_rl.value()},
            "CAT":    {"iterations": self.cat_it.value(), "depth": self.cat_d.value(),
                       "learning_rate": self.cat_lr.value(), "l2_leaf_reg": self.cat_l2.value(),
                       "random_strength": self.cat_rs.value(),
                       "bagging_temperature": self.cat_bt.value(),
                       "border_count": self.cat_bc.value()},
            "GAM":    {},
            "MAXENT": {"feature_types": _f(self.mx_ft.text()), "beta": self.mx_b.value(), "use_lambdas": self.mx_lm.currentText(), "n_hinge": self.mx_nh.value()},
            "ENFA":   {"n_spec_axes": self.enfa_k.value()},
            "MAHAL":  {"regularisation": self.mahal_reg.value(), "ledoit_wolf": self.mahal_shrink.isChecked()},
        }

        ens_method = self.ens_method.currentText()
        ens_metric = self.ens_metric.currentText()
        ens_thr    = self.ens_thr.value()

        self.results_table.setRowCount(0)
        self.dlg.set_progress("Fitting models…", 0)
        self.sub.setCurrentIndex(1)  # Switch to results tab

        from habitus.sdm_core import SDMModeler, EnsembleModeler, Projector
        from habitus.main_dialog import WorkerThread

        _var_names          = var_names[:]
        _training_rasters   = training_rasters[:]
        _cat_rasters        = cat_raster_paths[:]
        _encoded_cat_names  = encoded_cat_names[:]
        _cat_encoding       = cat_encoding
        _algos              = algos[:]
        _bg_X               = formatter.background_X if hasattr(formatter, "background_X") else None
        _formatter          = formatter
        _thr_method         = self.bin_thr_method.currentText().split()[0]  # "max_tss" etc.
        # Build final feature list:
        # selected continuous vars + categorical vars (label-encoded, 1 col each)
        _cat_feature_names = getattr(formatter, "cat_var_names", []) or []
        _all_feature_names = _var_names + _cat_feature_names

        if _cat_feature_names:
            self.dlg.log(
                f"Categorical variables added to model "
                f"({len(_cat_feature_names)}): {', '.join(_cat_feature_names)}")
        else:
            self.dlg.log("No categorical variables.")

        def task(progress_cb):
            # 1. Fit models
            _test_csv = None
            if self._rdo_external.isChecked():
                _test_csv = self._test_csv_edit.text().strip() or None
                if not _test_csv:
                    raise ValueError(
                        "External test points mode selected but no CSV provided.\n"
                        "Please browse and select a test occurrence CSV.")

            modeler = SDMModeler(
                pa_datasets=pa_datasets,
                var_names=_all_feature_names,
                cont_var_names=_var_names,
                algorithms=_algos, algo_options=algo_opts,
                n_cv_runs=self.n_cv.value(),
                data_split=self.split.value() if _test_csv is None else 80,
                var_import_n=self.v_imp.value(),
                maxent_background=_bg_X,
                ponly_background=getattr(formatter, "background_ponly", None),
                threshold_method=_thr_method,
                progress_callback=progress_cb,
                test_occurrence_csv=_test_csv,
                formatter=formatter,
            )
            modeler.run()

            # 2. Build ensemble (simple: all trained methods combined)
            methods = []
            if "Weighted" in ens_method or "Both" in ens_method:
                methods.append("weighted_mean")
            if "Committee" in ens_method or "Both" in ens_method:
                methods.append("committee_averaging")

            ensemble = EnsembleModeler(
                modeler=modeler,
                eval_metric=ens_metric,
                quality_threshold=ens_thr,
                methods=methods,
                progress_callback=progress_cb,
            )
            ensemble._filter_models()

            # 3. Project onto current climate rasters
            progress_cb("Projecting current distribution map…", 92)
            proj_out = os.path.join(out_dir, "current")
            projector = Projector(modeler=modeler, ensemble_modeler=ensemble,
                                    formatter=_formatter)
            output_files = projector.project(
                raster_paths=_training_rasters,
                proj_name="current",
                output_dir=proj_out,
                selected_algorithms=_algos,
                progress_cb=progress_cb,
            )

            return modeler, ensemble, output_files

        self._worker = WorkerThread(task)
        self._worker.progress.connect(self.dlg.set_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(lambda e: self.dlg.show_error(f"Modelling failed:\n{e}"))
        self._worker.start()

    def _on_done(self, result):
        modeler, ensemble, output_files = result

        # Store in state
        self.dlg.state["modeler"]  = modeler
        self.dlg.state["ensemble"] = ensemble
        self.dlg.state["projections"]["current"] = output_files

        if not output_files:
            self.dlg.log(
                "WARNING: No map files were produced. "
                "Check the log above for FAILED messages. "
                "Common causes: raster write permission, disk space, "
                "or model prediction error.")

        # Fill evaluation table
        df = modeler.get_evaluations_df()
        self.results_table.setRowCount(0)
        for _, row in df.iterrows():
            r = self.results_table.rowCount(); self.results_table.insertRow(r)
            self.results_table.setItem(r, 0, QTableWidgetItem(str(row["Algorithm"])))
            self.results_table.setItem(r, 1, QTableWidgetItem(str(row["PA_set"])))
            self.results_table.setItem(r, 2, QTableWidgetItem(str(row["CV_run"])))
            for ci, m in [(3,"ROC"),(4,"TSS"),(5,"Boyce")]:
                val = row[m]
                item = QTableWidgetItem(f"{val:.3f}" if val == val else "N/A")
                if val == val:
                    if val >= 0.8:   item.setForeground(_theme_fg("ok"))
                    elif val >= 0.6: item.setForeground(_theme_fg("warn"))
                    else:            item.setForeground(_theme_fg("bad"))
                self.results_table.setItem(r, ci, item)

        # Fill map table and auto-load ensemble maps
        self.map_table.setRowCount(0)
        n_sel = len(ensemble.selected_keys)
        algos_used = sorted(set(k[0] for k in modeler.fitted_models if k[2] == "Full"))
        loaded_layers = []

        for key, fpath in output_files.items():
            r = self.map_table.rowCount(); self.map_table.insertRow(r)
            self.map_table.setItem(r, 0, QTableWidgetItem(key))
            is_prob = key.endswith("_prob")
            type_item = QTableWidgetItem("Probability (0–1)" if is_prob else "Binary (0/1)")
            type_item.setForeground(_theme_fg("neutral" if is_prob else "ok"))
            self.map_table.setItem(r, 1, type_item)
            self.map_table.setItem(r, 2, QTableWidgetItem(fpath))

            # Auto-display all probability maps in the embedded viewer
            if is_prob and os.path.isfile(fpath):
                lname = _make_current_label(key)
                self.map_viewer.load_raster(fpath, lname, "suitability")
                loaded_layers.append(lname)

        # Add train/test occurrence points to the map viewer
        self._add_traintest_layers(modeler)

        # Update status
        n_maps = len(output_files)
        thr_method = getattr(modeler, "threshold_method", "max_tss")
        status_msg = (
            f"Modelling complete.\n"
            f"Algorithms: {', '.join(algos_used)}   |   "
            f"Models included in combined map: {n_sel}/{len(modeler.fitted_models)}\n"
            f"Threshold method: {thr_method}   |   "
            f"{n_maps} map files saved.  "
            f"{len(loaded_layers)} ensemble map(s) displayed in map viewer: "
            f"{', '.join(loaded_layers) if loaded_layers else '—'}\n"
            f"CRS: WGS 84 (EPSG:4326)   |   Values: 0.0 – 1.0 (normalised)"
        )
        self.map_status.setText(status_msg)
        self.sub.setCurrentIndex(2)  # Switch to map tab

        self.dlg.set_progress(
            f"Done — {len(algos_used)} algorithms, {n_maps} maps, "
            f"{len(loaded_layers)} auto-loaded to QGIS.", 100)

        # Unlock next steps
        self.dlg.unlock_tab(self.dlg.TAB_FUTURE)
        self.dlg.unlock_tab(self.dlg.TAB_RANGE)
        self.dlg.unlock_tab(self.dlg.TAB_EVALUATION)
        self.dlg.unlock_tab(self.dlg.TAB_VALIDATION)
        self.dlg.unlock_tab(self.dlg.TAB_REPORT)
        # Auto-populate validation tab layer combos
        try:
            self.dlg.tab_valid._fill_from_output()
        except Exception:
            pass

    def _add_traintest_layers(self, modeler):
        """
        Overlay train/test occurrence points on the embedded map viewer.
        Train presences = green   Test presences = yellow
        Train pseudo-absences = red  (smaller)
        """
        try:
            if not modeler.split_coords:
                return

            pa_key = sorted(modeler.split_coords.keys())[0]
            coords = modeler.split_coords[pa_key]
            tr = coords["train"]
            te = coords["test"]

            tr_lons = [tr["lon"][i] for i, y in enumerate(tr["y"]) if y == 1]
            tr_lats = [tr["lat"][i] for i, y in enumerate(tr["y"]) if y == 1]
            te_lons = [te["lon"][i] for i, y in enumerate(te["y"]) if y == 1]
            te_lats = [te["lat"][i] for i, y in enumerate(te["y"]) if y == 1]
            tr_a_lons = [tr["lon"][i] for i, y in enumerate(tr["y"]) if y == 0]
            tr_a_lats = [tr["lat"][i] for i, y in enumerate(tr["y"]) if y == 0]

            if tr_a_lons:
                self.map_viewer.add_scatter(
                    tr_a_lons, tr_a_lats,
                    color="#e74c3c", size=8,
                    label=f"Train PA (n={len(tr_a_lons)})",
                    ptype="bg"
                )
            if te_lons:
                self.map_viewer.add_scatter(
                    te_lons, te_lats,
                    color="#f39c12", size=30,
                    label=f"Test pres. (n={len(te_lons)})",
                    ptype="obs"
                )
            if tr_lons:
                self.map_viewer.add_scatter(
                    tr_lons, tr_lats,
                    color="#27ae60", size=30,
                    label=f"Train pres. (n={len(tr_lons)})",
                    ptype="obs"
                )

            self.dlg.log(
                f"Occurrence points overlaid on map: "
                f"train pres.={len(tr_lons)}, test pres.={len(te_lons)}, "
                f"train PA={len(tr_a_lons)}"
            )

            self._save_split_csv(coords)

        except Exception as e:
            self.dlg.log(f"Could not overlay occurrence points: {e}")

    def _save_split_csv(self, coords):
        """Train/test split noktalarını CSV olarak output klasörüne kaydet."""
        import csv, os
        out_base = self.dlg.state.get("output_dir", "")
        if not out_base:
            return
        os.makedirs(out_base, exist_ok=True)

        tr = coords.get("train", {})
        te = coords.get("test",  {})

        for split, data, fname in [
            ("train", tr, "occurrence_train.csv"),
            ("test",  te, "occurrence_test.csv"),
        ]:
            if not data.get("lon"):
                continue
            fpath = os.path.join(out_base, fname)
            try:
                with open(fpath, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["longitude", "latitude", "presence", "split"])
                    for lon, lat, y in zip(data["lon"], data["lat"], data["y"]):
                        w.writerow([
                            round(float(lon), 6),
                            round(float(lat), 6),
                            int(y),
                            split
                        ])
                self.dlg.log(f"Saved: {fpath}  ({len(data['lon'])} points)")
            except Exception as e:
                self.dlg.log(f"Could not save {fname}: {e}")

        # Combined file (all points, split column)
        fpath_all = os.path.join(out_base, "occurrence_all_splits.csv")
        try:
            with open(fpath_all, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["longitude", "latitude", "presence", "split"])
                for split, data in [("train", tr), ("test", te)]:
                    for lon, lat, y in zip(
                        data.get("lon",[]), data.get("lat",[]), data.get("y",[])):
                        w.writerow([round(float(lon),6), round(float(lat),6),
                                    int(y), split])
            self.dlg.log(f"Saved: {fpath_all}")
        except Exception as e:
            self.dlg.log(f"Could not save combined CSV: {e}")

    def _load_selected(self):
        done = set()
        for item in self.map_table.selectedItems():
            row = item.row()
            if row in done:
                continue
            done.add(row)
            key   = self.map_table.item(row, 0).text()
            suf   = self.map_table.item(row, 1).text()
            fpath = self.map_table.item(row, 2).text()
            if not os.path.isfile(fpath):
                self.dlg.show_error(f"File not found:\n{fpath}")
                continue
            style = "suitability" if "Probability" in suf else "binary"
            self.map_viewer.load_raster(fpath, _make_current_label(key), style)

    def _load_all_ensemble(self):
        output_files = self.dlg.state.get("projections", {}).get("current", {})
        for key, fpath in output_files.items():
            if key.startswith("EM") and os.path.isfile(fpath):
                style = "suitability" if key.endswith("_prob") else "binary"
                self.map_viewer.load_raster(fpath, _make_current_label(key), style)
