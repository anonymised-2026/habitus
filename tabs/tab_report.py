# -*- coding: utf-8 -*-
"""
Tab ⑧ – HTML Report Generator  (Q1 journal-level)

Section order:
  1. Study Summary
  2. Selected Variables (VIF, correlation, graphs)
  3. Methods
  4. Model Parameters
  5. Model Evaluation Results (5.1–5.3.5)
  6. Current Distribution Maps (EMwmean only)
  7. Future Scenarios (EMwmean only)
  8. Range Change (if available)
  9. Validation (if available)
 10. Session Log
 11. Citation / Footer
"""

import os, base64, datetime, re, io

import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QCheckBox, QProgressBar, QTextEdit, QFileDialog,
    QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# ── Algorithm descriptions ─────────────────────────────────────────────────
_ALGO_DESC = {
    "RF":       ("Random Forest (RF)", "Breiman 2001",
                 "an ensemble of decision trees trained on bootstrap samples with random "
                 "feature subsets; robust to overfitting and handles non-linear interactions"),
    "BRT":      ("Boosted Regression Trees (BRT)", "Elith et al. 2008",
                 "gradient boosting of regression trees with stochastic sampling; "
                 "handles complex interactions and missing data"),
    "LR":       ("Logistic Regression (LR)", "Guisan et al. 2002",
                 "logistic regression with L2 regularisation; interpretable linear baseline"),
    "SVM":      ("Support Vector Machine (SVM)", "Drake et al. 2006",
                 "maximum-margin classifier with radial basis function kernel; "
                 "effective in high-dimensional feature spaces"),
    "MAXENT":   ("MaxEnt", "Phillips et al. 2006",
                 "maximum entropy modelling from presence-only data; "
                 "models the most spread-out distribution consistent with constraints"),
    "GAM":      ("Generalised Additive Model (GAM)", "Hastie & Tibshirani 1990",
                 "semi-parametric model with smooth spline terms; "
                 "allows non-linear but interpretable species–environment relationships"),
    "ENFA":     ("Ecological Niche Factor Analysis (ENFA)", "Hirzel et al. 2002",
                 "presence-only ordination contrasting species habitat against the landscape; "
                 "estimates marginality and specialisation"),
    "MAHAL":    ("Mahalanobis Distance (MAHAL)", "Farber & Kadmon 2003",
                 "multivariate distance from species centroid in environmental space; "
                 "simple presence-only approach sensitive to outliers"),
    "GBM":      ("Gradient Boosting Machine (GBM)", "Friedman 2001",
                 "gradient boosting with decision tree weak learners; "
                 "high predictive power through iterative residual correction"),
    "CATBOOST": ("CatBoost", "Prokhorenkova et al. 2018",
                 "ordered gradient boosting with symmetric trees; "
                 "robust to overfitting and efficient with categorical features"),
    "LGBM":     ("LightGBM", "Ke et al. 2017",
                 "leaf-wise gradient boosting; extremely fast and memory-efficient "
                 "on large datasets with many predictors"),
    "MLP":      ("Multilayer Perceptron (MLP)", "LeCun et al. 2015",
                 "feed-forward artificial neural network with hidden layers; "
                 "universal function approximator sensitive to hyperparameter tuning"),
}

_PA_STRATEGY_DESC = {
    "random":     "randomly sampled across the accessible area",
    "env_kernel": "sampled proportional to environmental density (kernel density estimation)",
    "sre":        "sampled from the surface range envelope of the species",
}

# ── CSS ────────────────────────────────────────────────────────────────────
_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Times New Roman', Times, serif;
    font-size: 11pt; color: #111; background: #fff;
    max-width: 980px; margin: 0 auto;
    padding: 32px 44px 60px; line-height: 1.65;
}
h2 { font-size: 13pt; font-weight: bold; margin-top: 34px; margin-bottom: 10px;
     border-bottom: 2px solid #1a5c3a; padding-bottom: 4px; color: #1a5c3a; }
h3 { font-size: 11.5pt; font-weight: bold; margin-top: 20px; margin-bottom: 6px; color: #1d5235; }
h4 { font-size: 10.5pt; font-weight: bold; margin-top: 14px; margin-bottom: 4px; color: #2a6a48; }
p  { margin-bottom: 8px; text-align: justify; }
ul, ol { margin: 6px 0 10px 22px; }
li { margin-bottom: 3px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0 20px; font-size: 10pt; }
th { background: #1a5c3a; color: #fff; padding: 6px 10px; text-align: left; font-weight: bold; }
td { border: 1px solid #ccc; padding: 5px 10px; vertical-align: top; }
tr:nth-child(even) td { background: #f5f9f6; }
.badge-ex   { background: #c3e6cb; color: #0a3622; padding: 1px 7px; border-radius: 10px; font-size: 9pt; }
.badge-good { background: #d4edda; color: #155724; padding: 1px 7px; border-radius: 10px; font-size: 9pt; }
.badge-ok   { background: #fff3cd; color: #856404; padding: 1px 7px; border-radius: 10px; font-size: 9pt; }
.badge-poor { background: #f8d7da; color: #721c24; padding: 1px 7px; border-radius: 10px; font-size: 9pt; }
.fig-wrap   { text-align: center; margin: 20px 0; }
.fig-wrap img { max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }
.fig-caption { font-size: 9.5pt; color: #444; font-style: italic; margin-top: 6px; text-align: justify; }
.interp { background: #f0f9f4; border-left: 3px solid #3a8c60;
           padding: 7px 12px; margin: 8px 0 14px; font-size: 10pt;
           border-radius: 0 4px 4px 0; }
.log-box { font-family: 'Courier New', monospace; font-size: 8pt;
            background: #f8f8f8; border: 1px solid #ddd; border-radius: 4px;
            padding: 12px 14px; white-space: pre-wrap; word-break: break-word;
            max-height: 420px; overflow-y: auto; color: #1a3a1a; }
.param-key { font-family: 'Courier New', monospace; font-size: 9pt; }
.notice { background: #eaf4ee; border-left: 4px solid #1a8c5a;
           padding: 8px 14px; margin: 10px 0; font-size: 10pt;
           border-radius: 0 4px 4px 0; }
.map-note { font-size: 9.5pt; color: #555; margin-bottom: 8px; font-style: italic; }
footer { margin-top: 44px; border-top: 1px solid #ccc; padding-top: 12px;
         font-size: 9.5pt; color: #555; text-align: center; }
@media print { body { max-width: 100%; padding: 18px; } .log-box { max-height: none; } }
"""

# ── Helpers ────────────────────────────────────────────────────────────────

def _b64_img(fpath: str) -> str:
    try:
        with open(fpath, "rb") as fh:
            return "data:image/png;base64," + base64.b64encode(fh.read()).decode()
    except Exception:
        return ""


def _fmt(v, d=3):
    try:    return f"{float(v):.{d}f}"
    except: return "N/A"


def _badge(value, thresholds=(0.8, 0.7)):
    try:
        v = float(value)
        if   v >= thresholds[0]: cls = "badge-good"
        elif v >= thresholds[1]: cls = "badge-ok"
        else:                     cls = "badge-poor"
        return f'<span class="{cls}">{v:.3f}</span>'
    except:
        return str(value)


def _interp_auc(v):
    try:
        f = float(v)
        if   f >= 0.90: return "excellent discrimination"
        elif f >= 0.80: return "good discrimination"
        elif f >= 0.70: return "fair discrimination"
        elif f >= 0.60: return "poor discrimination"
        else:           return "no discrimination (random)"
    except: return "N/A"


def _interp_tss(v):
    try:
        f = float(v)
        if   f >= 0.80: return "excellent"
        elif f >= 0.60: return "good"
        elif f >= 0.40: return "acceptable"
        elif f >= 0.20: return "poor"
        else:           return "very poor / no skill"
    except: return "N/A"


def _interp_boyce(v):
    try:
        f = float(v)
        if   f >= 0.75: return "strong positive — model reliably predicts habitat use"
        elif f >= 0.50: return "moderate positive — model acceptable"
        elif f >= 0.0:  return "weak positive — model marginally useful"
        else:           return "negative — model inversely predicts habitat use"
    except: return "N/A"


def _interp_kappa(v):
    try:
        f = float(v)
        if   f >= 0.80: return "almost perfect agreement"
        elif f >= 0.60: return "substantial agreement"
        elif f >= 0.40: return "moderate agreement"
        elif f >= 0.20: return "fair agreement"
        elif f >= 0.0:  return "slight agreement"
        else:           return "poor / chance-level agreement"
    except: return "N/A"


def _map_title_from_stem(stem: str) -> str:
    """'Sp_current_EMwmean_prob' → 'EMwmean Probability'."""
    for kw in ("EMwmean", "EMca", "EMwMean"):
        if kw.lower() in stem.lower():
            idx = stem.lower().index(kw.lower())
            stem = stem[idx:]
            break
    stem = stem.replace("_", " ").strip()
    stem = re.sub(r"\bprob\b", "Probability", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\bbin\b",  "Binary",      stem, flags=re.IGNORECASE)
    return stem


# ══════════════════════════════════════════════════════════════════════════
class ReportTab(QWidget):

    def __init__(self, dlg):
        super().__init__()
        self.dlg = dlg
        self._html_path = None
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # Header banner
        hdr = QWidget(); hdr.setObjectName("report_header")
        hdr.setStyleSheet(
            "#report_header{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #c8e6d4,stop:1 #ddf0e6);border-radius:8px;border:1px solid #3a8c60;}")
        hl = QVBoxLayout(hdr); hl.setContentsMargins(20,14,20,14); hl.setSpacing(3)
        t = QLabel("HABITUS"); t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet("font-size:28px;font-weight:900;color:#1d5235;letter-spacing:4px;background:transparent;")
        s = QLabel("Habitat Analysis &amp; Biodiversity Integrated Toolkit for Unified Species Distribution Modelling")
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.setStyleSheet("font-size:12px;color:#3a7050;font-style:italic;background:transparent;")
        r = QLabel("⑧  Report Generator")
        r.setAlignment(Qt.AlignmentFlag.AlignCenter)
        r.setStyleSheet("font-size:10px;color:#5a9070;background:transparent;margin-top:2px;")
        hl.addWidget(t); hl.addWidget(s); hl.addWidget(r)
        root.addWidget(hdr)

        # Options
        grp = QGroupBox("Report Sections"); gl = QHBoxLayout(grp)
        self._chk_vars    = QCheckBox("Variables");    self._chk_vars.setChecked(True)
        self._chk_methods = QCheckBox("Methods");      self._chk_methods.setChecked(True)
        self._chk_params  = QCheckBox("Parameters");   self._chk_params.setChecked(True)
        self._chk_eval    = QCheckBox("Evaluation");   self._chk_eval.setChecked(True)
        self._chk_maps    = QCheckBox("Maps");         self._chk_maps.setChecked(True)
        self._chk_future  = QCheckBox("Future");       self._chk_future.setChecked(True)
        self._chk_range   = QCheckBox("Range Change"); self._chk_range.setChecked(True)
        self._chk_valid   = QCheckBox("Validation");   self._chk_valid.setChecked(True)
        self._chk_log     = QCheckBox("Log");          self._chk_log.setChecked(True)
        for w in (self._chk_vars, self._chk_methods, self._chk_params, self._chk_eval,
                  self._chk_maps, self._chk_future, self._chk_range, self._chk_valid, self._chk_log):
            gl.addWidget(w)
        gl.addStretch()
        root.addWidget(grp)

        # Buttons
        br = QHBoxLayout()
        self._btn_gen  = QPushButton("⚙  Generate HTML Report")
        self._btn_gen.setMinimumWidth(210); self._btn_gen.clicked.connect(self._generate)
        self._btn_open = QPushButton("🌐  Open in Browser")
        self._btn_open.setEnabled(False);   self._btn_open.clicked.connect(self._open_browser)
        br.addWidget(self._btn_gen); br.addWidget(self._btn_open); br.addStretch()
        root.addLayout(br)

        # Progress + status
        self._progress = QProgressBar()
        self._progress.setRange(0,100); self._progress.setValue(0)
        self._progress.setFormat("Ready"); self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._status_lbl = QLabel(
            "Click 'Generate HTML Report' to create the report from current results. "
            "Each click re-reads all outputs and re-generates from scratch.")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(
            "color:#3a7050;font-size:10px;background:#eaf4ee;"
            "border:1px solid #b8d4c4;border-radius:4px;padding:5px 8px;")
        root.addWidget(self._status_lbl)

        lbl = QLabel("Report preview (HTML source — first 8 000 characters):")
        lbl.setStyleSheet("font-size:10px;color:#555;")
        root.addWidget(lbl)
        self._preview = QTextEdit(); self._preview.setReadOnly(True)
        self._preview.setFont(QFont("Courier New", 8))
        self._preview.setPlaceholderText("Generate a report to see a preview here…")
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._preview, 1)

    # ── Utility ──────────────────────────────────────────────────────────

    def _step(self, label: str, pct: int):
        self._progress.setFormat(label); self._progress.setValue(pct)
        from PyQt6.QtWidgets import QApplication; QApplication.processEvents()

    def _figures(self) -> dict:
        """Return {stem: fpath} for all PNGs in output_dir/figures/."""
        out = self.dlg.state.get("output_dir","")
        fd  = os.path.join(out,"figures") if out else ""
        res = {}
        if os.path.isdir(fd):
            for f in sorted(os.listdir(fd)):
                if f.lower().endswith(".png"):
                    res[f[:-4]] = os.path.join(fd, f)
        return res

    def _tif_maps(self, subdir: str) -> list:
        """Return [(stem, fpath)] for EMwmean TIFs in output_dir/subdir/."""
        out  = self.dlg.state.get("output_dir","")
        path = os.path.join(out, subdir)
        res  = []
        if os.path.isdir(path):
            for f in sorted(os.listdir(path)):
                if f.lower().endswith(".tif") and "emwmean" in f.lower():
                    res.append((f[:-4], os.path.join(path, f)))
        return res

    def _read_log(self) -> str:
        out = self.dlg.state.get("output_dir","")
        if not out or not os.path.isdir(out): return ""
        logs = sorted([f for f in os.listdir(out) if f.endswith(".log")], reverse=True)
        if not logs: return ""
        try:
            with open(os.path.join(out, logs[0]), encoding="utf-8") as fh:
                return fh.read()
        except: return ""

    def _render_tif(self, fpath: str, title: str) -> str:
        """Render a suitability/binary TIF → base64 PNG using Agg backend.

        Figure size is derived from the raster's geographic extent with a
        cosine latitude correction so the map is neither squished nor stretched.
        """
        try:
            import rasterio
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from matplotlib.colors import LinearSegmentedColormap, ListedColormap

            with rasterio.open(fpath) as src:
                data   = src.read(1).astype(float)
                nodata = src.nodata
                bounds = src.bounds          # left, bottom, right, top

            if nodata is not None:
                data = np.where(data == nodata, np.nan, data)

            # ── Aspect ratio from geographic extent ────────────────────────
            width_deg  = bounds.right - bounds.left
            height_deg = bounds.top   - bounds.bottom
            lat_mid    = (bounds.top + bounds.bottom) / 2.0
            # Longitude degrees are shorter than latitude degrees by cos(lat)
            lon_scale  = np.cos(np.radians(lat_mid))
            geo_ratio  = (width_deg * lon_scale) / max(height_deg, 1e-6)

            # Fix map area width at 7.2 inches; derive height from ratio
            # Add margins for colorbar (right) and labels (left/bottom/top)
            map_w  = 7.2
            map_h  = map_w / max(geo_ratio, 0.2)
            map_h  = float(np.clip(map_h, 2.5, 10.0))
            # Total figure: extra height for title block (1.1 in) + x-label (0.5 in)
            fig_w  = map_w + 1.6   # colorbar + left label room
            fig_h  = map_h + 1.6   # title + xlabel room
            # ──────────────────────────────────────────────────────────────

            is_prob = "_prob" in fpath.lower()
            if is_prob:
                colors = ["#eaedf0","#c9d5de","#a0bece","#72a5b8",
                          "#4490a0","#237a82","#136860","#006837","#1a9641"]
                cmap = LinearSegmentedColormap.from_list("hs", colors, N=256)
                vmin, vmax, cbar_lbl = 0.0, 1.0, "Habitat suitability (0–1)"
            else:
                cmap = ListedColormap(["#c8c8c8","#1a9641"])
                vmin, vmax, cbar_lbl = 0, 1, "Presence (1) / Absence (0)"

            fig, ax = plt.subplots(figsize=(fig_w, fig_h), facecolor="#fff")
            ext = [bounds.left, bounds.right, bounds.bottom, bounds.top]
            im  = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax,
                            extent=ext, origin="upper", interpolation="nearest",
                            aspect="equal")          # honour geographic proportions
            plt.colorbar(im, ax=ax, label=cbar_lbl, fraction=0.03, pad=0.02)
            ax.set_xlabel("Longitude", fontsize=9)
            ax.set_ylabel("Latitude",  fontsize=9)
            ax.tick_params(labelsize=8)
            for sp in ax.spines.values(): sp.set_color("#cccccc")
            ax.set_facecolor("#f0f5f1")

            sp_name = self.dlg.state.get("species_name","").replace("_"," ")
            if sp_name:
                fig.text(0.5, 0.98, sp_name, ha="center", va="top",
                         fontsize=10, fontstyle="italic", color="#1a5c3a")
            fig.suptitle(title, y=0.93, fontsize=11, fontweight="bold", color="#1a5c3a")

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#fff")
            plt.close(fig)
            buf.seek(0)
            return "data:image/png;base64," + base64.b64encode(buf.read()).decode()
        except Exception:
            return ""

    def _fig_block(self, uri: str, caption: str, interp: str = "") -> str:
        if not uri: return ""
        interp_html = f'<div class="interp">{interp}</div>' if interp else ""
        return (f'<div class="fig-wrap"><img src="{uri}" alt="figure"/>'
                f'<p class="fig-caption">{caption}</p></div>{interp_html}')

    # ══════════════════════════════════════════════════════════════════════
    # SECTION BUILDERS
    # ══════════════════════════════════════════════════════════════════════

    # ── 1. Study Summary ─────────────────────────────────────────────────

    def _s1_summary(self, m, state):
        sp      = state.get("species_name","—").replace("_"," ")
        out_dir = state.get("output_dir","—")
        vars_   = state.get("var_names",[])
        n_vars  = len(vars_)
        algos   = getattr(m,"algorithms",[]) if m else []
        n_models= len(getattr(m,"fitted_models",{})) if m else 0
        n_pres  = 0
        if m and hasattr(m,"pa_datasets") and m.pa_datasets:
            n_pres = int((m.pa_datasets[0][1]==1).sum())
        now = datetime.datetime.now().strftime("%d %B %Y, %H:%M")

        rows = [
            ("Target species",            f"<i>{sp}</i>"),
            ("Occurrence records (filtered)", str(n_pres)),
            ("Environmental predictors",  str(n_vars)),
            ("Modelling algorithms",      ", ".join(algos) or "—"),
            ("Total model runs",          str(n_models)),
            ("Output directory",          f"<code style='font-size:9pt'>{out_dir}</code>"),
            ("Report generated",          now),
        ]
        rows_html = "".join(f"<tr><td><b>{k}</b></td><td>{v}</td></tr>" for k,v in rows)
        return f"<h2>1. Study Summary</h2><table>{rows_html}</table>"

    # ── 2. Selected Variables ─────────────────────────────────────────────

    def _s2_variables(self, state, figs):
        vars_  = state.get("var_names", [])
        tab_vif = getattr(self.dlg, "tab_vif", None)
        df = getattr(tab_vif, "_ranking_df", None) if tab_vif else None

        html  = "<h2>2. Selected Variables and Multicollinearity Assessment</h2>"
        html += """
<p>
Prior to species distribution modelling, environmental predictors were screened
for multicollinearity using the Variance Inflation Factor (VIF; O'Brien 2007)
and pairwise Pearson correlation coefficients (Dormann et al. 2013).
Variables with VIF&nbsp;&gt;&nbsp;10 or |r|&nbsp;&gt;&nbsp;0.75 were considered
collinear and excluded from the final predictor set. The remaining variables
were used in all subsequent modelling steps.
</p>"""

        # VIF table if ranking_df available
        if df is not None and not df.empty:
            try:
                thead = "<tr><th>Variable</th><th>VIF</th><th>Univariate AUC</th><th>VIF OK</th><th>Corr OK</th><th>Selected</th></tr>"
                tbody = ""
                sel_set = set(vars_)
                for _, row in df.iterrows():
                    vname = row.get("Variable","")
                    vif   = row.get("VIF", float("nan"))
                    auc   = row.get("Univariate_AUC", float("nan"))
                    vok   = "Yes" if row.get("VIF_OK", False)  else "No"
                    cok   = "Yes" if row.get("Corr_OK", False) else "No"
                    sel   = "<b>Yes</b>" if vname in sel_set else "No"
                    vif_b = _badge(1/vif if vif and vif>0 else float("nan"), (0.5,0.1)) if not np.isnan(vif) else "—"
                    tbody += (f"<tr><td>{vname}</td><td>{_fmt(vif,2)}</td>"
                              f"<td>{_fmt(auc,3)}</td><td>{vok}</td><td>{cok}</td><td>{sel}</td></tr>")
                html += f"<h3>2.1 Variable Screening Table</h3><table>{thead}{tbody}</table>"
                html += """<div class="interp">
VIF values below 5 indicate no problematic multicollinearity; values 5–10 suggest
moderate collinearity warranting careful consideration; values above 10 indicate
severe collinearity. Univariate AUC reflects the predictive power of each variable
in isolation — higher values indicate greater individual discriminatory ability.
Selected variables (marked <b>Yes</b>) were retained in all modelling algorithms.
</div>"""
            except Exception:
                pass

        # Variable list
        if vars_:
            var_items = "".join(f"<li><code>{v}</code></li>" for v in vars_)
            html += f"<h3>2.2 Final Selected Variables ({len(vars_)})</h3><ul>{var_items}</ul>"

        # Correlation heatmap
        for stem in ("correlation_heatmap_selected","correlation_heatmap"):
            if stem in figs:
                uri = _b64_img(figs[stem])
                if uri:
                    html += self._fig_block(
                        uri,
                        "Figure 2.1. Pairwise Pearson correlation matrix of the final selected "
                        "environmental predictors. Colour intensity reflects correlation magnitude; "
                        "red indicates strong positive and blue strong negative correlations.",
                        "Absence of cells exceeding |r|&nbsp;=&nbsp;0.75 confirms that the "
                        "retained predictor set is free from problematic multicollinearity, "
                        "reducing the risk of variance inflation and unstable model coefficients."
                    )
                    break

        # VIF barplot
        if "vif_barplot" in figs:
            uri = _b64_img(figs["vif_barplot"])
            if uri:
                html += self._fig_block(
                    uri,
                    "Figure 2.2. Variance Inflation Factor (VIF) bar chart for all candidate "
                    "environmental predictors. The dashed reference line at VIF&nbsp;=&nbsp;10 "
                    "marks the standard exclusion threshold.",
                    "Variables with VIF below 10 (grey dashed line) were retained. "
                    "Lower VIF values indicate a more orthogonal predictor set, "
                    "which improves model stability and interpretability."
                )
        return html

    # ── 3. Methods ───────────────────────────────────────────────────────

    def _s3_methods(self, m, state):
        sp     = state.get("species_name","species").replace("_"," ")
        vars_  = state.get("var_names",[])
        n_pres = 0
        if m and hasattr(m,"pa_datasets") and m.pa_datasets:
            n_pres = int((m.pa_datasets[0][1]==1).sum())
        n_pa   = getattr(m,"n_pa_rep",1)  if m else 1
        n_abs  = getattr(m,"n_absences",1000) if m else 1000
        pa_str = getattr(m,"pa_strategy","random") if m else "random"
        n_cv   = getattr(m,"n_cv_runs",2) if m else 2
        split  = getattr(m,"data_split",80) if m else 80
        algos  = getattr(m,"algorithms",[]) if m else []
        pa_desc= _PA_STRATEGY_DESC.get(pa_str, pa_str)

        algo_li = "".join(
            f"<li><b>{_ALGO_DESC[a][0]}</b> ({_ALGO_DESC[a][1]}): {_ALGO_DESC[a][2]}.</li>"
            if a in _ALGO_DESC else f"<li><b>{a}</b></li>"
            for a in algos
        )
        refs = sorted({_ALGO_DESC[a][1] for a in algos if a in _ALGO_DESC})

        return f"""
<h2>3. Methods</h2>

<h3>3.1 Occurrence data</h3>
<p>
Occurrence records for <i>{sp}</i> were subjected to a three-stage spatial
filtering procedure: (i) duplicate records sharing identical grid-cell coordinates
were removed; (ii) records falling outside the spatial extent of the environmental
raster stack were discarded; and (iii) records coinciding with NoData cells in any
predictor layer were excluded. After filtering, <b>{n_pres}</b> georeferenced records
were retained for modelling.
</p>

<h3>3.2 Environmental predictors</h3>
<p>
A total of <b>{len(vars_)}</b> environmental predictors were used after
multicollinearity screening (Section&nbsp;2):
{", ".join(f"<i>{v}</i>" for v in vars_) or "—"}.
</p>

<h3>3.3 Pseudo-absence generation</h3>
<p>
<b>{n_pa}</b> pseudo-absence replicate dataset(s) were generated, each comprising
<b>{n_abs}</b> background points {pa_desc}.
Points coinciding with known occurrence records were excluded from the background set.
</p>

<h3>3.4 Modelling algorithms</h3>
<p>The following {len(algos)} algorithm(s) were calibrated:</p>
<ul>{algo_li}</ul>
<p>
Each algorithm was fitted with <b>{n_cv}</b> cross-validation run(s) per
pseudo-absence replicate ({n_pa}&nbsp;PA&nbsp;&times;&nbsp;{n_cv}&nbsp;CV&nbsp;=&nbsp;{n_pa*n_cv}
fits per algorithm). Training/test data were stratified by class
({split}&nbsp;%&nbsp;train&nbsp;/&nbsp;{100-split}&nbsp;%&nbsp;test), with presence
and background points split independently to guarantee representative test-set sizes.
{("References: " + "; ".join(refs) + ".") if refs else ""}
</p>

<h3>3.5 Ensemble modelling</h3>
<p>
Individual algorithm predictions were combined via two ensemble strategies:
<b>weighted mean</b> (EMwmean; weights proportional to individual TSS scores)
and <b>committee averaging</b> (EMca; binary threshold before averaging).
Ensemble maps are produced as probability and binary outputs.
</p>

<h3>3.6 Model evaluation</h3>
<p>
Model performance was assessed on withheld test partitions using:
the Area Under the ROC Curve (<b>AUC</b>; Hanley &amp; McNeil 1982),
the True Skill Statistic (<b>TSS</b>; Allouche et al. 2006), and
the Boyce Continuous Index (<b>CBI</b>; Hirzel et al. 2006).
Variable importance was estimated by permutation of each predictor on the test set
and measuring the resulting AUC drop.
</p>"""

    # ── 4. Model Parameters ───────────────────────────────────────────────

    def _s4_params(self, m, state):
        if not m:
            return "<h2>4. Model Parameters</h2><p><i>No model results available.</i></p>"
        algos  = getattr(m,"algorithms",[])
        opts   = getattr(m,"algo_options",{})
        n_pa   = getattr(m,"n_pa_rep",1)
        n_cv   = getattr(m,"n_cv_runs",2)
        split  = getattr(m,"data_split",80)
        n_abs  = getattr(m,"n_absences",1000)
        pa_str = getattr(m,"pa_strategy","random")
        vi_n   = getattr(m,"var_import_n",3)
        vars_  = state.get("var_names",[])

        # Global table
        glob = f"""
<table>
<tr><th colspan="2">Global Modelling Settings</th></tr>
<tr><td>Selected predictors ({len(vars_)})</td>
    <td>{", ".join(f"<code>{v}</code>" for v in vars_) or "—"}</td></tr>
<tr><td>Pseudo-absences per replicate</td><td><b>{n_abs}</b></td></tr>
<tr><td>PA strategy</td><td><b>{pa_str}</b></td></tr>
<tr><td>PA replicates</td><td><b>{n_pa}</b></td></tr>
<tr><td>CV runs per PA replicate</td><td><b>{n_cv}</b></td></tr>
<tr><td>Train / Test split</td><td><b>{split} / {100-split} %</b></td></tr>
<tr><td>Permutation importance repeats</td><td><b>{vi_n}</b></td></tr>
</table>"""

        # Per-algorithm table
        rows = ""
        for a in algos:
            d     = _ALGO_DESC.get(a)
            aname = d[0] if d else a
            adesc = d[2] if d else "—"
            aref  = d[1] if d else "—"
            aopts = opts.get(a,{})
            param_str = "; ".join(f"<code>{k}={v}</code>" for k,v in aopts.items()) or "<i>defaults</i>"
            rows += (f"<tr><td><b>{aname}</b><br/><span style='font-size:9pt;color:#555'>"
                     f"Ref: {aref}</span></td>"
                     f"<td style='font-size:9pt'>{adesc}.</td>"
                     f"<td>{param_str}</td></tr>")

        algo_tbl = f"""
<table>
<tr><th>Algorithm</th><th>Description</th><th>Hyperparameters</th></tr>
{rows}
</table>"""

        return f"<h2>4. Model Parameters</h2>{glob}<h3>4.1 Algorithm Settings</h3>{algo_tbl}"

    # ── 5. Model Evaluation ───────────────────────────────────────────────

    def _s5_evaluation(self, m, figs):
        if not m or not getattr(m,"evaluation_scores",{}):
            return ("<h2>5. Model Evaluation Results</h2>"
                    "<p><i>No evaluation scores available. Run models first.</i></p>")

        scores  = m.evaluation_scores
        var_imp = getattr(m,"variable_importance",{})
        var_names = getattr(m,"var_names",[])
        algos_u = sorted(set(k[0] for k in scores))

        html = "<h2>5. Model Evaluation Results</h2>"

        # ── 5.1 Individual scores ─────────────────────────────────────────
        html += "<h3>5.1 Individual Model Scores</h3>"
        html += """<p>
AUC colour thresholds: <span class="badge-good">≥ 0.80 good</span>
<span class="badge-ok">≥ 0.70 fair</span>
<span class="badge-poor">&lt; 0.70 poor</span>.
TSS: <span class="badge-good">≥ 0.60</span>
<span class="badge-ok">≥ 0.40</span>
<span class="badge-poor">&lt; 0.40</span>.
Boyce CBI: <span class="badge-good">≥ 0.50</span>
<span class="badge-ok">≥ 0.0</span>
<span class="badge-poor">&lt; 0.0</span>.
</p>"""
        thead = ("<tr><th>Algorithm</th><th>PA rep.</th><th>CV run</th>"
                 "<th>AUC</th><th>TSS</th><th>Boyce CBI</th><th>Interpretation</th></tr>")
        tbody = ""
        for key in sorted(scores.keys()):
            s   = scores[key]
            auc = s.get("ROC",   float("nan"))
            tss = s.get("TSS",   float("nan"))
            byc = s.get("Boyce", float("nan"))
            interp = _interp_auc(auc)
            tbody += (f"<tr><td>{key[0]}</td><td>{key[1]}</td><td>{key[2]}</td>"
                      f"<td>{_badge(auc,(0.80,0.70))}</td>"
                      f"<td>{_badge(tss,(0.60,0.40))}</td>"
                      f"<td>{_badge(byc,(0.50,0.0))}</td>"
                      f"<td style='font-size:9pt'>{interp}</td></tr>")
        html += f"<table>{thead}{tbody}</table>"
        html += """<div class="interp">
AUC measures the probability that the model ranks a randomly chosen presence
site higher than a randomly chosen background site; values &ge; 0.80 are generally
considered good for SDMs. TSS (True Skill Statistic) accounts for both sensitivity
and specificity independently of prevalence; values &ge; 0.60 indicate good skill.
The Boyce Continuous Index quantifies the correspondence between predicted
suitability and observed habitat use; positive values confirm the model predicts
habitat preference correctly.
</div>"""

        # ── 5.2 Algorithm summary ─────────────────────────────────────────
        html += "<h3>5.2 Algorithm Summary (mean ± SD across PA replicates and CV runs)</h3>"
        thead2 = "<tr><th>Algorithm</th><th>AUC</th><th>TSS</th><th>Boyce CBI</th><th>Overall assessment</th></tr>"
        tbody2 = ""
        best_auc_algo = None; best_auc_val = -999
        for a in algos_u:
            vals  = [s for k,s in scores.items() if k[0]==a]
            aucs  = [v.get("ROC",float("nan")) for v in vals]
            tsss  = [v.get("TSS",float("nan")) for v in vals]
            bycs  = [v.get("Boyce",float("nan")) for v in vals]
            mr, sr = np.nanmean(aucs), np.nanstd(aucs)
            mt, st = np.nanmean(tsss), np.nanstd(tsss)
            mb, sb = np.nanmean(bycs), np.nanstd(bycs)
            if mr > best_auc_val:
                best_auc_val  = mr
                best_auc_algo = a
            assess = f"{_interp_auc(mr)}; TSS {_interp_tss(mt)}; CBI {_interp_boyce(mb)}"
            tbody2 += (f"<tr><td><b>{a}</b></td>"
                       f"<td>{_badge(mr,(0.80,0.70))} &pm; {_fmt(sr)}</td>"
                       f"<td>{_badge(mt,(0.60,0.40))} &pm; {_fmt(st)}</td>"
                       f"<td>{_badge(mb,(0.50,0.0))} &pm; {_fmt(sb)}</td>"
                       f"<td style='font-size:9pt'>{assess}</td></tr>")
        html += f"<table>{thead2}{tbody2}</table>"
        if best_auc_algo:
            html += (f'<div class="interp">Among the tested algorithms, <b>{best_auc_algo}</b> '
                     f'achieved the highest mean AUC ({_fmt(best_auc_val)}), '
                     f'indicating {_interp_auc(best_auc_val)}. '
                     f'Mean ± SD values reflect variability across pseudo-absence replicates '
                     f'and cross-validation runs; lower SD indicates more stable predictions.</div>')

        # ── 5.3 Evaluation metrics description ───────────────────────────
        html += """<h3>5.3 Evaluation Metrics and Graphical Outputs</h3>
<p>
Model performance was quantified using three complementary, threshold-independent
or threshold-dependent metrics applied to the withheld test partition:
</p>
<ul>
<li><b>AUC (Area Under the ROC Curve)</b> — threshold-independent measure of
rank discrimination ability (Hanley &amp; McNeil 1982). Ranges from 0.5 (random)
to 1.0 (perfect).</li>
<li><b>TSS (True Skill Statistic)</b> — combines sensitivity and specificity at
the optimal TSS threshold; independent of prevalence (Allouche et al. 2006).
Ranges from −1 to +1; values &gt; 0.4 are considered acceptable.</li>
<li><b>Boyce CBI (Continuous Boyce Index)</b> — evaluates the correspondence
between predicted suitability and observed habitat-use intensity across the
full suitability gradient (Hirzel et al. 2006). Values near +1 indicate the
model reliably predicts where the species occurs.</li>
</ul>"""

        # ── 5.3.1 Model Evaluation Scores ────────────────────────────────
        html += "<h4>5.3.1 Model Evaluation Scores</h4>"
        fig_key = "evaluation_model_scores"
        if fig_key in figs:
            uri = _b64_img(figs[fig_key])
            html += self._fig_block(
                uri,
                "Figure 5.1. Model performance scores (AUC, TSS, Boyce CBI) for all "
                "algorithm × PA replicate × CV run combinations. Diamond markers indicate "
                "mean values; vertical bars span the observed range.",
                "Points above the dashed reference lines (AUC&nbsp;0.80; TSS&nbsp;0.60; "
                "CBI&nbsp;0.50) indicate acceptable to good model performance. "
                "Tight clustering of replicates suggests stable, reproducible predictions."
            )

        # ── 5.3.2 ROC Curves ─────────────────────────────────────────────
        html += "<h4>5.3.2 ROC Curves</h4>"
        html += """<p>
The ROC (Receiver Operating Characteristic) curve plots sensitivity (true positive
rate) against 1&nbsp;&minus;&nbsp;specificity (false positive rate) across all
classification thresholds. The area under this curve (AUC) summarises overall
discriminatory ability. A model with no skill follows the diagonal (AUC&nbsp;=&nbsp;0.5).
</p>"""
        fig_key = "evaluation_roc_curves"
        if fig_key in figs:
            # Per-algo AUC summary sentence
            auc_lines = "; ".join(
                f"{a}: AUC&nbsp;=&nbsp;{_fmt(np.nanmean([s.get('ROC',float('nan')) for k,s in scores.items() if k[0]==a]))}"
                for a in algos_u
            )
            uri = _b64_img(figs[fig_key])
            html += self._fig_block(
                uri,
                "Figure 5.2. ROC curves for each modelling algorithm averaged across "
                "pseudo-absence replicates and cross-validation runs. Shaded bands "
                "indicate variability across replicates.",
                f"Mean AUC by algorithm — {auc_lines}. "
                f"Curves substantially above the diagonal confirm meaningful discrimination "
                f"between suitable and unsuitable habitats."
            )

        # ── 5.3.3 Omission / PR / Calibration ────────────────────────────
        html += "<h4>5.3.3 Omission Rate, Precision–Recall, and Calibration</h4>"
        html += """<p>
Omission rate at the 10th percentile training threshold (OR10) measures the
fraction of test presences predicted as absent; values near zero indicate the model
does not over-restrict the predicted range. The Precision–Recall curve evaluates
performance under class imbalance; the calibration plot assesses whether
predicted probabilities match observed occurrence frequencies.
</p>"""
        fig_key = "evaluation_omission_pr_calibration"
        if fig_key in figs:
            uri = _b64_img(figs[fig_key])
            html += self._fig_block(
                uri,
                "Figure 5.3. (Left) Omission rate as a function of the predicted "
                "suitability threshold. (Centre) Precision–Recall curve. "
                "(Right) Calibration plot comparing predicted probabilities against "
                "observed presence frequencies.",
                "Low omission rates at liberal thresholds and high precision–recall "
                "area-under-curve indicate reliable detection of suitable habitat. "
                "A well-calibrated model (diagonal in the calibration plot) produces "
                "probability values interpretable as actual occurrence likelihoods."
            )

        # ── 5.3.4 Variable Importance ─────────────────────────────────────
        html += "<h4>5.3.4 Variable Importance</h4>"
        html += """<p>
Permutation importance was estimated by randomly shuffling each predictor in the
test set and recording the resulting drop in AUC. Larger drops indicate stronger
dependence of the model on that predictor. Results are averaged over all
PA replicates, CV runs, and permutation repetitions.
</p>"""
        # Identify top/bottom variables
        top_var = bot_var = None
        if var_imp and var_names:
            try:
                all_arr = np.vstack(list(var_imp.values()))
                means   = np.nanmean(all_arr, axis=0)
                if len(means) == len(var_names):
                    top_var = var_names[int(np.argmax(means))]
                    bot_var = var_names[int(np.argmin(means))]
            except Exception:
                pass

        fig_key = "evaluation_variable_importance"
        if fig_key in figs:
            uri = _b64_img(figs[fig_key])
            top_msg = (f"<b>{top_var}</b> emerged as the most influential predictor, "
                       f"while <b>{bot_var}</b> contributed least to model discrimination. "
                       if top_var and bot_var else "")
            html += self._fig_block(
                uri,
                "Figure 5.4. Permutation-based variable importance averaged across all "
                "algorithms, PA replicates, and CV runs. Error bars represent standard deviation.",
                top_msg +
                "Variables with high importance should be prioritised in ecological interpretation "
                "and future data collection. Low-importance variables may be candidates for "
                "removal in model simplification, but should not be excluded without expert review."
            )

        # ── 5.3.5 Response Curves ─────────────────────────────────────────
        html += "<h4>5.3.5 Response Curves</h4>"
        html += """<p>
Marginal response curves depict the modelled habitat suitability as a function of
each environmental predictor while all other variables are held at their mean values.
They provide ecologically interpretable insight into species–environment relationships
and allow identification of thermal or hydrological optima.
</p>"""
        resp_keys = sorted(k for k in figs if k.startswith("evaluation_response_"))
        if resp_keys:
            for i, rk in enumerate(resp_keys, 1):
                algo = rk.replace("evaluation_response_","")
                uri  = _b64_img(figs[rk])
                html += self._fig_block(
                    uri,
                    f"Figure 5.{4+i}. Marginal response curves for <b>{algo}</b>. "
                    f"Each panel shows predicted suitability (y-axis) as a function "
                    f"of one predictor (x-axis); rug marks indicate the distribution "
                    f"of training presence records.",
                    f"Unimodal curves indicate clear optima; monotonic curves suggest "
                    f"the species is at the edge of the sampled environmental space. "
                    f"Non-linear relationships visible in these {algo} curves confirm "
                    f"the utility of flexible machine-learning approaches."
                )

        return html

    # ── 6. Current Distribution Maps ─────────────────────────────────────

    def _s6_current_maps(self):
        """Use user-exported PNGs from the map viewer (output_dir root)."""
        out_dir = self.dlg.state.get("output_dir", "")
        if not out_dir or not os.path.isdir(out_dir):
            return ""

        pngs = sorted(
            f for f in os.listdir(out_dir)
            if f.lower().endswith(".png") and not f.lower().startswith("habitus_")
        )
        if not pngs:
            return ""

        sp_disp = self.dlg.state.get("species_name","").replace("_"," ")
        html  = "<h2>6. Current Distribution</h2>"
        html += f"""<p>
The following maps were exported directly from the HABITUS map viewer using the
visualisation style selected by the analyst. Each map was saved at 300&nbsp;DPI
and reflects the colour palette, stretch, and layer combination chosen at the
time of export. Layer names and styling are embedded in the filename.
</p>"""

        for i, fname in enumerate(pngs, 1):
            fpath = os.path.join(out_dir, fname)
            uri   = _b64_img(fpath)
            if not uri:
                continue
            stem  = fname[:-4]
            # Infer map type from filename keywords
            fl = stem.lower()
            if "prob" in fl or "suitability" in fl:
                map_type = "habitat suitability probability"
                interp = (
                    "The probability map displays the ensemble-weighted mean predicted "
                    "occurrence probability across all contributing models and pseudo-absence "
                    "replicates. Values approaching 1.0 (high-suitability colours) indicate "
                    "environmentally optimal conditions. These areas should be prioritised "
                    "for field surveys and conservation resource allocation."
                )
            elif "bin" in fl or "binary" in fl or "presence" in fl:
                map_type = "binary presence/absence"
                interp = (
                    "The binary map converts continuous suitability to a discrete "
                    "presence/absence classification using the TSS-optimised threshold. "
                    "Predicted presence cells define the modelled current range extent, "
                    "which can be compared against occurrence records and protected-area "
                    "networks to evaluate coverage."
                )
            elif "range" in fl or "change" in fl or "src" in fl:
                map_type = "range change"
                interp = (
                    "The range-change map classifies each cell as Lost, Stable Present, "
                    "Stable Absent, or Gained relative to a comparison scenario. "
                    "This layer is key to quantifying climate-driven distributional shifts "
                    "and identifying refugia or colonisation corridors."
                )
            elif "ensemble" in fl or "emw" in fl or "ems" in fl:
                map_type = "ensemble"
                interp = (
                    "The ensemble map combines predictions from multiple algorithms, "
                    "reducing the influence of algorithm-specific artefacts. "
                    "Ensemble approaches generally yield more robust spatial predictions "
                    "than any single algorithm (Araújo &amp; New 2007)."
                )
            else:
                map_type = "distribution"
                interp = (
                    "This map was exported from the HABITUS map viewer with the "
                    "analyst-selected visualisation style. The layer name indicates "
                    "the algorithm, pseudo-absence replicate, and output type."
                )

            # Human-readable label from filename (remove species prefix if present)
            label = stem.replace("_"," ").strip()
            if sp_disp:
                safe_sp = re.sub(r"[^\w ]","", sp_disp)
                label   = re.sub(r"(?i)^" + re.escape(safe_sp) + r"\s*[_\-]?\s*", "", label).strip()
            if not label:
                label = stem.replace("_"," ")

            cap = (f"Figure 6.{i}. <i>{sp_disp}</i> — {map_type} map: <b>{label}</b>. "
                   f"Exported from HABITUS map viewer at 300 DPI with analyst-selected "
                   f"colour style.")
            html += self._fig_block(uri, cap, interp)

        return html

    # ── 7. Future Scenarios ───────────────────────────────────────────────

    def _s7_future_maps(self):
        """Use user-exported PNGs from future projection subdirectories."""
        out_dir = self.dlg.state.get("output_dir","")
        if not out_dir or not os.path.isdir(out_dir):
            return ""

        skip = {"figures", "validation"}
        sp_disp = self.dlg.state.get("species_name","").replace("_"," ")

        # Collect per-period PNG lists (subdirs that have at least one PNG)
        periods = []
        for sub in sorted(os.listdir(out_dir)):
            sub_path = os.path.join(out_dir, sub)
            if not os.path.isdir(sub_path) or sub in skip:
                continue
            # "current" subdirectory PNGs are already shown in section 6
            if sub == "current":
                continue
            pngs = sorted(f for f in os.listdir(sub_path) if f.lower().endswith(".png"))
            if pngs:
                periods.append((sub, sub_path, pngs))

        if not periods:
            return ""

        html  = "<h2>7. Future Scenarios</h2>"
        html += """<p>
Future habitat suitability projections were produced by applying the calibrated
ensemble model to projected climate layers for each scenario and time period.
The maps below were exported from the HABITUS projection map viewer using the
analyst-selected colour style at 300&nbsp;DPI. Each period is presented separately,
and the layer name embedded in the filename identifies the algorithm, pseudo-absence
replicate, and output type (probability or binary).
</p>"""

        for sec_no, (period, sub_path, pngs) in enumerate(periods, 1):
            html += f"<h3>7.{sec_no}. {period}</h3>"
            html += f"""<p style="font-size:10pt">
Climate scenario / time period: <b>{period}</b>. Maps reflect the ensemble
weighted-mean (EMwmean) projection and any individual algorithm outputs that
were loaded in the map viewer during this analysis session.
</p>"""
            for fig_no, fname in enumerate(pngs, 1):
                fpath = os.path.join(sub_path, fname)
                uri   = _b64_img(fpath)
                if not uri:
                    continue

                stem = fname[:-4]
                fl   = stem.lower()

                if "prob" in fl or "suitability" in fl:
                    map_type = "projected habitat suitability probability"
                    interp = (
                        "Areas of high projected suitability indicate environmentally "
                        "favourable conditions under this future scenario. Comparison with "
                        "the current probability map (Section&nbsp;6) reveals the direction "
                        "and magnitude of projected range shifts. Northward or upslope "
                        "displacement of high-suitability zones is consistent with warming "
                        "trends under most CMIP6 scenarios."
                    )
                elif "bin" in fl or "binary" in fl or "presence" in fl:
                    map_type = "binary projected distribution"
                    interp = (
                        "The binary future map applies the TSS-optimised threshold to the "
                        "projected probability surface. Overlaying this layer with the current "
                        "binary map (Section&nbsp;6) directly produces the range-change "
                        "classification reported in Section&nbsp;8."
                    )
                else:
                    map_type = "projected distribution"
                    interp = (
                        "This map represents a model projection for the selected climate "
                        "scenario exported with the analyst-chosen visualisation style."
                    )

                # Clean label: remove species prefix
                label = stem.replace("_"," ").strip()
                if sp_disp:
                    safe_sp = re.sub(r"[^\w ]","", sp_disp)
                    label   = re.sub(r"(?i)^" + re.escape(safe_sp) + r"\s*[_\-]?\s*", "", label).strip()
                if not label:
                    label = stem.replace("_"," ")

                cap = (f"Figure 7.{sec_no}.{fig_no}. <i>{sp_disp}</i> — {map_type}: "
                       f"<b>{label}</b> ({period}). "
                       f"Exported from HABITUS projection map viewer at 300&nbsp;DPI.")
                html += self._fig_block(uri, cap, interp)

        return html

    # ── 8. Range Change ───────────────────────────────────────────────────

    def _s8_range_change(self, state, figs):
        rr = state.get("range_results", {})
        if not rr:
            return ""

        html = "<h2>8. Range Change Analysis</h2>"
        html += """<p>
Species range change was quantified by comparing binary current and future
distribution maps pixel by pixel. Each cell was classified into one of four
categories: <b>Lost</b> (predicted present now, absent in future),
<b>Stable Present</b>, <b>Stable Absent</b>, and <b>Gained</b>
(absent now, present in future).
</p>"""

        for name, val in rr.items():
            try:
                stats, tif_path = val
            except (TypeError, ValueError):
                continue

            lost   = stats.get("Pct_Lost",  float("nan"))
            gained = stats.get("Pct_Gained", float("nan"))
            net    = stats.get("Net_Change",  float("nan"))
            tot_c  = stats.get("Total_Current",  "—")
            tot_f  = stats.get("Total_Future",   "—")

            html += f"<h3>8. {name}</h3>"
            rows = [
                ("Current range (cells)",  str(tot_c)),
                ("Future range (cells)",   str(tot_f)),
                ("Lost (%)",               _fmt(lost,  2)),
                ("Gained (%)",             _fmt(gained,2)),
                ("Net change (%)",         _fmt(net,   2)),
                ("Stable Present (cells)", str(stats.get("Stable_Present","—"))),
                ("Stable Absent (cells)",  str(stats.get("Stable_Absent","—"))),
                ("Lost (cells)",           str(stats.get("Lost","—"))),
                ("Gained (cells)",         str(stats.get("Gained","—"))),
            ]
            rhtml = "".join(f"<tr><td>{k}</td><td><b>{v}</b></td></tr>" for k,v in rows)
            html += f"<table><tr><th>Metric</th><th>Value</th></tr>{rhtml}</table>"

            # Interpret net change
            try:
                nv = float(net)
                if   nv >  10: direction = f"a projected range expansion of {nv:+.1f}%"
                elif nv < -10: direction = f"a projected range contraction of {nv:+.1f}%"
                else:          direction = f"relative range stability ({nv:+.1f}% net change)"
            except: direction = "indeterminate range change"
            html += (f'<div class="interp">Under the <b>{name}</b> scenario, the analysis indicates '
                     f'{direction}. '
                     f'Lost habitat ({_fmt(lost,1)}%) represents areas where current suitable '
                     f'conditions are projected to disappear, posing a climate risk. '
                     f'Gained habitat ({_fmt(gained,1)}%) represents newly suitable areas '
                     f'that may serve as refugia or colonisation targets.</div>')

            # Range change TIF
            if os.path.isfile(str(tif_path)):
                uri = self._render_range_tif(tif_path, f"Range Change — {name}")
                if uri:
                    html += self._fig_block(
                        uri,
                        f"Figure 8. Range change map for {name}. "
                        f"Red: lost; light grey: stable absent; teal: stable present; green: gained.",
                        ""
                    )
        return html

    def _render_range_tif(self, fpath, title):
        """Render a 4-class range-change TIF with geographically correct aspect ratio."""
        try:
            import rasterio, matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from matplotlib.colors import ListedColormap, BoundaryNorm
            import matplotlib.patches as mpatches

            with rasterio.open(fpath) as src:
                data   = src.read(1).astype(float)
                nodata = src.nodata
                bounds = src.bounds
            if nodata is not None:
                data = np.where(data == nodata, np.nan, data)

            # Geographic aspect ratio with cosine latitude correction
            width_deg  = bounds.right - bounds.left
            height_deg = bounds.top   - bounds.bottom
            lat_mid    = (bounds.top + bounds.bottom) / 2.0
            geo_ratio  = (width_deg * np.cos(np.radians(lat_mid))) / max(height_deg, 1e-6)
            map_w = 7.2
            map_h = float(np.clip(map_w / max(geo_ratio, 0.2), 2.5, 10.0))
            fig_w = map_w + 1.0
            fig_h = map_h + 1.6

            cmap   = ListedColormap(["#f03b20","#f0f0f0","#99d8c9","#2ca25f"])
            norm   = BoundaryNorm([-2.5,-1.5,-0.5,1.5,2.5], cmap.N)
            legend = [mpatches.Patch(color=c, label=l) for c,l in
                      zip(["#f03b20","#f0f0f0","#99d8c9","#2ca25f"],
                          ["Lost","Stable Absent","Stable Present","Gained"])]

            fig, ax = plt.subplots(figsize=(fig_w, fig_h), facecolor="#fff")
            ext = [bounds.left, bounds.right, bounds.bottom, bounds.top]
            ax.imshow(data, cmap=cmap, norm=norm, extent=ext,
                      origin="upper", interpolation="nearest", aspect="equal")
            ax.legend(handles=legend, loc="lower right", fontsize=8,
                      framealpha=0.9, edgecolor="#ccc")
            ax.set_xlabel("Longitude", fontsize=9)
            ax.set_ylabel("Latitude",  fontsize=9)
            ax.tick_params(labelsize=8)
            for sp in ax.spines.values(): sp.set_color("#ccc")

            sp_name = self.dlg.state.get("species_name","").replace("_"," ")
            if sp_name:
                fig.text(0.5, 0.98, sp_name, ha="center", va="top",
                         fontsize=10, fontstyle="italic", color="#1a5c3a")
            fig.suptitle(title, y=0.93, fontsize=11, fontweight="bold", color="#1a5c3a")

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#fff")
            plt.close(fig); buf.seek(0)
            return "data:image/png;base64," + base64.b64encode(buf.read()).decode()
        except Exception:
            return ""

    # ── 9. Validation ─────────────────────────────────────────────────────

    def _s9_validation(self):
        tab_v   = getattr(self.dlg, "tab_valid", None)
        results = getattr(tab_v, "_results", None) if tab_v else None
        if not results:
            return ""

        kappa = results.get("kappa", float("nan"))
        oa    = results.get("oa",    float("nan"))
        f1    = results.get("f1_weighted", float("nan"))
        mode  = results.get("mode","—")
        n_pts = results.get("n_points","—")
        ref   = results.get("reference","—")
        val   = results.get("validation","—")

        html = "<h2>9. Validation</h2>"
        html += f"""<p>
Independent validation was performed by comparing the model binary map against
reference data ({ref}) using {n_pts} evaluation points.
The {mode} validation framework was applied.
</p>"""

        rows = [
            ("Mode",                   mode),
            ("Reference layer",        ref),
            ("Validation layer",       val),
            ("Number of points",       str(n_pts)),
            ("Overall Accuracy (OA)",  _fmt(oa,3)),
            ("Cohen's Kappa (&kappa;)", _fmt(kappa,3)),
            ("F1 Score (weighted)",    _fmt(f1,3)),
        ]
        # Regression metrics if available
        for key, label in [("r2","R²"),("rmse","RMSE"),("mae","MAE")]:
            v = results.get(key)
            if v is not None:
                rows.append((label, _fmt(v,3)))

        rhtml = "".join(f"<tr><td>{k}</td><td><b>{v}</b></td></tr>" for k,v in rows)
        html += f"<table><tr><th>Metric</th><th>Value</th></tr>{rhtml}</table>"

        html += (f'<div class="interp">'
                 f'Cohen\'s &kappa; = {_fmt(kappa,3)} indicates <b>{_interp_kappa(kappa)}</b> '
                 f'between the modelled distribution and the reference map. '
                 f'Overall accuracy of {_fmt(oa*100 if oa<=1 else oa,1)}% reflects the '
                 f'proportion of correctly classified evaluation points. '
                 f'&kappa; values above 0.60 are generally considered acceptable for '
                 f'spatial model validation in conservation applications.</div>')

        # Confusion matrix
        cm     = results.get("cm")
        labels = results.get("labels")
        if cm and labels:
            try:
                thead_cm = "<tr><th>Actual \\ Predicted</th>" + \
                           "".join(f"<th>{l}</th>" for l in labels) + "</tr>"
                tbody_cm = ""
                for i,row in enumerate(cm):
                    tbody_cm += f"<tr><td><b>{labels[i]}</b></td>"
                    for j,val2 in enumerate(row):
                        style = " style='background:#d4edda;font-weight:bold'" if i==j else ""
                        tbody_cm += f"<td{style}>{val2}</td>"
                    tbody_cm += "</tr>"
                html += f"<h3>9.1 Confusion Matrix</h3><table>{thead_cm}{tbody_cm}</table>"
                html += """<div class="interp">
Diagonal cells (highlighted) represent correctly classified points.
Off-diagonal cells indicate misclassifications. A well-performing model
concentrates counts on the diagonal with minimal off-diagonal values.
</div>"""
            except Exception:
                pass

        # Validation raster map if available
        out_dir  = self.dlg.state.get("output_dir","")
        val_dir  = os.path.join(out_dir,"validation") if out_dir else ""
        val_tifs = []
        if os.path.isdir(val_dir):
            for f in sorted(os.listdir(val_dir)):
                if f.lower().startswith("reclassify") and f.lower().endswith(".tif"):
                    val_tifs.append(os.path.join(val_dir, f))
        if val_tifs:
            html += "<h3>9.2 Reclassified Validation Maps</h3>"
            for fp in val_tifs[:2]:
                uri = self._render_tif(fp, os.path.basename(fp).replace("_"," ").replace(".tif",""))
                if uri:
                    html += self._fig_block(
                        uri,
                        f"Figure 9. Reclassified validation layer: {os.path.basename(fp)}.",
                        "Spatial agreement between the reclassified model output and the "
                        "reference layer can be visually assessed; areas of disagreement "
                        "highlight regions where further field verification is warranted."
                    )
        return html

    # ══════════════════════════════════════════════════════════════════════
    # MAIN GENERATE
    # ══════════════════════════════════════════════════════════════════════

    def _generate(self):
        # Reset
        self._html_path = None
        self._btn_open.setEnabled(False)
        self._preview.clear()
        self._status_lbl.setText("Generating report from current outputs…")
        self._status_lbl.setStyleSheet(
            "color:#856404;font-size:10px;background:#fff3cd;"
            "border:1px solid #ffc107;border-radius:4px;padding:5px 8px;")

        state   = self.dlg.state
        m       = state.get("modeler")
        species = state.get("species_name","Species")
        out_dir = state.get("output_dir","")
        sp_disp = species.replace("_"," ")
        now     = datetime.datetime.now().strftime("%d %B %Y, %H:%M")

        self._progress.setVisible(True); self._progress.setValue(0)
        self._step("Scanning figures…", 5)
        figs = self._figures()

        sections = []

        # ── HTML header block ─────────────────────────────────────────────
        sections.append(f"""
<div style="text-align:center;margin-bottom:20px;padding-bottom:16px;border-bottom:2px solid #1a5c3a;">
  <div style="font-size:32pt;font-weight:900;letter-spacing:5px;color:#1d5235;line-height:1.1;">HABITUS</div>
  <div style="font-size:12pt;font-style:italic;color:#3a7050;margin-top:4px;">
    Habitat Analysis &amp; Biodiversity Integrated Toolkit for<br/>Unified Species Distribution Modelling
  </div>
  <div style="font-size:11pt;font-weight:bold;color:#1d5235;margin-top:14px;">Species Distribution Modelling Report</div>
  <div style="font-size:11pt;font-style:italic;color:#333;margin-top:4px;"><i>{sp_disp}</i></div>
  <div style="font-size:9.5pt;color:#666;margin-top:6px;">Generated: {now}</div>
</div>
<div class="notice">
This report was automatically generated by HABITUS SDM. Results and interpretive
text should be reviewed and adapted before submission to a scientific journal.
Re-run this generator after any new analysis to reflect updated outputs.
</div>""")

        # ── 1. Summary ────────────────────────────────────────────────────
        self._step("Study summary…", 10)
        sections.append(self._s1_summary(m, state))

        # ── 2. Variables ──────────────────────────────────────────────────
        if self._chk_vars.isChecked():
            self._step("Variable section…", 18)
            sections.append(self._s2_variables(state, figs))

        # ── 3. Methods ────────────────────────────────────────────────────
        if self._chk_methods.isChecked():
            self._step("Methods section…", 25)
            sections.append(self._s3_methods(m, state))

        # ── 4. Parameters ─────────────────────────────────────────────────
        if self._chk_params.isChecked():
            self._step("Model parameters…", 32)
            sections.append(self._s4_params(m, state))

        # ── 5. Evaluation ─────────────────────────────────────────────────
        if self._chk_eval.isChecked():
            self._step("Evaluation results…", 42)
            sections.append(self._s5_evaluation(m, figs))

        # ── 6. Current maps ───────────────────────────────────────────────
        if self._chk_maps.isChecked():
            self._step("Rendering current maps…", 55)
            s = self._s6_current_maps()
            if s: sections.append(s)

        # ── 7. Future maps ────────────────────────────────────────────────
        if self._chk_future.isChecked():
            self._step("Rendering future maps…", 67)
            s = self._s7_future_maps()
            if s: sections.append(s)

        # ── 8. Range change ───────────────────────────────────────────────
        if self._chk_range.isChecked():
            self._step("Range change…", 76)
            s = self._s8_range_change(state, figs)
            if s: sections.append(s)

        # ── 9. Validation ─────────────────────────────────────────────────
        if self._chk_valid.isChecked():
            self._step("Validation…", 83)
            s = self._s9_validation()
            if s: sections.append(s)

        # ── 10. Session log ───────────────────────────────────────────────
        if self._chk_log.isChecked():
            self._step("Reading log…", 90)
            log_text = self._read_log()
            if log_text:
                escaped = log_text.replace("&","&amp;").replace("<","&lt;")
                sections.append(f"<h2>10. Session Log</h2><div class='log-box'>{escaped}</div>")

        # ── Footer / Citation ─────────────────────────────────────────────
        sections.append("""
<footer>
  <p style="margin-bottom:6px;">
    <b>Citation:</b><br/>
    [Authors removed for peer review] (2026).
    HABITUS: Habitat Analysis and Biodiversity Integrated Toolkit for Unified
    Species Distribution Modelling.
    <i>Ecological Perspective</i>, [Technical Report].
    [DOI removed for peer review]
  </p>
  <p>Generated by HABITUS SDM</p>
</footer>""")

        # ── Assemble HTML ─────────────────────────────────────────────────
        self._step("Saving HTML…", 95)
        body = "\n".join(sections)
        html = (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n'
                f'<meta charset="UTF-8"/>\n'
                f'<meta name="viewport" content="width=device-width,initial-scale=1.0"/>\n'
                f'<title>HABITUS Report \u2013 {sp_disp}</title>\n'
                f'<style>\n{_CSS}\n</style>\n</head>\n<body>\n{body}\n</body>\n</html>')

        # ── Save ──────────────────────────────────────────────────────────
        if out_dir and os.path.isdir(out_dir):
            sp_slug = re.sub(r"[^\w.-]","_",sp_disp).strip("_") or "report"
            ts      = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fpath   = os.path.join(out_dir, f"{sp_slug}_HABITUS_report_{ts}.html")
        else:
            fpath, _ = QFileDialog.getSaveFileName(
                self, "Save HTML Report", f"{sp_disp}_HABITUS_report.html",
                "HTML files (*.html)")
            if not fpath:
                self._progress.setFormat("Cancelled"); self._progress.setVisible(False)
                self._status_lbl.setText("Cancelled."); return

        try:
            with open(fpath,"w",encoding="utf-8") as fh:
                fh.write(html)
            self._html_path = fpath
            self.dlg.log(f"HTML report saved: {fpath}")
        except Exception as exc:
            QMessageBox.critical(self,"Save Failed",str(exc))
            self._progress.setVisible(False); return

        self._step("Done!", 100)
        self._preview.setPlainText(html[:8000] + "\n…[truncated]…")
        self._btn_open.setEnabled(True)
        self._status_lbl.setText(
            f"Report saved: {fpath}  |  "
            "Click 'Generate HTML Report' again after re-running models to refresh.")
        self._status_lbl.setStyleSheet(
            "color:#155724;font-size:10px;background:#d4edda;"
            "border:1px solid #52b788;border-radius:4px;padding:5px 8px;")
        QMessageBox.information(self,"Report Ready",
            f"HTML report saved to:\n{fpath}\n\nClick 'Open in Browser' to view it.")
        self._progress.setVisible(False)

    def _open_browser(self):
        if not self._html_path: return
        try:
            import webbrowser
            webbrowser.open("file:///" + self._html_path.replace(os.sep,"/"))
        except Exception as exc:
            QMessageBox.warning(self,"Cannot Open",str(exc))
