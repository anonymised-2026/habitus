# -*- coding: utf-8 -*-
"""
Tab ② – Variable Selection

Layout:
  ┌─ Settings ────────────────────────────────────────────────────────────┐
  │  Corr threshold (default 0.8) | Method | VIF threshold | Re-run       │
  └───────────────────────────────────────────────────────────────────────┘
  ┌─ High-correlation pairs ──────┐  ┌─ Variable checklist ──────────────┐
  │  Sorted list of correlated    │  │  ☑ bio_5   VIF=3.2  AUC=0.81     │
  │  pairs — user sees which ones │  │  ☑ bio_7   VIF=1.9  AUC=0.74     │
  │  to remove                    │  │  ☐ bio_11  VIF=8.4  AUC=0.65     │
  │                               │  │  ...                               │
  │  Click pair → auto-highlights │  │  [All] [Recommended] [None]       │
  │  in checklist                 │  │                                    │
  └───────────────────────────────┘  └────────────────────────────────────┘
  ┌─ Correlation heatmap ─────────────────────────────────────────────────┐
  └───────────────────────────────────────────────────────────────────────┘
  [Confirm & Proceed →]
"""

import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QGroupBox, QComboBox,
    QDoubleSpinBox, QSizePolicy, QApplication, QScrollArea,
    QCheckBox, QFrame, QSpinBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPalette

try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigCanvas
    from matplotlib.figure import Figure
    import matplotlib.patches as _patches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def _tc():
    """Theme colours — dark vs light."""
    bg = QApplication.instance().palette().color(QPalette.ColorRole.Window)
    dark = bg.lightness() < 128
    return {
        "ok":      QColor("#52b788" if dark else "#1a7a4a"),
        "warn":    QColor("#f6ad55" if dark else "#b45309"),
        "bad":     QColor("#fc8181" if dark else "#c0392b"),
        "neutral": QColor("#74c69d" if dark else "#0e6655"),
        "text":    QColor("#e8edf5" if dark else "#1a202c"),  # okunabilir varsayılan metin
        "purple":  QColor("#7c3aed" if dark else "#5b21b6"),
        "row_a":   QColor("#252b3b" if dark else "#ffffff"),
        "row_b":   QColor("#1a2030" if dark else "#eef7f2"),
    }


class VifTab(QWidget):

    def __init__(self, main_dialog):
        super().__init__()
        self.dlg = main_dialog
        self._ranking_df  = None
        self._corr_df     = None      # full correlation matrix
        self._var_checks  = {}        # {varname: QCheckBox}
        self._safe_vars   = set()     # vars with no high-correlation pair
        self._setup_ui()

    # ══════════════════════════════════════════════════════════════════════
    # UI SETUP
    # ══════════════════════════════════════════════════════════════════════

    def _setup_ui(self):
        # ── Root: sub-tabs (classic VIF/Correlation + Advanced) ───────────
        root_outer = QVBoxLayout(self)
        root_outer.setContentsMargins(0, 0, 0, 0)
        root_outer.setSpacing(0)

        from PyQt6.QtWidgets import QTabWidget
        self._outer_tabs = QTabWidget()
        self._outer_tabs.setObjectName("sdm_tabs")
        root_outer.addWidget(self._outer_tabs)

        # Primary sub-tab (VIF + Correlation — existing layout)
        primary = QWidget()
        root = QVBoxLayout(primary)
        root.setSpacing(5)
        root.setContentsMargins(8, 8, 8, 8)
        self._outer_tabs.addTab(primary, "VIF + Correlation")

        # ── Banner ────────────────────────────────────────────────────────
        banner = QLabel(
            "Set the Pearson/Spearman correlation threshold (default 0.8).  "
            "The left panel lists every correlated pair above the threshold — "
            "use it to decide which variable in each pair to drop.  "
            "The right panel lets you freely tick/untick any variable.  "
            "VIF scores are shown as supplementary information only."
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "padding:8px; border-radius:5px; font-size:11px;"
            "border:1px solid palette(mid);")
        root.addWidget(banner)

        # ── Settings bar ─────────────────────────────────────────────────
        sg = QGroupBox("Analysis Settings")
        sf = QFormLayout(sg); sf.setSpacing(6)
        sf.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        sf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        sf.setHorizontalSpacing(12)
        sf.setVerticalSpacing(6)

        self.corr_thr = QDoubleSpinBox()
        self.corr_thr.setRange(0.3, 0.99); self.corr_thr.setValue(0.80)
        self.corr_thr.setDecimals(2); self.corr_thr.setSingleStep(0.05)
        self.corr_thr.setToolTip(
            "Pairs with |r| ≥ this threshold are listed as 'high-correlation'.\n"
            "Common choices: 0.70 (conservative), 0.80 (default), 0.90 (lenient).\n"
            "Dormann et al. (2013) recommend |r| < 0.70 for SDM.")
        self.corr_thr.valueChanged.connect(self._on_thr_changed)

        self.corr_method = QComboBox()
        self.corr_method.addItems(["pearson", "spearman"])
        self.corr_method.setToolTip(
            "pearson: linear correlation (assumes normality)\n"
            "spearman: rank-based, robust to non-normality and outliers")

        self.vif_thr = QDoubleSpinBox()
        self.vif_thr.setRange(2, 50); self.vif_thr.setValue(10)
        self.vif_thr.setSingleStep(1)
        self.vif_thr.setToolTip(
            "VIF > 10 indicates severe multicollinearity (O'Brien 2007).\n"
            "Used for colouring the checklist — does NOT force deselection.")

        btn_run = QPushButton("↻  Run / Refresh Analysis")
        btn_run.setObjectName("btn_secondary")
        btn_run.clicked.connect(self._run_analysis)

        sf.addRow("Correlation threshold (|r| ≥):", self.corr_thr)
        sf.addRow("Correlation method:", self.corr_method)
        sf.addRow("VIF flag threshold (info only):", self.vif_thr)
        sf.addRow("", btn_run)
        root.addWidget(sg)

        # ── Main area: pairs list | checklist ─────────────────────────────
        mid_split = QSplitter(Qt.Orientation.Horizontal)

        # Left: high-correlation pairs
        left_w = QWidget(); left_v = QVBoxLayout(left_w); left_v.setContentsMargins(0,0,0,0); left_v.setSpacing(6)
        lbl_pairs = QLabel("⚠  High-correlation pairs  (|r| ≥ threshold)")
        lbl_pairs.setStyleSheet("font-weight:700; font-size:13px;")
        left_v.addWidget(lbl_pairs)

        self.pairs_info = QLabel(
            "Correlated pairs are listed here after analysis.\n"
            "For each pair, keep the variable with higher AUC or ecological relevance.\n"
            "Click a row to highlight both variables in the checklist.")
        self.pairs_info.setWordWrap(True)
        self.pairs_info.setStyleSheet(
            "font-size:12px; padding:6px; border:1px solid palette(mid); border-radius:4px;")
        left_v.addWidget(self.pairs_info)

        # Safe variables banner — populated by _populate_pairs
        self._safe_label = QLabel()
        self._safe_label.setWordWrap(True)
        self._safe_label.setVisible(False)
        self._safe_label.setStyleSheet(
            "font-size:12px; font-weight:700; color:#1d5235;"
            "background:#d4ead9; padding:8px; border:2px solid #3a8c60;"
            "border-radius:5px;")
        left_v.addWidget(self._safe_label)

        self.pairs_table = QTableWidget(0, 4)
        self.pairs_table.setHorizontalHeaderLabels(["Variable A", "Variable B", "|r|", "±"])
        ph = self.pairs_table.horizontalHeader()
        ph.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        ph.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        ph.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        ph.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        ph.setDefaultSectionSize(32)
        self.pairs_table.verticalHeader().setDefaultSectionSize(30)
        self.pairs_table.verticalHeader().setVisible(False)
        self.pairs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pairs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pairs_table.setAlternatingRowColors(False)
        self.pairs_table.setStyleSheet(
            "QTableWidget { background:#f5faf7; gridline-color:#c4ddd0; border:1px solid #b8d4c4; font-size:12px; }"
            "QTableWidget::item { background:#ffffff; color:#1c3328; padding:5px 6px; }"
            "QTableWidget::item:alternate { background:#eef7f2; color:#1c3328; }"
            "QTableWidget::item:selected { background:#3a8c60; color:#ffffff; }"
            "QHeaderView::section { background:#d4ead9; color:#1d5235; padding:7px 6px; "
            "border:1px solid #b8d4c4; font-weight:bold; font-size:12px; }")
        self.pairs_table.setMinimumWidth(320)
        self.pairs_table.setMinimumHeight(220)
        self.pairs_table.itemSelectionChanged.connect(self._on_pair_selected)
        left_v.addWidget(self.pairs_table, 1)

        # "Drop A" / "Drop B" helper buttons
        pair_btn_row = QHBoxLayout()
        self.btn_drop_a = QPushButton("Uncheck  Variable A")
        self.btn_drop_a.setObjectName("btn_danger")
        self.btn_drop_a.setToolTip("Untick the first variable of the selected pair")
        self.btn_drop_a.clicked.connect(lambda: self._drop_pair_var(0))
        self.btn_drop_b = QPushButton("Uncheck  Variable B")
        self.btn_drop_b.setObjectName("btn_danger")
        self.btn_drop_b.setToolTip("Untick the second variable of the selected pair")
        self.btn_drop_b.clicked.connect(lambda: self._drop_pair_var(1))
        pair_btn_row.addWidget(self.btn_drop_a)
        pair_btn_row.addWidget(self.btn_drop_b)
        left_v.addLayout(pair_btn_row)

        mid_split.addWidget(left_w)

        # Right: variable checklist
        right_w = QWidget(); right_v = QVBoxLayout(right_w); right_v.setContentsMargins(0,0,0,0); right_v.setSpacing(4)
        lbl_vars = QLabel("Variable selection  (tick to include in model)")
        lbl_vars.setStyleSheet("font-weight:700; font-size:12px;")
        right_v.addWidget(lbl_vars)

        # Scroll area for checkboxes
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._checklist_container = QWidget()
        self._checklist_layout = QVBoxLayout(self._checklist_container)
        self._checklist_layout.setSpacing(2)
        self._checklist_layout.setContentsMargins(4, 4, 4, 4)
        self._checklist_layout.addStretch()
        self._scroll.setWidget(self._checklist_container)
        right_v.addWidget(self._scroll, 1)

        # Bulk-action buttons
        bulk_row = QHBoxLayout()
        btn_all  = QPushButton("All");         btn_all.setObjectName("btn_secondary")
        btn_rec  = QPushButton("Recommended"); 
        btn_none = QPushButton("None");        btn_none.setObjectName("btn_danger")
        btn_all.setToolTip("Tick all variables")
        btn_rec.setToolTip("Tick only variables flagged as Recommended (no high VIF, no high corr)")
        btn_none.setToolTip("Untick all variables")
        btn_all.clicked.connect(self._select_all)
        btn_rec.clicked.connect(self._select_recommended)
        btn_none.clicked.connect(self._deselect_all)
        bulk_row.addWidget(btn_all); bulk_row.addWidget(btn_rec); bulk_row.addWidget(btn_none)
        right_v.addLayout(bulk_row)

        mid_split.addWidget(right_w)
        mid_split.setSizes([520, 300])
        root.addWidget(mid_split, 1)

        # ── Heatmap ───────────────────────────────────────────────────────
        hm_group = QGroupBox("Correlation Heatmap")
        hm_v = QVBoxLayout(hm_group)
        if HAS_MPL:
            self.heatmap_fig    = Figure(facecolor="white")
            self.heatmap_canvas = FigCanvas(self.heatmap_fig)
            self.heatmap_canvas.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.heatmap_canvas.setMinimumHeight(160)
            hm_v.addWidget(self.heatmap_canvas)
        else:
            hm_v.addWidget(QLabel("pip install matplotlib  to enable heatmap"))
        root.addWidget(hm_group)

        # ── Confirm bar ───────────────────────────────────────────────────
        confirm_row = QHBoxLayout()
        self.selection_label = QLabel("No variables selected yet.")
        self.selection_label.setStyleSheet("font-size:11px;")
        btn_confirm = QPushButton("✔  Confirm Variable Selection → Proceed to ③ Models")
        btn_confirm.clicked.connect(self._confirm)
        confirm_row.addWidget(self.selection_label, 1)
        confirm_row.addWidget(btn_confirm)
        root.addLayout(confirm_row)

        # ── Secondary sub-tab: Advanced Analysis ──────────────────────────
        from habitus.tabs.tab_vif_advanced import AdvancedAnalysisTab
        self._advanced = AdvancedAnalysisTab(self.dlg)
        self._outer_tabs.addTab(self._advanced, "Advanced Analysis")

    # ══════════════════════════════════════════════════════════════════════
    # DATA FLOW
    # ══════════════════════════════════════════════════════════════════════

    def showEvent(self, event):
        super().showEvent(event)
        formatter = self.dlg.state.get("formatter")
        if (formatter and formatter.collinearity_df is not None
                and self._ranking_df is None):
            self._ranking_df = formatter.collinearity_df
            self._populate_pairs()
            self._rebuild_checklist(formatter.var_names)
            self._plot_heatmap()

    def _run_analysis(self):
        formatter   = self.dlg.state.get("formatter")
        pa_datasets = self.dlg.state.get("pa_datasets")
        if not formatter or not pa_datasets:
            self.dlg.show_error("Complete ① Data step first."); return

        import pandas as pd
        from habitus.sdm_core import variable_priority_ranking, compute_correlation_matrix

        try:
            X_pool = pd.concat([ds[0] for ds in pa_datasets], ignore_index=True)
            y_pool = np.concatenate([ds[1] for ds in pa_datasets]).astype(float).copy()
            var_names = self.dlg.state.get("var_names") or formatter.var_names
            X_clean   = X_pool[var_names].dropna().reset_index(drop=True)
            y_clean   = y_pool[:len(X_clean)]

            self._ranking_df = variable_priority_ranking(
                X_clean, y_clean,
                vif_threshold  = self.vif_thr.value(),
                corr_threshold = self.corr_thr.value(),
                method         = self.corr_method.currentText(),
            )
            self._corr_df = compute_correlation_matrix(
                X_clean, method=self.corr_method.currentText())

            self._populate_pairs()
            self._rebuild_checklist(var_names)
            self._plot_heatmap()

        except Exception as e:
            import traceback
            self.dlg.show_error(f"Analysis failed:\n{traceback.format_exc()}")

    # ══════════════════════════════════════════════════════════════════════
    # CHECKLIST  (right panel)
    # ══════════════════════════════════════════════════════════════════════

    def _rebuild_checklist(self, var_names):
        """Rebuild the right-side checkbox list for all variables."""
        # Remember current selection
        prev_selected = set(self._get_selected_vars())

        # Clear old widgets
        self._var_checks = {}
        while self._checklist_layout.count() > 1:   # keep the stretch
            item = self._checklist_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._ranking_df is not None:
            df_map = {row["Variable"]: row
                      for _, row in self._ranking_df.iterrows()}
        else:
            df_map = {}

        colors = _tc()

        for vname in var_names:
            row_data = df_map.get(vname, {})
            vif  = row_data.get("VIF", float("nan"))
            auc  = row_data.get("Univariate_AUC", float("nan"))
            rec  = row_data.get("Recommended", True)
            vif_ok  = row_data.get("VIF_OK", True)
            corr_ok = row_data.get("Corr_OK", True)

            frame = QFrame()
            frame.setObjectName("var_frame")
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame.setStyleSheet(
                "QFrame#var_frame { background:#f5faf7; border:1px solid #c4ddd0; "
                "border-radius:4px; margin:1px; }")

            row_layout = QHBoxLayout(frame)
            row_layout.setContentsMargins(6, 3, 6, 3)
            row_layout.setSpacing(8)

            # Checkbox — variable name in bold purple
            chk = QCheckBox(vname)
            f = QFont(); f.setBold(True); f.setPointSize(10)
            chk.setFont(f)
            # Variables that appear in no high-correlation pair are always
            # checked — they are "safe" (no redundancy with any other predictor).
            safe = getattr(self, "_safe_vars", set())
            if vname in safe:
                chk.setChecked(True)
            elif prev_selected:
                chk.setChecked(vname in prev_selected)
            else:
                chk.setChecked(rec)
            chk.setStyleSheet("color: #1d5235; font-weight: 700;")
            chk.stateChanged.connect(self._update_selection_label)
            self._var_checks[vname] = chk
            row_layout.addWidget(chk, 2)

            # VIF badge
            # VIF=999 means capped near-perfect collinearity (raw value >> 10^6)
            if vif != vif:           # NaN
                vif_str = "VIF=—"
                vif_style = "font-size:10px; color:palette(mid);"
                vif_tip = "VIF could not be computed (too few samples?)"
            elif vif >= 999:         # capped — near-perfect collinearity
                vif_str = "VIF=∞"
                vif_style = ("background:#7f1d1d; color:#fca5a5; border-radius:3px;"
                             "padding:1px 4px; font-size:10px; font-weight:700;")
                vif_tip = ("Near-perfect collinearity (VIF capped). ""This variable is almost a linear combination of the others. ""Example: bio_6 ~ bio_1 + bio_11 in WorldClim. ""Strongly recommended to remove.")
            elif vif > self.vif_thr.value():   # high but finite
                vif_str = f"VIF={vif:.1f}"
                vif_style = ("background:#7f1d1d; color:#fca5a5; border-radius:3px;"
                             "padding:1px 4px; font-size:10px; font-weight:600;")
                vif_tip = (f"High VIF ({vif:.1f} > {self.vif_thr.value():.0f}) — "
                           f"consider removing, especially for GLM/GAM.")
            else:                    # acceptable
                vif_str = f"VIF={vif:.1f}"
                vif_style = ("background:#14532d; color:#86efac; border-radius:3px;"
                             "padding:1px 4px; font-size:10px;")
                vif_tip = f"Acceptable VIF ({vif:.1f})"

            vif_lbl = QLabel(vif_str)
            vif_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vif_lbl.setMinimumWidth(72)
            vif_lbl.setStyleSheet(vif_style)
            vif_lbl.setToolTip(vif_tip)
            row_layout.addWidget(vif_lbl, 0)

            # AUC badge
            auc_str = f"AUC={auc:.2f}" if auc == auc else "AUC=—"
            auc_lbl = QLabel(auc_str)
            auc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            auc_lbl.setMinimumWidth(72)
            if auc == auc:
                if auc >= 0.75:
                    auc_lbl.setStyleSheet(
                        "background:#14532d; color:#86efac; border-radius:3px;"
                        "padding:1px 4px; font-size:10px;")
                elif auc >= 0.60:
                    auc_lbl.setStyleSheet(
                        "background:#78350f; color:#fde68a; border-radius:3px;"
                        "padding:1px 4px; font-size:10px;")
                else:
                    auc_lbl.setStyleSheet(
                        "background:#7f1d1d; color:#fca5a5; border-radius:3px;"
                        "padding:1px 4px; font-size:10px;")
            else:
                auc_lbl.setStyleSheet("font-size:10px; color:palette(mid);")
            row_layout.addWidget(auc_lbl, 0)

            # Status icon
            if not vif_ok:
                status = "⚠ VIF"
                sc = "color:#fc8181; font-size:10px;"
            elif not corr_ok:
                status = "⚠ Corr"
                sc = "color:#f6ad55; font-size:10px;"
            elif rec:
                status = "✔"
                sc = "color:#52b788; font-size:12px; font-weight:700;"
            else:
                status = "–"
                sc = "color:palette(mid); font-size:10px;"
            st_lbl = QLabel(status); st_lbl.setStyleSheet(sc)
            st_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            st_lbl.setMinimumWidth(40)
            row_layout.addWidget(st_lbl, 0)

            self._checklist_layout.insertWidget(
                self._checklist_layout.count() - 1, frame)

        self._update_selection_label()

    # ══════════════════════════════════════════════════════════════════════
    # PAIRS TABLE  (left panel)
    # ══════════════════════════════════════════════════════════════════════

    def _populate_pairs(self):
        """Fill the high-correlation pairs table."""
        import pandas as pd

        self.pairs_table.setRowCount(0)

        # Get correlation matrix
        corr = self._get_corr_matrix()
        if corr is None:
            return

        thr = self.corr_thr.value()
        vars_ = list(corr.columns)
        n = len(vars_)

        # Collect all pairs above threshold (upper triangle only)
        pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                r = corr.iloc[i, j]
                if abs(r) >= thr:
                    pairs.append((vars_[i], vars_[j], r))

        # Sort by |r| descending
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)

        # Identify variables that appear in NO high-correlation pair —
        # these are "safe" and should always be checked by default.
        vars_in_pairs = set()
        for va, vb, _ in pairs:
            vars_in_pairs.add(va); vars_in_pairs.add(vb)
        self._safe_vars = set(vars_) - vars_in_pairs  # stored for _rebuild_checklist

        if not pairs:
            self._safe_vars = set(vars_)
            self.pairs_info.setText(
                f"✔  No variable pairs exceed |r| ≥ {thr:.2f}.\n"
                "All variables can be safely used together.")
            self._safe_label.setVisible(False)
            return

        if self._safe_vars:
            names_str = ",  ".join(sorted(self._safe_vars))
            self._safe_label.setText(
                f"✔  {len(self._safe_vars)} variable(s) with NO high correlation "
                f"— auto-selected:\n{names_str}")
            self._safe_label.setVisible(True)
        else:
            self._safe_label.setVisible(False)

        self.pairs_info.setText(
            f"Found {len(pairs)} pair(s) with |r| ≥ {thr:.2f}.  "
            "For each pair, keep the variable with higher AUC or ecological relevance.\n"
            "Click a row → both variables highlighted in checklist.  "
            "Use 'Uncheck Variable A/B' to quickly drop one.")

        # AUC lookup
        auc_map = {}
        if self._ranking_df is not None:
            for _, row in self._ranking_df.iterrows():
                auc_map[row["Variable"]] = row.get("Univariate_AUC", float("nan"))

        colors = _tc()

        for va, vb, r in pairs:
            row_idx = self.pairs_table.rowCount()
            self.pairs_table.insertRow(row_idx)

            auc_a = auc_map.get(va, float("nan"))
            auc_b = auc_map.get(vb, float("nan"))

            # Variable A — show AUC as hint
            label_a = f"{va}  (AUC={auc_a:.2f})" if auc_a == auc_a else va
            label_b = f"{vb}  (AUC={auc_b:.2f})" if auc_b == auc_b else vb

            item_a = QTableWidgetItem(label_a)
            item_b = QTableWidgetItem(label_b)

            # Colour: lower AUC → red hint (candidate to drop)
            if auc_a == auc_a and auc_b == auc_b:
                if auc_a < auc_b:
                    item_a.setForeground(colors["bad"])
                    item_b.setForeground(colors["ok"])
                elif auc_b < auc_a:
                    item_b.setForeground(colors["bad"])
                    item_a.setForeground(colors["ok"])
                else:
                    item_a.setForeground(colors["text"])
                    item_b.setForeground(colors["text"])
            else:
                item_a.setForeground(colors["text"])
                item_b.setForeground(colors["text"])

            item_a.setData(Qt.ItemDataRole.UserRole, va)   # raw name for lookup
            item_b.setData(Qt.ItemDataRole.UserRole, vb)

            # |r| value — colour by severity
            r_item = QTableWidgetItem(f"{abs(r):.3f}")
            r_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if abs(r) >= 0.95:
                r_item.setForeground(colors["bad"])
            elif abs(r) >= 0.85:
                r_item.setForeground(colors["warn"])
            else:
                r_item.setForeground(colors["neutral"])

            # Direction
            dir_item = QTableWidgetItem("+" if r > 0 else "−")
            dir_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            dir_item.setForeground(colors["bad"] if r > 0 else colors["warn"])

            self.pairs_table.setItem(row_idx, 0, item_a)
            self.pairs_table.setItem(row_idx, 1, item_b)
            self.pairs_table.setItem(row_idx, 2, r_item)
            self.pairs_table.setItem(row_idx, 3, dir_item)

            # Alternating background
            bg = _tc()["row_a"] if row_idx % 2 == 0 else _tc()["row_b"]
            for c in range(4):
                it = self.pairs_table.item(row_idx, c)
                if it: it.setBackground(bg)

    def _get_corr_matrix(self):
        """Return correlation matrix from cache or recompute."""
        import pandas as pd
        if self._corr_df is not None:
            return self._corr_df

        pa_datasets = self.dlg.state.get("pa_datasets")
        var_names   = self.dlg.state.get("var_names")
        if not pa_datasets or not var_names:
            return None
        try:
            from habitus.sdm_core import compute_correlation_matrix
            X_pool = pd.concat([ds[0] for ds in pa_datasets], ignore_index=True)
            X_clean = X_pool[var_names].dropna()
            self._corr_df = compute_correlation_matrix(
                X_clean, method=self.corr_method.currentText())
            return self._corr_df
        except Exception:
            return None

    # ══════════════════════════════════════════════════════════════════════
    # PAIR → CHECKLIST INTERACTION
    # ══════════════════════════════════════════════════════════════════════

    def _on_pair_selected(self):
        """Highlight both variables of the selected pair in the checklist."""
        rows = self.pairs_table.selectedItems()
        if not rows:
            return
        row_idx = self.pairs_table.currentRow()
        item_a  = self.pairs_table.item(row_idx, 0)
        item_b  = self.pairs_table.item(row_idx, 1)
        if not item_a or not item_b:
            return
        va = item_a.data(Qt.ItemDataRole.UserRole) or item_a.text().split("  ")[0]
        vb = item_b.data(Qt.ItemDataRole.UserRole) or item_b.text().split("  ")[0]
        self._highlight_vars({va, vb})

    def _highlight_vars(self, names: set):
        """Highlight the checkbox frames of the given variable names with a clear pastel border."""
        for vname, chk in self._var_checks.items():
            frame = chk.parent()
            if frame:
                if vname in names:
                    # Highlighted: bold orange border + warm pastel background
                    frame.setStyleSheet(
                        "QFrame#var_frame { border:3px solid #e8a046; "
                        "background:#fff4dc; border-radius:5px; margin:1px; }")
                else:
                    # Default pastel sage style
                    frame.setStyleSheet(
                        "QFrame#var_frame { background:#f5faf7; border:1px solid #c4ddd0; "
                        "border-radius:4px; margin:1px; }")

    def _drop_pair_var(self, col: int):
        """Uncheck variable A (col=0) or B (col=1) of the selected pair."""
        row_idx = self.pairs_table.currentRow()
        if row_idx < 0:
            self.dlg.show_error("Select a pair row first."); return
        item = self.pairs_table.item(row_idx, col)
        if not item: return
        vname = item.data(Qt.ItemDataRole.UserRole) or item.text().split("  ")[0]
        if vname in self._var_checks:
            self._var_checks[vname].setChecked(False)
        self._update_selection_label()

    def _on_thr_changed(self):
        """Refresh pairs table when threshold slider changes."""
        if self._corr_df is not None:
            self._populate_pairs()
            self._plot_heatmap()

    # ══════════════════════════════════════════════════════════════════════
    # BULK SELECTION HELPERS
    # ══════════════════════════════════════════════════════════════════════

    def _select_all(self):
        for chk in self._var_checks.values():
            chk.setChecked(True)
        self._update_selection_label()

    def _deselect_all(self):
        for chk in self._var_checks.values():
            chk.setChecked(False)
        self._update_selection_label()

    def _select_recommended(self):
        if self._ranking_df is None:
            return
        rec = set(self._ranking_df[self._ranking_df["Recommended"]]["Variable"].tolist())
        safe = getattr(self, "_safe_vars", set())
        for vname, chk in self._var_checks.items():
            # Safe vars (no high correlation with anything) are always included
            chk.setChecked(vname in rec or vname in safe)
        self._update_selection_label()

    def _get_selected_vars(self):
        return [v for v, chk in self._var_checks.items() if chk.isChecked()]

    def _update_selection_label(self):
        sel = self._get_selected_vars()
        if sel:
            self.selection_label.setText(
                f"Selected ({len(sel)}): {', '.join(sel)}")
        else:
            self.selection_label.setText("No variables selected.")

    # ══════════════════════════════════════════════════════════════════════
    # HEATMAP
    # ══════════════════════════════════════════════════════════════════════

    def _plot_heatmap(self):
        if not HAS_MPL:
            return
        corr = self._get_corr_matrix()
        if corr is None:
            return

        import matplotlib.colors as mcolors
        import matplotlib.patches as patches

        var_names = list(corr.columns)
        n = len(var_names)
        thr = self.corr_thr.value()

        self.heatmap_fig.clear()
        ax = self.heatmap_fig.add_subplot(111)
        ax.set_facecolor("#F8F8F8")

        cmap = matplotlib.colormaps.get_cmap("RdYlGn")
        norm = mcolors.TwoSlopeNorm(vmin=-1, vcenter=0, vmax=1)
        im   = ax.imshow(corr.values, cmap=cmap, norm=norm, aspect="auto")

        ax.set_xticks(range(n)); ax.set_yticks(range(n))
        ax.set_xticklabels(var_names, rotation=45, ha="right",
                            fontsize=9, color="#1a1a1a")
        ax.set_yticklabels(var_names, fontsize=9, color="#1a1a1a")

        # Cell annotations
        for i in range(n):
            for j in range(n):
                val = corr.values[i, j]
                tc  = "#1a1a1a" if abs(val) > 0.6 else "#333333"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=max(5, min(8, 72 // n)), color=tc)

        # Highlight pairs above threshold with orange border
        for i in range(n):
            for j in range(n):
                if i != j and abs(corr.values[i, j]) >= thr:
                    rect = patches.Rectangle(
                        (j - 0.5, i - 0.5), 1, 1,
                        linewidth=2, edgecolor="#d4820a", facecolor="none")
                    ax.add_patch(rect)

        cb = self.heatmap_fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cb.ax.tick_params(colors="#1a1a1a", labelsize=8)

        method = self.corr_method.currentText().capitalize()
        ax.set_title(
            f"{method} Correlation  |  orange border = |r| ≥ {thr:.2f}",
            color="#1a5c3a", fontsize=9, pad=6)

        self.heatmap_fig.patch.set_facecolor("white")
        self.heatmap_fig.tight_layout()
        self.heatmap_canvas.draw()
        try:
            self._save_figure(self.heatmap_fig, "correlation_heatmap")
        except Exception as _e:
            self.dlg.log(f"Heatmap save failed: {_e}")

    # ══════════════════════════════════════════════════════════════════════
    # PNG EXPORT
    # ══════════════════════════════════════════════════════════════════════

    def _get_output_dir(self):
        """Output klasörünü döndür; yoksa oluştur."""
        import os
        out = self.dlg.state.get("output_dir", "")
        if not out:
            return None
        path = os.path.join(out, "figures")
        os.makedirs(path, exist_ok=True)
        return path

    def _save_figure(self, fig, name: str):
        """Figure'ü output/figures/<name>.png olarak kaydet."""
        import os
        out_dir = self._get_output_dir()
        if out_dir is None:
            return
        fpath = os.path.join(out_dir, f"{name}.png")
        try:
            fig.savefig(fpath, dpi=300, bbox_inches="tight",
                        facecolor=fig.get_facecolor())
            self.dlg.log(f"Saved: {fpath}")
        except Exception as e:
            self.dlg.log(f"Could not save {name}.png: {e}")

    def _save_pairs_csv(self):
        """High-correlation pairs tablosunu CSV olarak kaydet."""
        import os, csv
        out_dir = self._get_output_dir()
        if out_dir is None:
            return
        corr = self._get_corr_matrix()
        if corr is None:
            return
        thr = self.corr_thr.value()
        vars_ = list(corr.columns)
        auc_map = {}
        if self._ranking_df is not None:
            for _, row in self._ranking_df.iterrows():
                auc_map[row["Variable"]] = row.get("Univariate_AUC", float("nan"))

        fpath = os.path.join(out_dir, "high_correlation_pairs.csv")
        rows = [["Variable_A", "Variable_B", "Correlation_r", "AUC_A", "AUC_B",
                 "Direction", "Recommend_drop"]]
        for i in range(len(vars_)):
            for j in range(i + 1, len(vars_)):
                r = corr.iloc[i, j]
                if abs(r) >= thr:
                    va, vb = vars_[i], vars_[j]
                    auc_a  = auc_map.get(va, float("nan"))
                    auc_b  = auc_map.get(vb, float("nan"))
                    # Recommend dropping the one with lower AUC
                    if auc_a == auc_a and auc_b == auc_b:
                        drop = va if auc_a < auc_b else vb
                    else:
                        drop = ""
                    rows.append([va, vb, f"{r:.4f}",
                                 f"{auc_a:.4f}" if auc_a == auc_a else "",
                                 f"{auc_b:.4f}" if auc_b == auc_b else "",
                                 "positive" if r > 0 else "negative",
                                 drop])
        try:
            with open(fpath, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(rows)
            self.dlg.log(f"Saved: {fpath}")
        except Exception as e:
            self.dlg.log(f"Could not save high_correlation_pairs.csv: {e}")

    def _save_priority_csv(self):
        """Priority ranking tablosunu CSV olarak kaydet."""
        import os
        if self._ranking_df is None:
            return
        out_dir = self._get_output_dir()
        if out_dir is None:
            return
        fpath = os.path.join(out_dir, "variable_priority_ranking.csv")
        try:
            self._ranking_df.to_csv(fpath, index=False)
            self.dlg.log(f"Saved: {fpath}")
        except Exception as e:
            self.dlg.log(f"Could not save variable_priority_ranking.csv: {e}")

    def _save_vif_barplot(self):
        """VIF değerlerini bar grafik olarak kaydet."""
        if not HAS_MPL or self._ranking_df is None:
            return
        import matplotlib.pyplot as plt
        import numpy as np

        df = self._ranking_df.sort_values("VIF", ascending=True)
        n  = len(df)
        fig, ax = plt.subplots(figsize=(8, max(4, n * 0.35)))
        fig.patch.set_facecolor("white")
        ax.set_facecolor("#F8F8F8")

        thr = self.vif_thr.value()
        # Work with numeric VIF values throughout — build labels separately
        vif_raw    = [float(v) if v == v else 0.0 for v in df["VIF"]]
        colors_bar = ["#c0392b" if (v >= thr or v >= 999) else "#1a8c5a"
                      for v in vif_raw]
        vif_vals   = [min(v, 50.0) for v in vif_raw]   # cap bar length at 50
        labels     = []
        for v in vif_raw:
            if v >= 999:
                labels.append("∞  (near-perfect collinearity)")
            elif v > 50:
                labels.append(f"{v:.1f}  (>50, capped)")
            elif v != v:     # NaN
                labels.append("—")
            else:
                labels.append(f"{v:.1f}")

        bars = ax.barh(df["Variable"], vif_vals, color=colors_bar, alpha=0.85)
        ax.axvline(thr, color="#d4820a", lw=1.5, ls="--",
                   label=f"VIF threshold ({thr:.0f})")
        ax.axvline(10,  color="#c0392b",  lw=0.8, ls=":",
                   label="VIF=10 (severe, O'Brien 2007)")

        for bar, lbl in zip(bars, labels):
            ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                    lbl, va="center", ha="left", fontsize=9, color="#1a1a1a")

        ax.set_xlabel("VIF  (display capped at 50)", color="#1a1a1a")
        ax.set_title(f"Variance Inflation Factor  |  threshold={thr:.0f}",
                     color="#1a5c3a", fontsize=11)
        ax.tick_params(colors="#1a1a1a")
        for sp in ax.spines.values(): sp.set_color("#CCCCCC"); sp.set_linewidth(0.8)
        leg = ax.legend(facecolor="white", edgecolor="#CCCCCC", fontsize=9)
        if leg:
            for text in leg.get_texts():
                text.set_color("#1a1a1a")
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#CCCCCC", linewidth=0.6,
                linestyle="--", alpha=0.7)
        fig.tight_layout()
        try:
            self._save_figure(fig, "vif_barplot")
        except Exception as _e:
            self.dlg.log(f"VIF barplot save failed: {_e}")
        plt.close(fig)

    # ══════════════════════════════════════════════════════════════════════
    # CONFIRM
    # ══════════════════════════════════════════════════════════════════════

    def _confirm(self):
        selected = self._get_selected_vars()
        if not selected:
            self.dlg.show_error("Please select at least one variable."); return
        if len(selected) < 2:
            self.dlg.show_error(
                "At least 2 variables are needed for modelling.\n"
                "Please select more variables."); return

        # ── Only warn if models have actually been trained already ───────────
        has_modeler = self.dlg.state.get("modeler") is not None

        if has_modeler:
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "Re-confirm Variable Selection",
                "You have already run the model with a previous variable set.\n\n"
                "Confirming now will discard all existing models, maps, projections,\n"
                "and evaluation results so everything is recomputed from scratch.\n\n"
                "Proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self.dlg.reset_downstream()

        self.dlg.state["var_names"] = selected

        # ── Save all outputs to figures/ directory ────────────────────────
        self._save_pairs_csv()
        self._save_priority_csv()
        self._save_vif_barplot()
        self._save_selected_heatmap(selected)

        self.dlg.set_progress(
            f"Variables confirmed: {', '.join(f'[{v}]' for v in selected)}", 100)
        self.dlg.unlock_tab(self.dlg.TAB_MODELS)
        self.dlg.goto_tab(self.dlg.TAB_MODELS)
        self.dlg.tab_models.sub.setCurrentIndex(0)  # always open on Algorithm Settings

        out_dir = self._get_output_dir()
        saved_note = (f"\n\nFiles saved to:\n  {out_dir}" if out_dir else "")
        self.dlg.show_info(
            f"Variable selection confirmed.\n\n"
            f"Selected ({len(selected)}):\n  " + "\n  ".join(selected)
            + saved_note)

    def _save_selected_heatmap(self, selected):
        """Sadece seçilen değişkenlerin korelasyon matrisini PNG olarak kaydet."""
        if not HAS_MPL or self._corr_df is None or not selected:
            return
        import matplotlib.colors as mcolors
        import matplotlib.patches as patches

        corr = self._corr_df.loc[
            [v for v in selected if v in self._corr_df.columns],
            [v for v in selected if v in self._corr_df.columns]
        ]
        if corr.empty:
            return

        n   = len(corr)
        thr = self.corr_thr.value()
        import matplotlib.pyplot as _plt
        fig, ax = _plt.subplots(figsize=(max(6, n * 0.6 + 1), max(5, n * 0.6)))
        fig.patch.set_facecolor("white")
        ax.set_facecolor("#F8F8F8")

        cmap = matplotlib.colormaps.get_cmap("RdYlGn")
        norm = mcolors.TwoSlopeNorm(vmin=-1, vcenter=0, vmax=1)
        im   = ax.imshow(corr.values, cmap=cmap, norm=norm, aspect="auto")

        ax.set_xticks(range(n)); ax.set_yticks(range(n))
        ax.set_xticklabels(corr.columns, rotation=45, ha="right",
                            fontsize=max(7, min(10, 80 // n)), color="#1a1a1a")
        ax.set_yticklabels(corr.index, fontsize=max(7, min(10, 80 // n)),
                            color="#1a1a1a")
        for i in range(n):
            for j in range(n):
                val = corr.values[i, j]
                tc  = "#1a1a1a" if abs(val) > 0.6 else "#333333"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=max(6, min(9, 72 // n)), color=tc)
        for i in range(n):
            for j in range(n):
                if i != j and abs(corr.values[i, j]) >= thr:
                    ax.add_patch(patches.Rectangle(
                        (j-0.5, i-0.5), 1, 1,
                        lw=2, edgecolor="#d4820a", facecolor="none"))
        cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cb.ax.tick_params(colors="#1a1a1a", labelsize=8)
        method = self.corr_method.currentText().capitalize()
        ax.set_title(
            f"{method} Correlation Matrix — Selected Variables ({n})"
            f"  |  orange = |r| ≥ {thr:.2f}",
            color="#1a5c3a", fontsize=10, pad=8)
        fig.tight_layout()
        try:
            self._save_figure(fig, "correlation_heatmap_selected")
        except Exception as _e:
            self.dlg.log(f"Selected heatmap save failed: {_e}")
        import matplotlib.pyplot as _plt; _plt.close(fig)
