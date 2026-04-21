# -*- coding: utf-8 -*-
"""
Advanced Multicollinearity Analysis:
  - Condition Number (overall multicollinearity severity)
  - PCA (variance explained + loadings)
  - LASSO (L1 regularisation — embedded variable selection)
  - Ridge Regression (L2 — coefficient shrinkage)

Used as a sub-tab inside the Variables page to complement VIF + correlation.
All methods operate on the same PA dataset pool as the VIF tab.
"""

import warnings
import numpy as np
import pandas as pd

# Suppress sklearn coordinate descent convergence warnings from LASSO
# (inherent to coordinate descent; does not indicate a problem)
try:
    from sklearn.exceptions import ConvergenceWarning
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
except Exception:
    pass

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QTabWidget, QGroupBox, QComboBox, QDoubleSpinBox, QSpinBox,
    QSizePolicy, QFormLayout, QMessageBox,
)
from PyQt6.QtCore import Qt

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigCanvas
    from matplotlib.figure import Figure
    HAS_MPL = True
except Exception:
    HAS_MPL = False


def _style_ax(ax):
    ax.set_facecolor("#ffffff")
    ax.tick_params(colors="#1c3328", labelsize=9)
    for sp in ax.spines.values():
        sp.set_color("#b8d4c4")
    ax.grid(True, alpha=0.3, color="#c4ddd0")


# ══════════════════════════════════════════════════════════════════════════════
# Advanced Analysis Widget
# ══════════════════════════════════════════════════════════════════════════════

class AdvancedAnalysisTab(QWidget):
    """Advanced multicollinearity / regularisation analyses."""

    def __init__(self, main_dialog, parent=None):
        super().__init__(parent)
        self.dlg = main_dialog
        self._X = None
        self._y = None
        self._var_names = []
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        info = QLabel(
            "These analyses complement VIF + correlation by providing alternative "
            "perspectives on multicollinearity and variable importance: Condition "
            "Number gives a single severity score, PCA reveals variable groupings, "
            "LASSO performs automatic variable selection, and Ridge shows coefficient "
            "shrinkage under L2 regularisation."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "padding:8px; border-radius:5px; background:#eef7f2; "
            "color:#1d5235; font-size:11px; border:1px solid #b8d4c4;"
        )
        root.addWidget(info)

        # Run + Save buttons
        run_row = QHBoxLayout()
        self._btn_run = QPushButton("Run All Analyses")
        self._btn_run.setStyleSheet(
            "background:#3a8c60;color:#fff;font-weight:bold;"
            "padding:8px 24px;border-radius:4px;font-size:11pt;"
        )
        self._btn_run.clicked.connect(self._run_all)
        run_row.addWidget(self._btn_run)

        self._btn_save = QPushButton("Save All Results...")
        self._btn_save.setStyleSheet(
            "background:#2a6e45;color:#fff;font-weight:bold;"
            "padding:8px 24px;border-radius:4px;font-size:11pt;"
        )
        self._btn_save.setToolTip("Export all plots (PNG) and tables (CSV) "
                                  "to the analysis folder.")
        self._btn_save.clicked.connect(self._save_all)
        self._btn_save.setEnabled(False)
        run_row.addWidget(self._btn_save)

        self._status = QLabel("Waiting for data...")
        self._status.setStyleSheet("color:#3a7050; font-style:italic;")
        run_row.addWidget(self._status)
        run_row.addStretch()
        root.addLayout(run_row)

        # Sub-tabs for each method
        self._inner = QTabWidget()
        self._inner.setObjectName("sdm_tabs")

        self._tab_condition = self._make_condition_tab()
        self._tab_pca       = self._make_pca_tab()
        self._tab_lasso     = self._make_lasso_tab()
        self._tab_ridge     = self._make_ridge_tab()

        self._inner.addTab(self._tab_condition, "Condition Number")
        self._inner.addTab(self._tab_pca,       "PCA")
        self._inner.addTab(self._tab_lasso,     "LASSO (L1)")
        self._inner.addTab(self._tab_ridge,     "Ridge (L2)")

        root.addWidget(self._inner, 1)

    def _make_condition_tab(self):
        w = QWidget(); lo = QVBoxLayout(w)
        self._cond_label = QLabel(
            "<p style='color:#666; font-style:italic;'>"
            "Run analysis to compute condition number.</p>"
        )
        self._cond_label.setTextFormat(Qt.TextFormat.RichText)
        self._cond_label.setWordWrap(True)
        self._cond_label.setStyleSheet(
            "background:#ffffff; padding:20px; border:1px solid #b8d4c4; "
            "border-radius:6px; font-size:12pt;"
        )
        lo.addWidget(self._cond_label)
        lo.addStretch()
        return w

    def _make_pca_tab(self):
        w = QWidget(); lo = QVBoxLayout(w)

        if HAS_MPL:
            self._pca_fig = Figure(figsize=(9, 5), facecolor="#ffffff")
            self._pca_canvas = FigCanvas(self._pca_fig)
            self._pca_canvas.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            lo.addWidget(self._pca_canvas, 2)

        self._pca_table = QTableWidget(0, 0)
        self._pca_table.setMinimumHeight(180)
        self._pca_table.setAlternatingRowColors(True)
        self._pca_table.setStyleSheet(
            "QTableWidget { background:#f5faf7; gridline-color:#c4ddd0; "
            "border:1px solid #b8d4c4; }"
            "QTableWidget::item { background:#ffffff; color:#1c3328; padding:4px; }"
            "QTableWidget::item:alternate { background:#eef7f2; }"
            "QHeaderView::section { background:#d4ead9; color:#1d5235; "
            "padding:4px; border:1px solid #b8d4c4; font-weight:bold; }"
        )
        lo.addWidget(self._pca_table, 1)
        return w

    def _make_lasso_tab(self):
        w = QWidget(); lo = QVBoxLayout(w)

        # Settings
        s = QHBoxLayout()
        s.addWidget(QLabel("Alpha (regularisation strength):"))
        self._lasso_alpha = QDoubleSpinBox()
        self._lasso_alpha.setRange(0.0001, 10.0)
        self._lasso_alpha.setValue(0.01)
        self._lasso_alpha.setDecimals(4)
        self._lasso_alpha.setSingleStep(0.001)
        self._lasso_alpha.setToolTip("Higher alpha = more shrinkage = fewer variables")
        s.addWidget(self._lasso_alpha)
        self._lasso_cv = QSpinBox(); self._lasso_cv.setRange(3, 10); self._lasso_cv.setValue(5)
        s.addWidget(QLabel("CV folds for auto-alpha:"))
        s.addWidget(self._lasso_cv)
        btn = QPushButton("Recompute")
        btn.clicked.connect(self._run_lasso_only)
        s.addWidget(btn); s.addStretch()
        lo.addLayout(s)

        if HAS_MPL:
            self._lasso_fig = Figure(figsize=(9, 4), facecolor="#ffffff")
            self._lasso_canvas = FigCanvas(self._lasso_fig)
            lo.addWidget(self._lasso_canvas, 2)

        self._lasso_table = QTableWidget(0, 0)
        self._lasso_table.setMinimumHeight(160)
        self._lasso_table.setAlternatingRowColors(True)
        self._lasso_table.setStyleSheet(
            "QTableWidget { background:#f5faf7; gridline-color:#c4ddd0; "
            "border:1px solid #b8d4c4; }"
            "QTableWidget::item { background:#ffffff; color:#1c3328; padding:4px; }"
            "QTableWidget::item:alternate { background:#eef7f2; }"
            "QHeaderView::section { background:#d4ead9; color:#1d5235; "
            "padding:4px; border:1px solid #b8d4c4; font-weight:bold; }"
        )
        lo.addWidget(self._lasso_table, 1)
        return w

    def _make_ridge_tab(self):
        w = QWidget(); lo = QVBoxLayout(w)

        if HAS_MPL:
            self._ridge_fig = Figure(figsize=(9, 4), facecolor="#ffffff")
            self._ridge_canvas = FigCanvas(self._ridge_fig)
            lo.addWidget(self._ridge_canvas, 2)

        self._ridge_table = QTableWidget(0, 0)
        self._ridge_table.setMinimumHeight(160)
        self._ridge_table.setAlternatingRowColors(True)
        self._ridge_table.setStyleSheet(
            "QTableWidget { background:#f5faf7; gridline-color:#c4ddd0; "
            "border:1px solid #b8d4c4; }"
            "QTableWidget::item { background:#ffffff; color:#1c3328; padding:4px; }"
            "QTableWidget::item:alternate { background:#eef7f2; }"
            "QHeaderView::section { background:#d4ead9; color:#1d5235; "
            "padding:4px; border:1px solid #b8d4c4; font-weight:bold; }"
        )
        lo.addWidget(self._ridge_table, 1)
        return w

    # ── Data extraction ───────────────────────────────────────────────────

    def _get_data(self):
        """Build X, y from PA datasets, dropping zero-variance and NaN columns."""
        pa_datasets = self.dlg.state.get("pa_datasets")
        formatter   = self.dlg.state.get("formatter")
        var_names   = self.dlg.state.get("var_names") or \
                      (formatter.var_names if formatter else None)

        if not pa_datasets or not var_names:
            return None, None, []

        X_pool = pd.concat([ds[0] for ds in pa_datasets], ignore_index=True)
        y_pool = np.concatenate([ds[1] for ds in pa_datasets]).astype(int)

        # Keep only requested variables, drop NaN rows
        X = X_pool[var_names].dropna()
        y = y_pool[X.index.values] if len(X) != len(y_pool) else y_pool[:len(X)]

        # Drop zero-variance (constant) columns
        stds = X.std()
        kept = [v for v in var_names if stds.get(v, 0) > 1e-10]
        dropped = [v for v in var_names if v not in kept]
        if dropped:
            self.dlg.log(f"Advanced: dropped zero-variance columns: {dropped}")

        X = X[kept]
        return X.values, y, kept

    # ── Main runner ───────────────────────────────────────────────────────

    def _run_all(self):
        X, y, names = self._get_data()
        if X is None:
            QMessageBox.warning(self, "No data",
                "Please run the Data step first and confirm variables.")
            return
        self._X, self._y, self._var_names = X, y, names
        n, p = X.shape
        self._status.setText(f"Data: {n} samples × {p} variables — running...")
        self.dlg.log(f"Advanced analysis: {n} samples, {p} variables")

        try:
            self._compute_condition()
            self._pca_result = self._compute_pca()
            self._lasso_result = self._compute_lasso()
            self._ridge_result = self._compute_ridge()
            self._status.setText(
                f"Analysis complete — {n} samples × {p} variables.")
            self.dlg.log("Advanced multicollinearity analysis complete.")
            self._btn_save.setEnabled(True)
        except Exception as e:
            self._status.setText(f"Error: {e}")
            QMessageBox.critical(self, "Analysis Error", str(e))

    def _run_lasso_only(self):
        if self._X is None:
            self._run_all(); return
        try:
            self._compute_lasso()
        except Exception as e:
            QMessageBox.critical(self, "LASSO Error", str(e))

    # ── Condition Number ──────────────────────────────────────────────────

    def _compute_condition(self):
        from sklearn.preprocessing import StandardScaler
        Xs = StandardScaler().fit_transform(self._X)
        # Condition number = ratio of max to min singular value of scaled X
        sv = np.linalg.svd(Xs, compute_uv=False)
        sv = sv[sv > 1e-10]
        if len(sv) == 0 or len(sv) < len(self._var_names):
            # Near-singular — some variables are (nearly) linearly dependent
            kappa = float(sv.max() / max(sv.min(), 1e-10))
            note_extra = (" Note: some variables are near-collinear "
                         "(likely including encoded categorical columns).")
        else:
            kappa = float(sv.max() / sv.min())
            note_extra = ""

        if kappa < 30:
            sev = "LOW"; color = "#1a7a4a"
            note = "Multicollinearity is not a concern. Your variable set is well conditioned."
            action = "No action needed. Proceed with current variable selection."
        elif kappa < 100:
            sev = "MODERATE"; color = "#b45309"
            note = "Moderate multicollinearity detected."
            action = ("Interpret individual coefficients with caution. "
                     "Consider removing the most correlated pairs via VIF + Correlation tab.")
        elif kappa < 1000:
            sev = "SEVERE"; color = "#c0392b"
            note = "Severe multicollinearity — some variables carry redundant information."
            action = ("<b>Recommended actions:</b><br>"
                    "1. Go to VIF + Correlation tab and drop one variable from each highly correlated pair.<br>"
                    "2. Use <b>LASSO (L1)</b> tab below — it automatically selects a non-redundant subset.<br>"
                    "3. Or use <b>PCA</b> tab to pick variables with the highest loading on each component.")
        else:
            sev = "NEAR-SINGULAR"; color = "#8b0000"
            note = ("Design matrix is near-singular — at least two variables are almost "
                   "perfectly linearly dependent. <b>This is expected if you kept all 19 "
                   "bioclimatic variables (bio_1…bio_19)</b> — they are mathematically derived "
                   "from each other (e.g. bio_7 = bio_5 − bio_6).")
            action = (
                "<b>This is not a bug — your variable set is over-specified.</b> "
                "Huge κ values are normal when all WorldClim bio variables are kept.<br><br>"
                "<b>Recommended steps:</b><br>"
                "1. Go to <b>VIF + Correlation</b> tab, set correlation threshold to <b>0.70</b>, "
                "and drop one variable from each highly correlated pair.<br>"
                "2. Typically <b>5–7 bio variables</b> are enough (e.g. bio_1, bio_4, bio_5, "
                "bio_12, bio_15, bio_18 + Elevation).<br>"
                "3. Re-run this analysis — κ should drop to the 50–200 range.<br>"
                "4. Alternatively, use <b>LASSO</b> below — it performs automatic selection "
                "and will keep only the most informative subset.")
        if note_extra:
            note += note_extra
        self._last_kappa = kappa
        self._last_sv = sv

        self._cond_label.setText(
            f"<div style='text-align:center;'>"
            f"<h2 style='color:#1d5235; margin:8px 0;'>Condition Number (κ)</h2>"
            f"<div style='font-size:36pt; font-weight:bold; color:{color}; margin:10px 0;'>"
            f"{kappa:,.2f}</div>"
            f"<div style='font-size:15pt; font-weight:bold; color:{color}; margin:6px 0;'>"
            f"{sev}</div>"
            f"<p style='color:#1c3328; font-size:11pt; max-width:700px; "
            f"margin:12px auto;'>{note}</p>"
            f"<div style='background:#fff4dc; border-left:4px solid #e8a046; "
            f"padding:10px 16px; margin:16px auto; max-width:700px; "
            f"text-align:left; border-radius:0 6px 6px 0;'>"
            f"<p style='color:#5c3a00; font-size:10.5pt; margin:0;'>"
            f"<b>What should you do?</b><br>{action}</p>"
            f"</div>"
            f"<hr style='border:none; border-top:1px solid #c4ddd0; margin:16px 0;'>"
            f"<p style='color:#3a7050; font-size:10pt; font-style:italic;'>"
            f"<b>Belsley et al. (1980) thresholds:</b> "
            f"κ &lt; 30: weak &nbsp;|&nbsp; "
            f"30–100: moderate &nbsp;|&nbsp; "
            f"100–1000: severe &nbsp;|&nbsp; "
            f"&gt; 1000: near-singular</p>"
            f"</div>"
        )

    # ── PCA ───────────────────────────────────────────────────────────────

    def _compute_pca(self):
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler

        Xs = StandardScaler().fit_transform(self._X)
        pca = PCA()
        pca.fit(Xs)

        var_ratio = pca.explained_variance_ratio_
        cum_var   = np.cumsum(var_ratio)
        loadings  = pca.components_  # shape: (n_components, n_features)

        # Plot: scree + cumulative
        if HAS_MPL:
            self._pca_fig.clear()
            ax1 = self._pca_fig.add_subplot(121)
            ax2 = self._pca_fig.add_subplot(122)

            n_show = min(len(var_ratio), 15)
            idx = np.arange(1, n_show + 1)
            ax1.bar(idx, var_ratio[:n_show] * 100, color="#3a8c60", edgecolor="#1d5235")
            ax1.set_title("Variance Explained per Component", fontsize=10, color="#1d5235")
            ax1.set_xlabel("Principal Component", fontsize=9)
            ax1.set_ylabel("% Variance", fontsize=9)
            _style_ax(ax1)

            ax2.plot(idx, cum_var[:n_show] * 100, marker="o",
                     color="#3a8c60", markerfacecolor="#e8a046")
            ax2.axhline(80, color="#c0392b", linestyle="--", alpha=0.6,
                        label="80% threshold")
            ax2.set_title("Cumulative Variance Explained", fontsize=10, color="#1d5235")
            ax2.set_xlabel("Number of Components", fontsize=9)
            ax2.set_ylabel("Cumulative % Variance", fontsize=9)
            ax2.legend(fontsize=8)
            _style_ax(ax2)

            self._pca_fig.tight_layout()
            self._pca_canvas.draw()

        # Table: loadings for first K components (K such that cumvar >= 80%)
        k = int(np.searchsorted(cum_var, 0.80)) + 1
        k = max(2, min(k, 8))

        # Recommended variables: pick the variable with the largest |loading|
        # on each of the first k components. This gives a non-redundant subset.
        recommended = set()
        dominant_on_pc = [None] * k
        for j in range(k):
            i_max = int(np.argmax(np.abs(loadings[j])))
            recommended.add(self._var_names[i_max])
            dominant_on_pc[j] = self._var_names[i_max]

        self._pca_table.setRowCount(len(self._var_names))
        self._pca_table.setColumnCount(k + 2)
        headers = ["Variable"] + [f"PC{i+1} ({var_ratio[i]*100:.1f}%)"
                                  for i in range(k)] + ["Status"]
        self._pca_table.setHorizontalHeaderLabels(headers)

        from PyQt6.QtGui import QColor, QFont

        for i, vname in enumerate(self._var_names):
            is_rec = vname in recommended
            name_item = QTableWidgetItem(vname)
            if is_rec:
                f = QFont(); f.setBold(True); name_item.setFont(f)
                name_item.setForeground(QColor("#1d5235"))
                name_item.setBackground(QColor("#d4edda"))
            self._pca_table.setItem(i, 0, name_item)

            for j in range(k):
                val = loadings[j, i]
                cell = QTableWidgetItem(f"{val:+.3f}")
                # Highlight the dominant cell on each PC
                if self._var_names[i] == dominant_on_pc[j]:
                    f = QFont(); f.setBold(True); cell.setFont(f)
                    cell.setBackground(QColor("#b8e0c8"))
                    cell.setForeground(QColor("#1d5235"))
                elif abs(val) > 0.4:
                    cell.setBackground(QColor("#fff4dc"))
                self._pca_table.setItem(i, j + 1, cell)

            # Status column
            if is_rec:
                st = QTableWidgetItem("RECOMMENDED")
                st.setBackground(QColor("#d4edda"))
                st.setForeground(QColor("#1d5235"))
                f = QFont(); f.setBold(True); st.setFont(f)
            else:
                st = QTableWidgetItem("redundant")
                st.setForeground(QColor("#999"))
            self._pca_table.setItem(i, k + 1, st)

        self._pca_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)

        self._pca_recommended = list(recommended)
        return {"var_ratio": var_ratio, "cum_var": cum_var,
                "loadings": loadings, "k": k, "recommended": list(recommended)}

    # ── LASSO ─────────────────────────────────────────────────────────────

    def _compute_lasso(self):
        from sklearn.linear_model import LassoCV, Lasso
        from sklearn.preprocessing import StandardScaler

        Xs = StandardScaler().fit_transform(self._X)
        y  = self._y

        # Fit LassoCV to find optimal alpha
        alphas = np.logspace(-4, 1, 50)
        try:
            lcv = LassoCV(alphas=alphas, cv=self._lasso_cv.value(),
                          max_iter=50000).fit(Xs, y)
            best_alpha = float(lcv.alpha_)
        except Exception:
            best_alpha = 0.01

        # Fit at user-selected alpha
        user_alpha = float(self._lasso_alpha.value())
        lasso = Lasso(alpha=user_alpha, max_iter=50000).fit(Xs, y)
        coefs = lasso.coef_
        selected = [self._var_names[i] for i in range(len(coefs)) if abs(coefs[i]) > 1e-8]

        # Coefficient path plot
        if HAS_MPL:
            self._lasso_fig.clear()
            ax = self._lasso_fig.add_subplot(111)
            coefs_path = []
            for a in alphas:
                m = Lasso(alpha=a, max_iter=20000).fit(Xs, y)
                coefs_path.append(m.coef_)
            coefs_path = np.array(coefs_path)
            for i, vname in enumerate(self._var_names):
                ax.plot(alphas, coefs_path[:, i], lw=1.2, label=vname)
            ax.set_xscale("log")
            ax.axvline(user_alpha, color="#e8a046", linestyle="--", lw=2,
                       label=f"user α = {user_alpha}")
            ax.axvline(best_alpha, color="#c0392b", linestyle=":", lw=2,
                       label=f"CV best α = {best_alpha:.4f}")
            ax.set_xlabel("Alpha (regularisation strength)", fontsize=9)
            ax.set_ylabel("Coefficient value", fontsize=9)
            ax.set_title(f"LASSO Coefficient Paths ({len(selected)}/{len(coefs)} variables selected at user α)",
                         fontsize=10, color="#1d5235")
            _style_ax(ax)
            if len(self._var_names) <= 12:
                ax.legend(fontsize=7, loc="best", ncol=2)
            self._lasso_fig.tight_layout()
            self._lasso_canvas.draw()

        # Table: coefficients
        rows = [(v, c) for v, c in zip(self._var_names, coefs)]
        rows.sort(key=lambda r: -abs(r[1]))

        self._lasso_table.setRowCount(len(rows))
        self._lasso_table.setColumnCount(3)
        self._lasso_table.setHorizontalHeaderLabels(["Variable", "Coefficient", "Status"])

        from PyQt6.QtGui import QColor, QFont
        for i, (vname, c) in enumerate(rows):
            selected = abs(c) > 1e-8
            name_item = QTableWidgetItem(vname)
            coef_item = QTableWidgetItem(f"{c:+.4f}")
            if selected:
                f = QFont(); f.setBold(True)
                name_item.setFont(f); coef_item.setFont(f)
                name_item.setForeground(QColor("#1d5235"))
                name_item.setBackground(QColor("#d4edda"))
                coef_item.setBackground(QColor("#d4edda"))
                st = QTableWidgetItem("SELECTED")
                st.setBackground(QColor("#d4edda"))
                st.setForeground(QColor("#1d5235"))
                st.setFont(f)
            else:
                st = QTableWidgetItem("dropped")
                st.setBackground(QColor("#f8d7da"))
                st.setForeground(QColor("#721c24"))
            self._lasso_table.setItem(i, 0, name_item)
            self._lasso_table.setItem(i, 1, coef_item)
            self._lasso_table.setItem(i, 2, st)

        self._lasso_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)

        return {"coefs": coefs, "best_alpha": best_alpha,
                "user_alpha": user_alpha, "selected": selected, "rows": rows}

    # ── Ridge ─────────────────────────────────────────────────────────────

    def _compute_ridge(self):
        from sklearn.linear_model import Ridge, RidgeCV
        from sklearn.preprocessing import StandardScaler

        Xs = StandardScaler().fit_transform(self._X)
        y  = self._y

        alphas = np.logspace(-3, 3, 50)
        try:
            rcv = RidgeCV(alphas=alphas).fit(Xs, y)
            best_alpha = float(rcv.alpha_)
        except Exception:
            best_alpha = 1.0

        # Fit at best alpha
        ridge = Ridge(alpha=best_alpha).fit(Xs, y)
        coefs = ridge.coef_

        # Coefficient path
        if HAS_MPL:
            self._ridge_fig.clear()
            ax = self._ridge_fig.add_subplot(111)
            coefs_path = []
            for a in alphas:
                m = Ridge(alpha=a).fit(Xs, y)
                coefs_path.append(m.coef_)
            coefs_path = np.array(coefs_path)
            for i, vname in enumerate(self._var_names):
                ax.plot(alphas, coefs_path[:, i], lw=1.2, label=vname)
            ax.set_xscale("log")
            ax.axvline(best_alpha, color="#c0392b", linestyle=":", lw=2,
                       label=f"CV best α = {best_alpha:.4f}")
            ax.set_xlabel("Alpha (regularisation strength)", fontsize=9)
            ax.set_ylabel("Coefficient value", fontsize=9)
            ax.set_title("Ridge Coefficient Paths (all variables retained)",
                         fontsize=10, color="#1d5235")
            _style_ax(ax)
            if len(self._var_names) <= 12:
                ax.legend(fontsize=7, loc="best", ncol=2)
            self._ridge_fig.tight_layout()
            self._ridge_canvas.draw()

        rows = [(v, c) for v, c in zip(self._var_names, coefs)]
        rows.sort(key=lambda r: -abs(r[1]))

        # Ridge doesn't zero-out coefficients, so "selection" = top variables
        # by absolute coefficient magnitude. We recommend those with
        # |coef| greater than the median |coef|.
        abs_coefs = np.abs([c for _, c in rows])
        threshold = np.median(abs_coefs)
        recommended = set(v for v, c in rows if abs(c) > threshold)

        self._ridge_table.setRowCount(len(rows))
        self._ridge_table.setColumnCount(3)
        self._ridge_table.setHorizontalHeaderLabels(
            ["Variable", f"Coefficient (α = {best_alpha:.4f})", "Status"])

        from PyQt6.QtGui import QColor, QFont

        for i, (vname, c) in enumerate(rows):
            is_rec = vname in recommended
            name_item = QTableWidgetItem(vname)
            coef_item = QTableWidgetItem(f"{c:+.4f}")
            if is_rec:
                f = QFont(); f.setBold(True)
                name_item.setFont(f); coef_item.setFont(f)
                name_item.setForeground(QColor("#1d5235"))
                name_item.setBackground(QColor("#d4edda"))
                coef_item.setBackground(QColor("#d4edda"))
                st = QTableWidgetItem("RECOMMENDED")
                st.setBackground(QColor("#d4edda"))
                st.setForeground(QColor("#1d5235"))
                st.setFont(f)
            else:
                st = QTableWidgetItem("low importance")
                st.setForeground(QColor("#999"))
            self._ridge_table.setItem(i, 0, name_item)
            self._ridge_table.setItem(i, 1, coef_item)
            self._ridge_table.setItem(i, 2, st)

        self._ridge_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)

        self._ridge_recommended = list(recommended)
        return {"coefs": coefs, "best_alpha": best_alpha, "rows": rows,
                "recommended": list(recommended), "threshold": float(threshold)}

    # ── Save all results ──────────────────────────────────────────────────

    def _save_all(self):
        """Export all plots (PNG) and tables (CSV) to output_dir/advanced/."""
        out_base = self.dlg.state.get("output_dir", "")
        if not out_base:
            QMessageBox.warning(self, "No output directory",
                "Set the output directory in the Data tab first.")
            return

        import os
        out_dir = os.path.join(out_base, "advanced_analysis")
        os.makedirs(out_dir, exist_ok=True)

        n_saved = 0
        errors = []

        # Condition Number — text file
        try:
            kappa = getattr(self, "_last_kappa", None)
            sv    = getattr(self, "_last_sv", None)
            if kappa is not None:
                with open(os.path.join(out_dir, "condition_number.txt"), "w",
                          encoding="utf-8") as f:
                    f.write(f"HABITUS — Advanced Multicollinearity Analysis\n")
                    f.write(f"{'='*60}\n")
                    f.write(f"Condition Number (kappa): {kappa:.4f}\n")
                    f.write(f"Variables analysed: {len(self._var_names)}\n")
                    f.write(f"Samples: {self._X.shape[0]}\n\n")
                    f.write(f"Interpretation (Belsley et al. 1980):\n")
                    f.write(f"  kappa < 30       : weak multicollinearity\n")
                    f.write(f"  30 <= kappa <100 : moderate multicollinearity\n")
                    f.write(f"  kappa >= 100     : severe multicollinearity\n")
                    f.write(f"  kappa >= 1000    : near-singular design matrix\n\n")
                    if sv is not None and len(sv) > 0:
                        f.write(f"Singular values (top 10): "
                                f"{', '.join(f'{v:.4g}' for v in sv[:10])}\n")
                n_saved += 1
        except Exception as e:
            errors.append(f"condition: {e}")

        # PCA
        try:
            r = getattr(self, "_pca_result", None)
            if r:
                # Scree + cumulative plot
                self._pca_fig.savefig(
                    os.path.join(out_dir, "pca_variance.png"),
                    dpi=300, bbox_inches="tight", facecolor="white")
                n_saved += 1
                # Loadings table
                k = r["k"]
                df = pd.DataFrame(
                    r["loadings"][:k].T,
                    index=self._var_names,
                    columns=[f"PC{i+1}" for i in range(k)])
                df["ExplainedVar_%"] = [""] * len(df)
                for i in range(k):
                    df.at[self._var_names[0], f"PC{i+1}"] = r["loadings"][i, 0]
                df.to_csv(os.path.join(out_dir, "pca_loadings.csv"),
                         encoding="utf-8")
                n_saved += 1
                # Variance explained
                var_df = pd.DataFrame({
                    "Component": [f"PC{i+1}" for i in range(len(r["var_ratio"]))],
                    "VarianceExplained_%": r["var_ratio"] * 100,
                    "CumulativeVariance_%": r["cum_var"] * 100,
                })
                var_df.to_csv(os.path.join(out_dir, "pca_variance.csv"),
                             index=False, encoding="utf-8")
                n_saved += 1
        except Exception as e:
            errors.append(f"PCA: {e}")

        # LASSO
        try:
            r = getattr(self, "_lasso_result", None)
            if r:
                self._lasso_fig.savefig(
                    os.path.join(out_dir, "lasso_coefficient_paths.png"),
                    dpi=300, bbox_inches="tight", facecolor="white")
                n_saved += 1
                rows = r["rows"]
                pd.DataFrame({
                    "Variable": [v for v, _ in rows],
                    "Coefficient": [c for _, c in rows],
                    "Selected": ["Yes" if abs(c) > 1e-8 else "No" for _, c in rows],
                }).to_csv(os.path.join(out_dir, "lasso_coefficients.csv"),
                         index=False, encoding="utf-8")
                n_saved += 1
                # Alpha info
                with open(os.path.join(out_dir, "lasso_info.txt"), "w",
                          encoding="utf-8") as f:
                    f.write(f"User alpha : {r['user_alpha']}\n")
                    f.write(f"CV best alpha : {r['best_alpha']:.6f}\n")
                    f.write(f"Selected variables ({len(r['selected'])}): "
                            f"{', '.join(r['selected'])}\n")
                n_saved += 1
        except Exception as e:
            errors.append(f"LASSO: {e}")

        # Ridge
        try:
            r = getattr(self, "_ridge_result", None)
            if r:
                self._ridge_fig.savefig(
                    os.path.join(out_dir, "ridge_coefficient_paths.png"),
                    dpi=300, bbox_inches="tight", facecolor="white")
                n_saved += 1
                rows = r["rows"]
                pd.DataFrame({
                    "Variable": [v for v, _ in rows],
                    "Coefficient": [c for _, c in rows],
                }).to_csv(os.path.join(out_dir, "ridge_coefficients.csv"),
                         index=False, encoding="utf-8")
                n_saved += 1
        except Exception as e:
            errors.append(f"Ridge: {e}")

        msg = f"Saved {n_saved} files to:\n{out_dir}"
        if errors:
            msg += "\n\nWarnings:\n" + "\n".join(errors)
        QMessageBox.information(self, "Export Complete", msg)
        self.dlg.log(f"Advanced analysis: {n_saved} files saved to {out_dir}")
