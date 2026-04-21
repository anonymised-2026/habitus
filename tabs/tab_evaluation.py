# -*- coding: utf-8 -*-
"""
Tab ⑥ – Evaluation & Visualisation

Sub-tabs:
  1. Model Scores   – ROC-AUC, TSS, Boyce per model (scatter + box + bar)
  2. ROC Curves     – actual ROC curve per algorithm
  3. Variable Imp.  – permutation importance bar chart
  4. Response Curves – 1-D marginal response per variable
  5. Boyce Detail   – F-ratio curve (Hirzel 2006)

Layer naming guide shown in header.
"""

import traceback, os
import numpy as np
import pandas as pd

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QComboBox, QGroupBox,
    QAbstractItemView, QHeaderView, QSizePolicy, QMessageBox,
    QTableWidget, QTableWidgetItem, QApplication, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette

try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigCanvas
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# ── Publication-quality light theme ────────────────────────────────────
DARK   = "#FFFFFF"   # figure background → white
PANEL  = "#F8F8F8"   # axes background → near-white
TICK   = "#1a1a1a"   # axis labels, ticks → near-black
GREEN  = "#1a8c5a"   # presence-only colour → dark green
YELLOW = "#d4820a"   # warning / moderate → amber
RED    = "#c0392b"   # poor / absent → dark red
ACCENT = "#1a5c3a"   # titles, highlights → dark forest green
GRID   = "#CCCCCC"   # grid lines, spines → light grey
METRICS = {"ROC": "#2471A3", "TSS": "#1a8c5a", "Boyce": "#d4820a"}

def _style_ax(ax):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=TICK, labelsize=9)
    for sp in ax.spines.values():
        sp.set_color(GRID); sp.set_linewidth(0.8)
    ax.yaxis.label.set_color(TICK); ax.xaxis.label.set_color(TICK)
    for lb in ax.get_xticklabels()+ax.get_yticklabels():
        lb.set_color(TICK); lb.set_fontsize(9)
    ax.grid(axis="y", color=GRID, linewidth=0.6, alpha=0.7, linestyle="--")
    ax.set_axisbelow(True)

def _make_canvas(fig):
    c = FigCanvas(fig); c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return c

def _make_scroll_canvas(fig):
    """Canvas wrapped in a QScrollArea — for variable-height multi-row figures."""
    canvas = FigCanvas(fig)
    canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(canvas)
    return scroll, canvas

def _set_fig_header(fig, main_title: str, species: str = ""):
    """Uniform header for every evaluation figure.

    Layout (figure-fraction coordinates, top→bottom):
      0.97  italic species name  (if present)
      0.92  bold main title
      0.88  top of plot area  ← tight_layout rect
    """
    if species:
        fig.text(0.5, 0.97, species,
                 ha="center", va="top",
                 fontsize=10, fontstyle="italic",
                 fontfamily="DejaVu Sans",
                 color=ACCENT, alpha=0.90)
    fig.suptitle(main_title, y=0.92,
                 color=ACCENT, fontsize=11, fontweight="bold",
                 fontfamily="DejaVu Sans")

def _resize_fig(fig, canvas, n_rows, n_cols=3,
                row_h=3.8, col_w=4.5, min_h=5.0):
    """Set figure size based on grid dimensions and update canvas minimum height."""
    w = col_w * n_cols
    h = max(min_h, row_h * n_rows)
    fig.set_size_inches(w, h)
    canvas.setMinimumHeight(int(h * fig.dpi))

def _theme_fg(role):
    from PyQt6.QtGui import QColor, QPalette
    bg = QApplication.instance().palette().color(QPalette.ColorRole.Window)
    dark = bg.lightness() < 128
    tbl = {"ok":("#52b788","#1a7a4a"),"warn":("#f6ad55","#b45309"),
           "bad":("#fc8181","#c0392b"),"neutral":("#74c69d","#0e6655")}
    d,l = tbl.get(role,("#888","#444")); return QColor(d if dark else l)


class EvaluationTab(QWidget):

    def __init__(self, main_dialog):
        super().__init__()
        self.dlg = main_dialog
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self); layout.setSpacing(8); layout.setContentsMargins(16,16,16,16)

        if not HAS_MPL:
            w = QLabel("matplotlib not installed.\nRun: pip install matplotlib  then restart QGIS.")
            w.setStyleSheet("color:#f6ad55;background:#2d2000;padding:14px;"
                            "border:1px solid #f6ad55;border-radius:6px;font-size:12px;")
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(w); layout.addStretch(); return

        # ── Layer naming legend ──────────────────────────────────────────
        legend = QLabel(
            "Layer name guide:  "
            "RF_PA1 = Random Forest, pseudo-absence set 1  |  "
            "MAXENT_PA2 = MaxEnt, PA set 2  |  "
            "EMwmean = Weighted-mean ensemble  |  "
            "EMca = Committee-averaging ensemble  |  "
            "_prob = suitability probability (0–1)  |  "
            "_bin = binary presence/absence map"
        )
        legend.setWordWrap(True)
        legend.setStyleSheet(
            "font-size:10px; padding:6px; border-radius:4px; border:1px solid palette(mid);")
        layout.addWidget(legend)

        self.sub = QTabWidget(); self.sub.setObjectName("sdm_tabs")
        layout.addWidget(self.sub, 1)

        self.sub.addTab(self._scores_tab(),     "Model Scores")
        self.sub.addTab(self._roc_tab(),        "ROC Curves")
        self.sub.addTab(self._omission_tab(),   "Omission & PR")
        self.sub.addTab(self._varimp_tab(),     "Variable Importance")
        self.sub.addTab(self._response_tab(),   "Response Curves")
        self.sub.addTab(self._boyce_tab(),      "Boyce Detail")
        self.sub.addTab(self._threshold_tab(),  "Classification Thresholds")

        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("↻  Refresh All Charts")
        btn_refresh.clicked.connect(self._refresh)
        btn_save = QPushButton("💾  Save All Charts to Output Folder")
        btn_save.setObjectName("btn_secondary")
        btn_save.setToolTip(
            "Save all evaluation charts as PNG files to the output/figures/ directory")
        btn_save.clicked.connect(self._save_all)
        btn_row.addWidget(btn_refresh); btn_row.addWidget(btn_save); btn_row.addStretch()
        layout.addLayout(btn_row)

    # ── 1. Model Scores ──────────────────────────────────────────────────

    def _scores_tab(self):
        w = QWidget(); v = QVBoxLayout(w)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Group by:"))
        self.sc_group = QComboBox(); self.sc_group.addItems(["Algorithm","PA Set","CV Run"])
        self.sc_group.currentIndexChanged.connect(self._plot_scores)
        ctrl.addWidget(self.sc_group)
        ctrl.addWidget(QLabel("Chart:"))
        self.sc_chart = QComboBox(); self.sc_chart.addItems(["Scatter + range","Box plot","Bar mean±SD"])
        self.sc_chart.currentIndexChanged.connect(self._plot_scores)
        ctrl.addWidget(self.sc_chart); ctrl.addStretch()
        v.addLayout(ctrl)

        self.sc_fig = Figure(facecolor=DARK); self.sc_canvas = _make_canvas(self.sc_fig)
        v.addWidget(self.sc_canvas, 1)
        return w

    def _plot_scores(self):
        m = self.dlg.state.get("modeler"); 
        if not m: return
        df = m.get_evaluations_df()
        if df.empty: return

        gcol = {"Algorithm":"Algorithm","PA Set":"PA_set","CV Run":"CV_run"}.get(
            self.sc_group.currentText(),"Algorithm")
        ctype = self.sc_chart.currentText()
        groups = sorted(df[gcol].unique())
        colors = plt.cm.Set2(np.linspace(0,1,max(len(groups),1)))

        self.sc_fig.clear()
        gs = gridspec.GridSpec(1, 3, wspace=0.38)

        for mi, metric in enumerate(["ROC","TSS","Boyce"]):
            ax = self.sc_fig.add_subplot(gs[0,mi]); _style_ax(ax)
            ax.set_title(metric, color=METRICS[metric], fontsize=11, fontweight="bold")
            ax.set_ylim(-0.15 if metric=="Boyce" else 0.3, 1.05)
            for gi,(grp,color) in enumerate(zip(groups,colors)):
                sub = df[df[gcol]==grp][metric].dropna()
                if sub.empty: continue
                if "Scatter" in ctype:
                    ax.scatter([gi]*len(sub),sub,color=color,alpha=0.7,s=40,zorder=3)
                    if len(sub)>1: ax.plot([gi,gi],[sub.min(),sub.max()],color=color,alpha=0.4,lw=1.5)
                    ax.scatter([gi],[sub.mean()],color=color,s=100,marker="D",
                               edgecolors="white",linewidth=0.8,zorder=5)
                elif "Box" in ctype:
                    bp = ax.boxplot(sub,positions=[gi],widths=0.5,patch_artist=True,showfliers=True)
                    bp["boxes"][0].set(facecolor=color,alpha=0.7)
                    for el in bp["medians"]: el.set(color="white",linewidth=2)
                    for el in bp["whiskers"]+bp["caps"]: el.set(color=color)
                else:
                    ax.bar(gi,sub.mean(),0.6,color=color,alpha=0.75,
                           yerr=sub.std() if len(sub)>1 else 0,
                           capsize=4,ecolor="white",error_kw={"linewidth":1.2})
            ax.set_xticks(range(len(groups)))
            ax.set_xticklabels(groups,rotation=30,ha="right",fontsize=8)
            if metric in ("ROC","TSS"):
                ax.axhline(0.8,color=GREEN,lw=0.8,ls="--",alpha=0.7)
                ax.axhline(0.6,color=YELLOW,lw=0.8,ls="--",alpha=0.7)
            else:
                ax.axhline(0.5,color=GREEN,lw=0.8,ls="--",alpha=0.7)
                ax.axhline(0.0,color="#888888",lw=0.8,alpha=0.8)

        self.sc_fig.patch.set_facecolor(DARK)
        # Use subplots_adjust instead of tight_layout: gives the subplot titles
        # ~10% clearance below the figure header (suptitle at y=0.92).
        self.sc_fig.subplots_adjust(top=0.80, bottom=0.22, left=0.06, right=0.97, wspace=0.45)
        _set_fig_header(self.sc_fig,
                        "Model Evaluation Scores  (ROC-AUC / TSS / Boyce Index)",
                        self.dlg.state.get("species_name", ""))
        self.sc_canvas.draw()
        self._save_fig(self.sc_fig, "evaluation_model_scores")

    # ── 2. ROC Curves ────────────────────────────────────────────────────

    def _roc_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        note = QLabel(
            "ROC curve — sensitivity vs 1−specificity at all thresholds.  "
            "AUC = 0.5 is random; 1.0 is perfect.  "
            "Solid = test set  |  Dashed = train set.  Scroll down to see all algorithms.")
        note.setWordWrap(True); note.setStyleSheet("font-size:10px;")
        v.addWidget(note)
        self.roc_fig = Figure(facecolor=DARK)
        scroll, self.roc_canvas = _make_scroll_canvas(self.roc_fig)
        v.addWidget(scroll, 1)
        return w

    def _plot_roc(self):
        m = self.dlg.state.get("modeler")
        pa_datasets = self.dlg.state.get("pa_datasets")
        if not m or not pa_datasets: return

        import pandas as pd
        from sklearn.metrics import roc_curve
        from sklearn.metrics import auc as sk_auc

        all_vars = m.var_names

        # ── Use CV models (RUN1, RUN2…) for honest ROC curves ───────────────
        # Full models are trained on 100% of data, so predicting on any
        # subset of that data gives inflated AUC (RF/XGB memorise training set).
        # CV models are trained on data_split% and evaluated on the REMAINING
        # held-out portion — these give unbiased AUC that matches the table.

        # {algo: [(fpr_tr, tpr_tr, auc_tr, fpr_te, tpr_te, auc_te), ...]}
        algo_roc_data = {}

        for pa_idx, ds in enumerate(pa_datasets):
            X_df, y_ds, _ = ds
            avail = [v for v in all_vars if v in X_df.columns]
            X_all = X_df[avail].fillna(0).values.astype(float)
            y_all = y_ds.astype(int)

            pa_label = f"PA{pa_idx+1}"
            cv_keys  = [k for k in m.fitted_models
                        if k[1] == pa_label and k[2] != "Full"]

            for key in cv_keys:
                algo, pa, run = key
                model = m.fitted_models.get(key)
                if model is None:
                    continue

                try:
                    run_idx = int(run.replace("RUN", "")) - 1
                except Exception:
                    run_idx = 0
                np.random.seed(run_idx * 100 + pa_idx)
                n    = len(y_all)
                n_tr = int(n * m.data_split / 100)
                idx  = np.random.permutation(n)
                tr, te = idx[:n_tr], idx[n_tr:]

                X_tr, y_tr = X_all[tr], y_all[tr]
                X_te, y_te = X_all[te], y_all[te]

                def _has_both(y):
                    return len(y) > 0 and y.sum() > 0 and (1 - y).sum() > 0

                if not _has_both(y_te):
                    continue

                try:
                    probs_te = m._predict(model, algo, X_te)
                    fpr_te, tpr_te, _ = roc_curve(y_te, probs_te)
                    auc_te = sk_auc(fpr_te, tpr_te)

                    fpr_tr = tpr_tr = None
                    auc_tr = float("nan")
                    if _has_both(y_tr):
                        probs_tr = m._predict(model, algo, X_tr)
                        fpr_tr, tpr_tr, _ = roc_curve(y_tr, probs_tr)
                        auc_tr = sk_auc(fpr_tr, tpr_tr)

                    algo_roc_data.setdefault(algo, []).append(
                        (fpr_tr, tpr_tr, auc_tr, fpr_te, tpr_te, auc_te))
                except Exception as e:
                    self.dlg.log(f"ROC plot error {key}: {e}")

        if not algo_roc_data:
            return

        algos  = list(algo_roc_data.keys())
        ncols  = min(len(algos), 3)
        nrows  = (len(algos) + ncols - 1) // ncols
        colors = plt.cm.Set2(np.linspace(0, 1, len(algos)))

        self.roc_fig.clear()
        for i, (algo, color) in enumerate(zip(algos, colors)):
            ax = self.roc_fig.add_subplot(nrows, ncols, i + 1)
            _style_ax(ax)
            curves = algo_roc_data[algo]

            auc_tr_vals = [c[2] for c in curves if c[0] is not None]
            auc_te_vals = [c[5] for c in curves]

            # Thin semi-transparent individual CV runs
            for fpr_tr, tpr_tr, _, fpr_te, tpr_te, _ in curves:
                if fpr_tr is not None:
                    ax.plot(fpr_tr, tpr_tr, color="#2471A3", alpha=0.25, lw=0.9)
                ax.plot(fpr_te, tpr_te, color=color, alpha=0.25, lw=0.9)

            # Thick representative (closest to mean) lines
            mean_te = float(np.mean(auc_te_vals))
            mid_te  = int(np.argmin(np.abs(np.array(auc_te_vals) - mean_te)))
            _, _, _, fpr_m, tpr_m, _ = curves[mid_te]
            ax.plot(fpr_m, tpr_m, color=color, lw=2.2,
                    label=f"Test AUC = {mean_te:.3f}")

            if auc_tr_vals:
                mean_tr = float(np.mean(auc_tr_vals))
                tr_curves = [(c[0], c[1], c[2]) for c in curves if c[0] is not None]
                mid_tr = int(np.argmin(np.abs(np.array(auc_tr_vals) - mean_tr)))
                fpr_tm, tpr_tm, _ = tr_curves[mid_tr]
                ax.plot(fpr_tm, tpr_tm, color="#2471A3", lw=2.2, ls="--",
                        label=f"Train AUC = {mean_tr:.3f}")

            ax.plot([0, 1], [0, 1], color="#888888", lw=0.8, ls=":")
            ax.set_xlabel("1 − Specificity", fontsize=10)
            ax.set_ylabel("Sensitivity", fontsize=10)
            ax.set_title(algo, color=ACCENT, fontsize=11, fontweight="bold", pad=10)
            ax.legend(facecolor="white", edgecolor=GRID, labelcolor=TICK, fontsize=9)
            ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)

        self.roc_fig.patch.set_facecolor(DARK)
        _resize_fig(self.roc_fig, self.roc_canvas, nrows, ncols, row_h=4.0, col_w=4.8)
        self.roc_fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.88])
        _set_fig_header(self.roc_fig,
                        "ROC Curves per Algorithm  —  Train (dashed blue) vs Test (solid)",
                        self.dlg.state.get("species_name", ""))
        self.roc_canvas.draw()
        self._save_fig(self.roc_fig, "evaluation_roc_curves")

    # ── 3. Omission Rate · Precision-Recall · Calibration ────────────────

    def _omission_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        note = QLabel(
            "Omission Rate: fraction of presences predicted below each threshold — "
            "lower is better.  "
            "Precision-Recall: AP (average precision) summarises the curve — "
            "higher is better.  "
            "Calibration: do predicted probabilities reflect actual occurrence rates?  "
            "Solid = test set  |  Dashed = train set.")
        note.setWordWrap(True)
        note.setStyleSheet("font-size:10px; padding:4px;")
        v.addWidget(note)
        self.om_fig = Figure(facecolor=DARK)
        scroll, self.om_canvas = _make_scroll_canvas(self.om_fig)
        v.addWidget(scroll, 1)
        return w

    def _plot_omission(self):
        m           = self.dlg.state.get("modeler")
        pa_datasets = self.dlg.state.get("pa_datasets")
        if not m or not pa_datasets:
            return

        from sklearn.metrics import precision_recall_curve, average_precision_score
        from sklearn.calibration import calibration_curve as sk_cal_curve

        all_vars = m.var_names

        # {algo: {"tr": [(y, probs),...], "te": [(y, probs),...]}}
        algo_data = {}

        for pa_idx, ds in enumerate(pa_datasets):
            X_df, y_ds, _ = ds
            avail = [v for v in all_vars if v in X_df.columns]
            X_all = X_df[avail].fillna(0).values.astype(float)
            y_all = y_ds.astype(int)
            pa_label = f"PA{pa_idx+1}"
            cv_keys  = [k for k in m.fitted_models
                        if k[1] == pa_label and k[2] != "Full"]

            for key in cv_keys:
                algo, pa, run = key
                model = m.fitted_models.get(key)
                if model is None:
                    continue
                try:
                    run_idx = int(run.replace("RUN", "")) - 1
                except Exception:
                    run_idx = 0
                np.random.seed(run_idx * 100 + pa_idx)
                n    = len(y_all)
                n_tr = int(n * m.data_split / 100)
                idx  = np.random.permutation(n)
                tr, te = idx[:n_tr], idx[n_tr:]

                def _ok(y): return len(y) > 0 and y.sum() > 0 and (1 - y).sum() > 0

                if not _ok(y_all[te]):
                    continue
                try:
                    entry = algo_data.setdefault(algo, {"tr": [], "te": []})
                    entry["te"].append((y_all[te], m._predict(model, algo, X_all[te])))
                    if _ok(y_all[tr]):
                        entry["tr"].append((y_all[tr], m._predict(model, algo, X_all[tr])))
                except Exception as e:
                    self.dlg.log(f"Omission/PR error {key}: {e}")

        if not algo_data:
            return

        algos      = list(algo_data.keys())
        n_algos    = len(algos)
        n_cols     = 3
        thresholds = np.linspace(0, 1, 101)
        c_set2     = plt.cm.Set2(np.linspace(0, 1, max(n_algos, 1)))

        self.om_fig.clear()

        for ai, (algo, algo_color) in enumerate(zip(algos, c_set2)):
            data = algo_data[algo]

            # ── Omission Rate ─────────────────────────────────────────
            ax_om = self.om_fig.add_subplot(n_algos, n_cols, ai * n_cols + 1)
            _style_ax(ax_om)

            for split, col, ls in [("te", algo_color, "-"), ("tr", "#2471A3", "--")]:
                if not data[split]:
                    continue
                y_s  = np.concatenate([p[0] for p in data[split]])
                pr_s = np.concatenate([p[1] for p in data[split]])
                pres = pr_s[y_s == 1]
                if len(pres) == 0:
                    continue
                om = np.array([(pres < t).mean() for t in thresholds])
                lbl = "Test" if split == "te" else "Train"
                ax_om.plot(thresholds, om, color=col, lw=2, ls=ls, label=lbl)

            ax_om.axvline(0.5, color="#888888", lw=0.8, ls=":")
            ax_om.set_xlabel("Threshold", fontsize=10); ax_om.set_ylabel("Omission Rate", fontsize=10)
            ax_om.set_title(f"{algo} — Omission Rate",
                            color=ACCENT, fontsize=10, fontweight="bold", pad=10)
            ax_om.set_xlim(0, 1); ax_om.set_ylim(-0.02, 1.02)
            ax_om.legend(facecolor="white", edgecolor=GRID, labelcolor=TICK, fontsize=9)

            # ── Precision-Recall ──────────────────────────────────────
            ax_pr = self.om_fig.add_subplot(n_algos, n_cols, ai * n_cols + 2)
            _style_ax(ax_pr)

            for split, col, ls in [("te", algo_color, "-"), ("tr", "#2471A3", "--")]:
                if not data[split]:
                    continue
                y_s  = np.concatenate([p[0] for p in data[split]])
                pr_s = np.concatenate([p[1] for p in data[split]])
                if y_s.sum() == 0:
                    continue
                prec, rec, _ = precision_recall_curve(y_s, pr_s)
                ap = average_precision_score(y_s, pr_s)
                lbl = f"{'Test' if split == 'te' else 'Train'}  AP={ap:.3f}"
                ax_pr.plot(rec, prec, color=col, lw=2, ls=ls, label=lbl)

            if data["te"]:
                baseline = np.concatenate([p[0] for p in data["te"]]).mean()
                ax_pr.axhline(baseline, color="#888888", lw=0.8, ls=":",
                              label=f"Baseline {baseline:.2f}")
            ax_pr.set_xlabel("Recall", fontsize=10); ax_pr.set_ylabel("Precision", fontsize=10)
            ax_pr.set_title(f"{algo} — Precision-Recall",
                            color=ACCENT, fontsize=10, fontweight="bold", pad=10)
            ax_pr.set_xlim(0, 1); ax_pr.set_ylim(0, 1.05)
            ax_pr.legend(facecolor="white", edgecolor=GRID, labelcolor=TICK, fontsize=9)

            # ── Calibration ───────────────────────────────────────────
            ax_cal = self.om_fig.add_subplot(n_algos, n_cols, ai * n_cols + 3)
            _style_ax(ax_cal)

            for split, col, ls in [("te", algo_color, "-"), ("tr", "#2471A3", "--")]:
                if not data[split]:
                    continue
                y_s  = np.concatenate([p[0] for p in data[split]])
                pr_s = np.concatenate([p[1] for p in data[split]])
                if y_s.sum() == 0 or (1 - y_s).sum() == 0:
                    continue
                try:
                    n_bins = max(5, min(10, len(y_s) // 30))
                    frac, mean_p = sk_cal_curve(y_s, pr_s, n_bins=n_bins)
                    lbl = "Test" if split == "te" else "Train"
                    ax_cal.plot(mean_p, frac, color=col, lw=2, ls=ls,
                                marker="o", ms=4, label=lbl)
                except Exception:
                    pass

            ax_cal.plot([0, 1], [0, 1], color="#888888", lw=0.8, ls=":", label="Perfect")
            ax_cal.set_xlabel("Mean Predicted Prob.", fontsize=10)
            ax_cal.set_ylabel("Fraction of Presences", fontsize=10)
            ax_cal.set_title(f"{algo} — Calibration",
                             color=ACCENT, fontsize=10, fontweight="bold", pad=10)
            ax_cal.set_xlim(0, 1); ax_cal.set_ylim(0, 1.05)
            ax_cal.legend(facecolor="white", edgecolor=GRID, labelcolor=TICK, fontsize=9)

        self.om_fig.patch.set_facecolor(DARK)
        _resize_fig(self.om_fig, self.om_canvas, n_algos, n_cols=3, row_h=4.0, col_w=4.8)
        self.om_fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.88])
        _set_fig_header(self.om_fig,
                        "Predictive Performance  —  Omission Rate  ·  Precision-Recall  ·  Calibration"
                        "  (solid = test,  dashed = train)",
                        self.dlg.state.get("species_name", ""))
        self.om_canvas.draw()
        self._save_fig(self.om_fig, "evaluation_omission_pr_calibration")

    # ── 4. Variable Importance ───────────────────────────────────────────

    def _varimp_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.vi_fig = Figure(facecolor=DARK); self.vi_canvas = _make_canvas(self.vi_fig)
        v.addWidget(self.vi_canvas, 1)
        return w

    def _plot_varimp(self):
        m = self.dlg.state.get("modeler")
        if not m: return
        try:
            df = m.get_variable_importance_df()
        except Exception as e:
            self.dlg.log(f"Variable importance error: {e}")
            return
        if df is None or df.empty: return
        # Importance sütunu sayısal olmalı
        import pandas as pd
        df["Importance"] = pd.to_numeric(df["Importance"], errors="coerce")
        df = df.dropna(subset=["Importance"])
        if df.empty: return

        mean_imp = df.groupby(["Algorithm","Variable"])["Importance"].mean().unstack(0)
        n_algo = len(mean_imp.columns); n_var = len(mean_imp.index)
        x = np.arange(n_var); width = 0.8/max(n_algo,1)
        colors = plt.cm.Set2(np.linspace(0,1,n_algo))

        self.vi_fig.clear()
        ax = self.vi_fig.add_subplot(111); _style_ax(ax)
        for i,(algo,col) in enumerate(mean_imp.items()):
            ax.bar(x+i*width, col.values, width*0.9, label=algo, color=colors[i], alpha=0.85)
        ax.set_xticks(x+width*(n_algo-1)/2)
        ax.set_xticklabels(mean_imp.index, rotation=35, ha="right")
        ax.set_ylabel("Mean Permutation Importance", fontsize=10)
        ax.set_xlabel("Variable", fontsize=10)
        ax.legend(facecolor="white", edgecolor=GRID, labelcolor=TICK, fontsize=9)
        self.vi_fig.patch.set_facecolor(DARK)
        self.vi_fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.88])
        _set_fig_header(self.vi_fig,
                        "Variable Importance by Algorithm",
                        self.dlg.state.get("species_name", ""))
        self.vi_canvas.draw()
        self._save_fig(self.vi_fig, "evaluation_variable_importance")

    # ── 4. Response Curves ───────────────────────────────────────────────

    def _response_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Algorithm:"))
        self.resp_cb = QComboBox(); ctrl.addWidget(self.resp_cb)
        ctrl.addWidget(QLabel("Method:"))
        self.resp_method = QComboBox()
        self.resp_method.addItems([
            "marginal  (median-hold, fast)",
            "partial   (PDP – Friedman 2001, rigorous)",
            "ice       (ICE – Goldstein 2015, per-sample)",
        ])
        self.resp_method.setToolTip(
            "marginal: vary 1 variable, hold others at median (biomod2 style)\n"
            "partial:  PDP — average over real covariate distribution (slower, more rigorous)\n"
            "ice:      ICE — per-sample curves, reveals interactions")
        ctrl.addWidget(self.resp_method)
        btn = QPushButton("Plot"); btn.setObjectName("btn_secondary")
        btn.clicked.connect(self._plot_response); ctrl.addWidget(btn); ctrl.addStretch()
        v.addLayout(ctrl)
        self.resp_fig = Figure(facecolor=DARK)
        scroll, self.resp_canvas = _make_scroll_canvas(self.resp_fig)
        v.addWidget(scroll, 1)
        return w

    def _plot_response(self):
        m = self.dlg.state.get("modeler")
        pa = self.dlg.state.get("pa_datasets")
        vn = self.dlg.state.get("var_names") or []
        if not m or not pa: return
        algo = self.resp_cb.currentText(); 
        if not algo: return
        method_str = self.resp_method.currentText().split()[0]
        # Use cont_var_names for response curves (interpretable)
        resp_vars = getattr(m, "cont_var_names", vn) or vn
        try:
            from habitus.sdm_core import compute_response_curves
            curves = compute_response_curves(m, pa, resp_vars, method=method_str)
        except Exception as _e:
            self.dlg.log(f"Response curves failed: {_e}")
            return
        if not curves or algo not in curves or not curves.get(algo):
            self.dlg.log(f"No response curves for {algo} — skipping.")
            return
        ac = curves[algo]; n = len(ac)
        if n == 0:
            self.dlg.log(f"Response curves empty for {algo}.")
            return
        ncols = min(n,3); nrows = (n+ncols-1)//ncols
        self.resp_fig.clear()
        for i,(vname,(x,ymean,ysd)) in enumerate(ac.items()):
            ax = self.resp_fig.add_subplot(nrows,ncols,i+1); _style_ax(ax)
            is_cat = vname.startswith("_cat_")
            display_name = vname[5:] if is_cat else vname
            if is_cat:
                # Bar chart for categorical variable
                bars = ax.bar(np.arange(len(x)), ymean,
                              color=ACCENT, alpha=0.75, edgecolor="white", linewidth=0.5)
                ax.errorbar(np.arange(len(x)), ymean, yerr=ysd,
                            fmt="none", color=TICK, capsize=3, linewidth=1)
                ax.set_xticks(np.arange(len(x)))
                ax.set_xticklabels([str(int(v)) for v in x],
                                   rotation=45, ha="right", fontsize=7)
                ax.set_xlabel("Class", fontsize=10, color=TICK)
                ax.set_ylabel("Mean suitability", fontsize=10, color=TICK)
                ax.set_ylim(0, 1)
                ax.set_title(display_name, color=ACCENT, fontsize=10, fontweight="bold", pad=10)
                continue  # skip the line-plot block below
            ax.plot(x, ymean, color=GREEN, lw=2)
            ax.fill_between(x, np.clip(ymean-ysd,0,1), np.clip(ymean+ysd,0,1),
                            color=GREEN, alpha=0.2)
            ax.set_ylim(0, 1)
            ax.set_xlabel(display_name, fontsize=10)
            ax.set_ylabel("Suitability", fontsize=10)
            ax.set_title(display_name, color=ACCENT, fontsize=10, fontweight="bold", pad=10)
        self.resp_fig.patch.set_facecolor(DARK)
        _resize_fig(self.resp_fig, self.resp_canvas, nrows, ncols, row_h=4.0, col_w=4.8)
        self.resp_fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.88])
        _set_fig_header(self.resp_fig,
                        f"{algo} – Response Curves",
                        self.dlg.state.get("species_name", ""))
        self.resp_canvas.draw()
        # Save combined multi-panel figure
        self._save_fig(self.resp_fig, f"evaluation_response_{algo}")

    # ── 5. Boyce Detail ──────────────────────────────────────────────────

    def _boyce_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Algorithm:")); self.bx_algo = QComboBox(); ctrl.addWidget(self.bx_algo)
        ctrl.addWidget(QLabel("PA set:"));   self.bx_pa   = QComboBox(); ctrl.addWidget(self.bx_pa)
        btn = QPushButton("Plot Boyce"); btn.setObjectName("btn_secondary")
        btn.clicked.connect(self._plot_boyce); ctrl.addWidget(btn); ctrl.addStretch()
        v.addLayout(ctrl)
        info = QLabel("CBI > 0.5 = good model (monotone ↑ F-ratio)  |  CBI ≈ 0 = random  |  CBI < 0 = counter-useful")
        info.setStyleSheet("font-size:10px; padding:4px; border-radius:4px; border:1px solid palette(mid);")
        v.addWidget(info)
        self.bx_fig = Figure(facecolor=DARK); self.bx_canvas = _make_canvas(self.bx_fig)
        v.addWidget(self.bx_canvas, 1)
        return w

    def _plot_boyce(self):
        m  = self.dlg.state.get("modeler")
        pa = self.dlg.state.get("pa_datasets")
        vn = self.dlg.state.get("var_names") or []
        if not m or not pa: return
        algo   = self.bx_algo.currentText()
        pa_sel = self.bx_pa.currentText()
        if not algo: return

        import pandas as pd
        from habitus.sdm_core import compute_boyce_index
        X_pool   = pd.concat([ds[0] for ds in pa], ignore_index=True)
        y_pool   = np.concatenate([ds[1] for ds in pa])
        all_vars = m.var_names
        avail    = [v for v in all_vars if v in X_pool.columns]
        X_arr    = X_pool[avail].fillna(0).values.astype(float)
        y_arr    = y_pool[:len(X_arr)].astype(int)

        keys = [(a,p,r) for (a,p,r) in m.fitted_models
                if a==algo and (not pa_sel or pa_sel=="(all)" or p==pa_sel) and r!="Full"]
        if not keys: return

        ncols = min(len(keys),3); nrows = (len(keys)+ncols-1)//ncols
        colors = plt.cm.Set1(np.linspace(0,1,len(keys)))
        self.bx_fig.clear()
        for ki,(key,color) in enumerate(zip(keys,colors)):
            model = m.fitted_models[key]
            try:
                probs = m._predict(model,key[0],X_arr)
                b = compute_boyce_index(y_arr,probs)
                ax = self.bx_fig.add_subplot(nrows,ncols,ki+1); _style_ax(ax)
                ax.plot(b["bin_centers"],b["F_ratio"],color=color,lw=2,marker="o",markersize=3)
                ax.axhline(1.0,color="#888888",lw=1.0,ls="--",alpha=0.8)
                ax.fill_between(b["bin_centers"],1.0,b["F_ratio"],
                                where=b["F_ratio"]>=1.0,color=color,alpha=0.15)
                cbi = b["boyce"]
                cbi_str = f"{cbi:.3f}" if cbi==cbi else "N/A"
                cc = GREEN if cbi==cbi and cbi>=0.5 else YELLOW if cbi==cbi and cbi>=0 else RED
                ax.set_title(f"{key[0]}  {key[1]}  {key[2]}  —  CBI = {cbi_str}",
                             color=cc, fontsize=10, fontweight="bold", pad=8)
                ax.set_xlabel("Predicted suitability", fontsize=10)
                ax.set_ylabel("Obs / Exp  (F-ratio)", fontsize=10)
            except Exception: pass
        self.bx_fig.patch.set_facecolor(DARK)
        _resize_fig(self.bx_fig, self.bx_canvas, nrows, ncols, row_h=4.0, col_w=4.8)
        self.bx_fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.88])
        _set_fig_header(self.bx_fig,
                        f"Boyce Index – {algo}",
                        self.dlg.state.get("species_name", ""))
        self.bx_canvas.draw()
        self._save_fig(self.bx_fig, f"evaluation_boyce_{algo}")

    # ── Refresh ──────────────────────────────────────────────────────────

    def _refresh(self):
        if not HAS_MPL: return
        m = self.dlg.state.get("modeler")
        if not m: return
        algos   = m.algorithms
        pa_sets = sorted(set(k[1] for k in m.fitted_models))

        # Populate dropdowns
        for cb in [self.resp_cb, self.bx_algo]:
            cur = cb.currentText(); cb.clear(); cb.addItems(algos)
            if cur in algos: cb.setCurrentText(cur)
            elif algos: cb.setCurrentIndex(0)
        self.bx_pa.clear(); self.bx_pa.addItem("(all)"); self.bx_pa.addItems(pa_sets)

        # Plot all charts
        self._plot_scores()
        self._plot_roc()
        self._plot_omission()
        self._plot_varimp()
        # Auto-plot response curves for first algorithm
        if algos:
            self.resp_cb.setCurrentIndex(0)
            self._plot_response()
        # Auto-plot Boyce for first algorithm
        if algos:
            self.bx_algo.setCurrentIndex(0)
            self._plot_boyce()
        # Populate thresholds
        self._populate_thresholds()

    # ══════════════════════════════════════════════════════════════════════
    # PNG EXPORT
    # ══════════════════════════════════════════════════════════════════════

    def _get_output_dir(self):
        import os
        out = self.dlg.state.get("output_dir", "")
        if not out:
            return None
        path = os.path.join(out, "figures")
        os.makedirs(path, exist_ok=True)
        return path

    def _save_fig(self, fig, name: str):
        """Figure'ü output/figures/<name>.png olarak 200 dpi kaydet."""
        import os
        out_dir = self._get_output_dir()
        if out_dir is None:
            self.dlg.log("Output directory not set — cannot save figure.")
            return
        fpath = os.path.join(out_dir, f"{name}.png")
        try:
            fig.savefig(fpath, dpi=300, bbox_inches="tight",
                        facecolor=fig.get_facecolor())
            self.dlg.log(f"Saved: {fpath}")
        except Exception as e:
            self.dlg.log(f"Could not save {name}.png: {e}")

    def _save_all(self):
        """Tüm evaluation grafiklerini PNG olarak kaydet — progress dialog ile."""
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt

        if not HAS_MPL:
            self.dlg.show_error("matplotlib required for saving figures."); return
        m = self.dlg.state.get("modeler")
        if not m:
            self.dlg.show_error("Run models first (③ Models)."); return

        algos = sorted(set(k[0] for k in m.fitted_models if k[2] != "Full"))
        # Steps: 4 combined plots + (response + boyce) per algo + CSV
        total_steps = 4 + len(algos) * 2 + 1

        prog = QProgressDialog("Saving evaluation charts…", "Cancel", 0, total_steps, self)
        prog.setWindowTitle("Saving…")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)
        QApplication.processEvents()

        def _step(label):
            if prog.wasCanceled():
                return False
            prog.setLabelText(label)
            prog.setValue(prog.value() + 1)
            QApplication.processEvents()
            return True

        # ── Combined charts ──────────────────────────────────────────────
        if not _step("Rendering Model Scores…"): return
        self._plot_scores()
        self._save_fig(self.sc_fig, "evaluation_model_scores")

        if not _step("Rendering ROC Curves…"): return
        self._plot_roc()
        self._save_fig(self.roc_fig, "evaluation_roc_curves")

        if not _step("Rendering Omission / PR / Calibration…"): return
        self._plot_omission()
        self._save_fig(self.om_fig, "evaluation_omission_pr_calibration")

        if not _step("Rendering Variable Importance…"): return
        self._plot_varimp()
        self._save_fig(self.vi_fig, "evaluation_variable_importance")

        # ── Per-algorithm: response + boyce ──────────────────────────────
        saved_algos = []
        original_algo = self.resp_cb.currentText()
        for algo in algos:
            if not _step(f"Response curves — {algo}…"): break
            idx = self.resp_cb.findText(algo)
            if idx >= 0:
                self.resp_cb.setCurrentIndex(idx)
                self._plot_response()
                self._save_fig(self.resp_fig, f"evaluation_response_{algo}")

            if not _step(f"Boyce index — {algo}…"): break
            self._plot_boyce()
            self._save_fig(self.bx_fig, f"evaluation_boyce_{algo}")
            saved_algos.append(algo)

        idx = self.resp_cb.findText(original_algo)
        if idx >= 0:
            self.resp_cb.setCurrentIndex(idx)

        # ── CSV ──────────────────────────────────────────────────────────
        if not prog.wasCanceled():
            _step("Saving evaluation_scores.csv…")
            self._save_scores_csv()

        prog.setValue(total_steps)

        if prog.wasCanceled():
            self.dlg.log("Save cancelled by user.")
            return

        out_dir = self._get_output_dir()
        algo_str = ", ".join(saved_algos) or "none"
        self.dlg.show_info(
            f"All evaluation figures saved to:\n{out_dir}\n\n"
            f"Combined plots: model_scores, roc_curves, omission_pr_calibration, variable_importance\n"
            f"Per-algorithm: response + boyce for {algo_str}\n"
            f"Individual response curves: figures/response_curves/\n"
            f"evaluation_scores.csv")

    def _save_scores_csv(self):
        """Save evaluation scores CSV including ensemble (EMwmean, EMca) metrics."""
        import os
        import pandas as pd
        m = self.dlg.state.get("modeler")
        if not m: return
        out_dir = self._get_output_dir()
        if not out_dir: return
        fpath = os.path.join(out_dir, "evaluation_scores.csv")
        try:
            df = m.get_evaluations_df()

            # Compute ensemble metrics from the prob rasters + test data
            ens_rows = self._compute_ensemble_scores(out_dir)
            if ens_rows:
                ens_df = pd.DataFrame(ens_rows)
                df = pd.concat([df, ens_df], ignore_index=True)

            df.to_csv(fpath, index=False)
            self.dlg.log(f"Saved: {fpath}")
        except Exception as e:
            self.dlg.log(f"Could not save evaluation_scores.csv: {e}")

    def _compute_ensemble_scores(self, out_dir):
        """Compute ROC-AUC, TSS and Boyce for EMwmean and EMca ensemble
        rasters using the held-out test occurrence points."""
        import os
        import numpy as np
        import pandas as pd

        # Load test occurrences
        csv_dir = os.path.join(out_dir, "..", "csv") if not os.path.exists(
            os.path.join(out_dir, "occurrence_test.csv")) else out_dir
        # Search for occurrence_test.csv in likely locations
        test_path = None
        for candidate in [
            os.path.join(out_dir, "..", "csv", "occurrence_test.csv"),
            os.path.join(out_dir, "..", "occurrence_test.csv"),
            os.path.join(out_dir, "occurrence_test.csv"),
        ]:
            if os.path.isfile(candidate):
                test_path = candidate; break

        if test_path is None:
            # Try to find it anywhere under the parent of out_dir
            parent = os.path.dirname(out_dir)
            for root, dirs, files in os.walk(parent):
                if "occurrence_test.csv" in files:
                    test_path = os.path.join(root, "occurrence_test.csv"); break

        if test_path is None:
            self.dlg.log("  EMwmean/EMca scores skipped: occurrence_test.csv not found.")
            return []

        test = pd.read_csv(test_path)
        if "longitude" not in test.columns or "presence" not in test.columns:
            return []

        y_true = test["presence"].values.astype(int)
        lons = test["longitude"].values
        lats = test["latitude"].values

        results = []
        # Check for ensemble prob rasters in current/ subfolder
        current_dir = os.path.join(out_dir, "current") if os.path.isdir(
            os.path.join(out_dir, "current")) else out_dir

        for ens_name in ["EMwmean", "EMca"]:
            # Find the ensemble prob raster
            prob_path = None
            for fname in os.listdir(current_dir):
                if ens_name in fname and fname.endswith("_prob.tif"):
                    prob_path = os.path.join(current_dir, fname); break

            if prob_path is None:
                # Try parent directory
                parent = os.path.dirname(out_dir)
                for root, dirs, files in os.walk(parent):
                    for fname in files:
                        if ens_name in fname and fname.endswith("_prob.tif"):
                            prob_path = os.path.join(root, fname); break
                    if prob_path: break

            if prob_path is None:
                continue

            try:
                import rasterio
                with rasterio.open(prob_path) as src:
                    data = src.read(1).astype(float)
                    transform = src.transform
                    nd = src.nodata
                    if nd is not None:
                        data[data == nd] = np.nan

                # Extract predictions at test locations
                probs = []
                yt = []
                for lon, lat, y in zip(lons, lats, y_true):
                    col, row = ~transform * (lon, lat)
                    row, col = int(row), int(col)
                    if 0 <= row < data.shape[0] and 0 <= col < data.shape[1]:
                        val = data[row, col]
                        if np.isfinite(val):
                            probs.append(val)
                            yt.append(y)

                probs = np.array(probs)
                yt = np.array(yt)

                if len(probs) < 10 or yt.sum() < 2:
                    continue

                # ROC-AUC
                from sklearn.metrics import roc_auc_score
                roc = float(roc_auc_score(yt, probs))

                # TSS (max over thresholds)
                best_tss = 0.0
                for thr in np.linspace(0.01, 0.99, 200):
                    pred = (probs >= thr).astype(int)
                    tp = ((pred == 1) & (yt == 1)).sum()
                    fn = ((pred == 0) & (yt == 1)).sum()
                    tn = ((pred == 0) & (yt == 0)).sum()
                    fp = ((pred == 1) & (yt == 0)).sum()
                    sens = tp / (tp + fn) if (tp + fn) > 0 else 0
                    spec = tn / (tn + fp) if (tn + fp) > 0 else 0
                    tss = sens + spec - 1
                    if tss > best_tss:
                        best_tss = tss

                # Boyce Index
                from scipy.stats import spearmanr
                window = 0.1
                centers = np.linspace(0, 1, 101)
                ratios, valid_c = [], []
                for c in centers:
                    lo = max(0, c - window / 2)
                    hi = min(1, c + window / 2)
                    mask_all = (probs >= lo) & (probs <= hi)
                    mask_pres = mask_all & (yt == 1)
                    n_all = mask_all.sum()
                    if n_all > 0:
                        frac = n_all / len(probs)
                        exp = frac * yt.sum()
                        if exp > 0:
                            ratios.append(mask_pres.sum() / exp)
                            valid_c.append(c)
                boyce = float(spearmanr(valid_c, ratios)[0]) if len(valid_c) >= 3 else np.nan

                results.append({
                    "Algorithm": ens_name,
                    "PA_set": "Ensemble",
                    "CV_run": "Full",
                    "ROC": roc,
                    "TSS": best_tss,
                    "Boyce": round(boyce, 4),
                })
                self.dlg.log(f"  {ens_name}: ROC={roc:.4f}  TSS={best_tss:.4f}  Boyce={boyce:.4f}")

            except Exception as e:
                self.dlg.log(f"  {ens_name} score computation failed: {e}")

        return results

    # ══════════════════════════════════════════════════════════════════════
    # CLASSIFICATION THRESHOLDS TAB
    # ══════════════════════════════════════════════════════════════════════

    def _threshold_tab(self):
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QHeaderView,
            QAbstractItemView, QGroupBox, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QComboBox
        )
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(5,5,5,5); v.setSpacing(6)

        info = QLabel(
            "Optimal binary classification thresholds for converting probability maps (0-1) ""to presence/absence maps. ""Each method uses a different statistical criterion. Choose based on your objective.")
        info.setWordWrap(True); info.setStyleSheet("font-size:10px;")
        v.addWidget(info)

        # Method legend
        legend_grp = QGroupBox("Threshold Methods")
        leg_layout = QVBoxLayout(legend_grp)
        for method, desc in [
            ("max_tss",      "Maximise TSS (Sensitivity + Specificity − 1). "
                             "Prevalence-independent. Recommended for SDM. [Allouche 2006]"),
            ("max_kappa",    "Maximise Cohen's Kappa. "
                             "Prevalence-sensitive. [Fielding & Bell 1997]"),
            ("sens_spec_eq", "Equal Sensitivity & Specificity. "
                             "Use when omission = commission error. [Liu 2005]"),
            ("p10",          "10th percentile of presence predictions. "
                             "Minimal predicted area. Recommended for MaxEnt. [Pearson 2007]"),
            ("min_roi",      "Minimum distance to perfect ROC point (0,1). "
                             "Threshold-independent of prevalence."),
        ]:
            lbl = QLabel(f"  <b>{method}</b>: {desc}")
            lbl.setWordWrap(True); lbl.setStyleSheet("font-size:10px;")
            leg_layout.addWidget(lbl)
        v.addWidget(legend_grp)

        # Threshold table
        self.thr_table = QTableWidget(0, 8)
        self.thr_table.setHorizontalHeaderLabels([
            "Algorithm", "PA Set",
            "max_tss", "max_kappa", "sens_spec_eq", "p10", "min_roi",
            "Used (current)"
        ])
        hdr = self.thr_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(2, 8):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        self.thr_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.thr_table.setAlternatingRowColors(True)
        v.addWidget(self.thr_table, 1)

        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("↻  Compute All Thresholds")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.clicked.connect(self._populate_thresholds)
        btn_save = QPushButton("💾  Save Threshold Table (CSV)")
        btn_save.clicked.connect(self._save_threshold_csv)
        btn_row.addWidget(btn_refresh); btn_row.addWidget(btn_save); btn_row.addStretch()
        v.addLayout(btn_row)
        return w

    def _populate_thresholds(self):
        """Tüm Full modeller için 5 farklı yöntemle threshold hesapla."""
        m  = self.dlg.state.get("modeler")
        pa = self.dlg.state.get("pa_datasets")
        if not m or not pa:
            self.dlg.log("Run models first."); return

        import pandas as pd
        from habitus.sdm_core import find_optimal_threshold

        X_pool   = pd.concat([ds[0] for ds in pa], ignore_index=True)
        y_pool   = np.concatenate([ds[1] for ds in pa])
        all_vars = m.var_names
        avail    = [v for v in all_vars if v in X_pool.columns]
        X_arr    = X_pool[avail].fillna(0).values.astype(float)
        y_arr    = y_pool[:len(X_arr)].astype(int)

        methods = ["max_tss", "max_kappa", "sens_spec_eq", "p10", "min_roi"]
        colors  = {
            "max_tss":      "#52b788",
            "max_kappa":    "#74c69d",
            "sens_spec_eq": "#f6ad55",
            "p10":          "#63b3ed",
            "min_roi":      "#b794f4",
        }

        self.thr_table.setRowCount(0)
        self._threshold_data = []   # store for CSV export

        for key, model in sorted(m.fitted_models.items()):
            algo, pa_set, run = key
            if run != "Full": continue
            try:
                probs = m._predict(model, algo, X_arr)
                row = self.thr_table.rowCount()
                self.thr_table.insertRow(row)

                self.thr_table.setItem(row, 0, QTableWidgetItem(algo))
                self.thr_table.setItem(row, 1, QTableWidgetItem(pa_set))

                row_data = {"Algorithm": algo, "PA_set": pa_set}
                used_thr = m.tss_thresholds.get(key, 0.5)

                for ci, method in enumerate(methods, start=2):
                    thr, val = find_optimal_threshold(y_arr, probs, method=method)
                    cell_text = f"{thr:.4f}  (metric={val:.3f})"
                    item = QTableWidgetItem(cell_text)
                    from PyQt6.QtGui import QColor
                    item.setForeground(QColor(colors[method]))
                    item.setToolTip(
                        f"Threshold: {thr:.4f}\n"
                        f"Metric value: {val:.4f}\n"
                        f"pixel >= {thr:.4f} -> Present (1)\n"
                        f"pixel <  {thr:.4f} -> Absent  (0)")
                    self.thr_table.setItem(row, ci, item)
                    row_data[method] = round(thr, 4)

                # Currently used threshold
                used_item = QTableWidgetItem(f"{used_thr:.4f}")
                from PyQt6.QtGui import QColor
                used_item.setForeground(QColor("#f6ad55"))
                used_item.setToolTip(
                    f"This is the threshold used for the current binary map.\n"
                    f"Method: {getattr(m, 'threshold_method', 'max_tss')}")
                self.thr_table.setItem(row, 7, used_item)
                row_data["used"] = round(used_thr, 4)
                row_data["method_used"] = getattr(m, "threshold_method", "max_tss")
                self._threshold_data.append(row_data)

            except Exception as e:
                self.dlg.log(f"Threshold compute error for {key}: {e}")

        self.dlg.log(f"Thresholds computed for {self.thr_table.rowCount()} models.")

    def _save_threshold_csv(self):
        """Threshold tablosunu CSV olarak kaydet."""
        import csv, os
        out_base = self.dlg.state.get("output_dir","")
        if not out_base:
            self.dlg.show_error("Output directory not set."); return
        os.makedirs(out_base, exist_ok=True)
        fpath = os.path.join(out_base, "figures", "classification_thresholds.csv")
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        data = getattr(self, "_threshold_data", [])
        if not data:
            self._populate_thresholds()
            data = getattr(self, "_threshold_data", [])
        if not data:
            self.dlg.log("No threshold data to save."); return
        try:
            cols = ["Algorithm","PA_set","max_tss","max_kappa",
                    "sens_spec_eq","p10","min_roi","used","method_used"]
            with open(fpath,"w",newline="",encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader(); w.writerows(data)
            self.dlg.log(f"Saved: {fpath}")
        except Exception as e:
            self.dlg.log(f"Could not save thresholds: {e}")

    def showEvent(self, event):
        super().showEvent(event)
        if not HAS_MPL: return
        m = self.dlg.state.get("modeler")
        if not m: return
        # Sadece stat grafikleri güncelle — response/boyce kullanıcı isteğiyle çalışır
        algos   = m.algorithms
        pa_sets = sorted(set(k[1] for k in m.fitted_models))
        for cb in [self.resp_cb, self.bx_algo]:
            cur = cb.currentText(); cb.clear(); cb.addItems(algos)
            if cur in algos: cb.setCurrentText(cur)
            elif algos: cb.setCurrentIndex(0)
        self.bx_pa.clear()
        self.bx_pa.addItem("(all)"); self.bx_pa.addItems(pa_sets)
        self._plot_scores()
        self._plot_roc()
        self._plot_omission()
        self._plot_varimp()
        self._populate_thresholds()
